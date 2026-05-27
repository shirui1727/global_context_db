from hashlib import sha256
from collections import Counter
from datetime import datetime, timezone
import json
from itertools import combinations

from app.core.schemas import (
    ImprovementTaskCreate,
    MemoryCreate,
    MemoryEvidenceCreate,
    MemoryPromotionCreate,
    MemoryPromotionReview,
    MemoryPromotionUpdate,
    MemoryUpdate,
)
from app.improvements.service import create_improvement_task
from app.reader.service import read_text_fast
from app.retrieval.embedding import embed_text
from app.storage.repo import (
    audit_logs_repo,
    memories_repo,
    memory_evidence_repo,
    memory_promotion_proposals_repo,
    memory_versions_repo,
    session_events_repo,
)
from app.storage.vector_store import delete_item, search_items, upsert_items


def _actor(agent_id: str | None, user_id: str | None) -> str:
    return agent_id or user_id or "unknown"


def _audit(action: str, target_id: str, actor: str, metadata: dict | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    audit_logs_repo().insert(
        {
            "id": sha256(f"{now}:{actor}:{action}:{target_id}".encode("utf-8")).hexdigest(),
            "actor": actor,
            "action": action,
            "target_type": "memory",
            "target_id": target_id,
            "created_at": now,
            "metadata": metadata or {},
        }
    )


def _version(memory_id: str, row: dict, change_type: str) -> None:
    changed_at = datetime.now(timezone.utc).isoformat()
    memory_versions_repo().insert(
        {
            "id": sha256(f"{changed_at}:{change_type}:{memory_id}".encode("utf-8")).hexdigest(),
            "memory_id": memory_id,
            "content": row.get("content"),
            "tags": row.get("tags", []),
            "user_id": row.get("user_id"),
            "agent_id": row.get("agent_id"),
            "session_id": row.get("session_id"),
            "conversation_id": row.get("conversation_id"),
            "memory_type": row.get("memory_type"),
            "metadata": row.get("metadata", {}),
            "changed_at": changed_at,
            "change_type": change_type,
        }
    )


def add_memory(payload: MemoryCreate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    memory_id = sha256(
        "|".join(
            [
                payload.user_id,
                payload.agent_id or "",
                payload.session_id or "",
                payload.conversation_id or "",
                payload.memory_type,
                payload.content,
            ]
        ).encode("utf-8")
    ).hexdigest()
    reader_item = read_text_fast(
        source=payload.source_kind,
        text=payload.content,
        cube_id=payload.cube_id,
        tags=payload.tags,
        metadata={**payload.metadata, "source_domain": "memory"},
    )
    reader_metadata = {
        "source_domain": "memory",
        "source_id": memory_id,
        "content_kind": reader_item.content_kind,
        "provenance": {**reader_item.provenance, "source_domain": "memory", "source_id": memory_id},
    }
    metadata = {**payload.metadata, "reader": reader_metadata}
    row = {
        "id": memory_id,
        "content": payload.content,
        "cube_id": payload.cube_id,
        "tags": payload.tags,
        "user_id": payload.user_id,
        "agent_id": payload.agent_id,
        "session_id": payload.session_id,
        "conversation_id": payload.conversation_id,
        "memory_type": payload.memory_type,
        "context_domain": payload.context_domain,
        "status": payload.status,
        "source_kind": payload.source_kind,
        "trust_level": payload.trust_level,
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
    }
    existing = memories_repo().get(memory_id)
    if existing is not None:
        _audit(
            "memory.deduplicated",
            memory_id,
            _actor(payload.agent_id, payload.user_id),
            {"reason": "same scoped content already exists"},
        )
        return {"memory_id": memory_id, "memory": existing, "status": "deduplicated"}
    memories_repo().upsert(row)
    for evidence in payload.evidence:
        add_memory_evidence(memory_id, evidence)
    _version(memory_id, row, "created")
    _audit("memory.created", memory_id, _actor(payload.agent_id, payload.user_id))
    upsert_items(
        [
            {
                "id": memory_id,
                "kind": "memory",
                "text": payload.content,
                "vector": embed_text(payload.content).tolist(),
                "cube_id": payload.cube_id,
                "tags": payload.tags,
                "user_id": payload.user_id,
                "agent_id": payload.agent_id,
                "session_id": payload.session_id,
                "conversation_id": payload.conversation_id,
                "memory_type": payload.memory_type,
                "context_domain": payload.context_domain,
                "status": payload.status,
                "source_kind": payload.source_kind,
                "trust_level": payload.trust_level,
                "metadata": metadata,
            }
        ]
    )
    return {"memory_id": memory_id, "memory": memories_repo().get(memory_id), "status": "created"}


def add_memory_evidence(memory_id: str, payload: MemoryEvidenceCreate) -> dict:
    if memories_repo().get(memory_id) is None:
        raise ValueError("memory not found")
    now = datetime.now(timezone.utc).isoformat()
    evidence_id = sha256(
        f"evidence:{memory_id}:{payload.source_domain}:{payload.source_id}:{payload.quote}".encode("utf-8")
    ).hexdigest()
    row = {
        "id": evidence_id,
        "memory_id": memory_id,
        "source_domain": payload.source_domain,
        "source_id": payload.source_id,
        "quote": payload.quote,
        "confidence": payload.confidence,
        "created_at": now,
        "metadata": payload.metadata,
    }
    memory_evidence_repo().insert(row)
    _audit("memory_evidence.created", memory_id, "memory_quality", {"evidence_id": evidence_id, "source_domain": payload.source_domain})
    return row


def list_memory_evidence(memory_id: str, limit: int = 50) -> list[dict]:
    if memories_repo().get(memory_id) is None:
        raise ValueError("memory not found")
    return memory_evidence_repo().list_by_memory(memory_id, limit)


PROMOTION_STATUSES = {"pending", "approved", "rejected", "promoted", "archived"}


def create_memory_promotion(payload: MemoryPromotionCreate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    source_event_ids = payload.source_event_ids or _recent_session_event_ids(payload.source_session_id)
    proposal_id = sha256(
        f"promotion:{payload.source_session_id}:{payload.proposed_content}:{','.join(source_event_ids)}".encode("utf-8")
    ).hexdigest()
    row = memory_promotion_proposals_repo().upsert(
        {
            "id": proposal_id,
            "source_session_id": payload.source_session_id,
            "source_event_ids": source_event_ids,
            "proposed_content": payload.proposed_content,
            "cube_id": payload.cube_id,
            "tags": payload.tags,
            "memory_type": payload.memory_type,
            "user_id": payload.user_id,
            "agent_id": payload.agent_id,
            "project_path": payload.project_path,
            "status": "pending",
            "reason": payload.reason,
            "created_by": payload.created_by,
            "reviewed_by": None,
            "created_at": now,
            "updated_at": now,
            "reviewed_at": None,
            "promoted_memory_id": None,
            "metadata": payload.metadata,
        }
    )
    _audit("memory_promotion.created", proposal_id, payload.created_by or "memory_quality", {"source_session_id": payload.source_session_id})
    return row


def list_memory_promotions(limit: int = 100, status: str | None = None, source_session_id: str | None = None) -> list[dict]:
    return memory_promotion_proposals_repo().list_recent(limit=limit, status=status, source_session_id=source_session_id)


def memory_quality_report(limit: int = 100) -> dict:
    memories = memories_repo().list_all(limit=max(limit, 1000))
    active = [memory for memory in memories if memory.get("status") == "active"]
    low_evidence = _low_evidence_candidates(active, limit)
    stale = _stale_candidates(memories, limit)
    conflicts = _conflict_candidates(active, limit)
    return {
        "summary": {
            "total_memories_checked": len(memories),
            "active_memories_checked": len(active),
            "low_evidence_count": len(low_evidence),
            "stale_count": len(stale),
            "conflict_candidate_count": len(conflicts),
            "status_counts": _count_by(memories, "status", "active"),
            "trust_level_counts": _count_by(memories, "trust_level", "verified"),
            "source_kind_counts": _count_by(memories, "source_kind", "agent_note"),
        },
        "low_evidence": low_evidence,
        "stale": stale,
        "conflicts": conflicts,
    }


def enqueue_memory_quality_improvements(limit: int = 100, created_by: str | None = None) -> dict:
    report = memory_quality_report(limit)
    tasks = []
    for item in report["low_evidence"]:
        tasks.append(
            create_improvement_task(
                ImprovementTaskCreate(
                    task_kind="verify_memory_evidence",
                    target_domain="memory",
                    target_id=item["memory_id"],
                    priority=70,
                    reason=item["reason"],
                    created_by=created_by or "memory_quality",
                    metadata={"quality_category": "low_evidence", "candidate": item},
                )
            )
        )
    for item in report["stale"]:
        tasks.append(
            create_improvement_task(
                ImprovementTaskCreate(
                    task_kind="refresh_stale_memory",
                    target_domain="memory",
                    target_id=item["memory_id"],
                    priority=75,
                    reason="; ".join(item["reasons"]),
                    created_by=created_by or "memory_quality",
                    metadata={"quality_category": "stale", "candidate": item},
                )
            )
        )
    for item in report["conflicts"]:
        target_id = sha256("|".join(item["memory_ids"]).encode("utf-8")).hexdigest()
        tasks.append(
            create_improvement_task(
                ImprovementTaskCreate(
                    task_kind="resolve_memory_conflict",
                    target_domain="memory",
                    target_id=target_id,
                    priority=85,
                    reason=item["reason"],
                    created_by=created_by or "memory_quality",
                    metadata={"quality_category": "conflict", "candidate": item},
                )
            )
        )
    _audit(
        "memory_quality.enqueued",
        "memory_quality",
        created_by or "memory_quality",
        {"created_count": len(tasks), "summary": report["summary"]},
    )
    return {"created_count": len(tasks), "tasks": tasks, "quality": report}


def _count_by(rows: list[dict], field: str, fallback: str) -> dict[str, int]:
    return dict(Counter(row.get(field) or fallback for row in rows))


def _low_evidence_candidates(memories: list[dict], limit: int) -> list[dict]:
    candidates = []
    for memory in memories:
        evidence = memory_evidence_repo().list_by_memory(memory["id"], limit=1)
        if evidence:
            continue
        if memory.get("source_kind") in {"manual", "user_confirmed"}:
            continue
        candidates.append(
            {
                "memory_id": memory["id"],
                "reason": "active memory has no evidence references",
                "trust_level": memory.get("trust_level"),
                "source_kind": memory.get("source_kind"),
                "evidence_count": 0,
                "content_preview": memory.get("content", "")[:240],
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def _stale_candidates(memories: list[dict], limit: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    candidates = []
    for memory in memories:
        metadata = memory.get("metadata") or {}
        valid_until = metadata.get("valid_until")
        stale_reason = metadata.get("stale_reason")
        reasons = []
        if memory.get("status") in {"stale", "deprecated"}:
            reasons.append(f"status={memory.get('status')}")
        expires_at = _parse_datetime(valid_until)
        if expires_at is not None and expires_at < now:
            reasons.append(f"valid_until={valid_until}")
        if isinstance(stale_reason, str) and stale_reason:
            reasons.append(f"stale_reason={stale_reason}")
        if not reasons:
            continue
        candidates.append(
            {
                "memory_id": memory["id"],
                "reasons": reasons,
                "content_preview": memory.get("content", "")[:240],
                "updated_at": memory.get("updated_at"),
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _conflict_candidates(memories: list[dict], limit: int) -> list[dict]:
    buckets: dict[tuple, list[dict]] = {}
    for memory in memories:
        key = (
            memory.get("user_id") or "default",
            memory.get("agent_id") or "",
            memory.get("memory_type") or "long_term",
            tuple(sorted(memory.get("tags") or [])),
        )
        buckets.setdefault(key, []).append(memory)
    candidates = []
    for key, bucket in buckets.items():
        if len(bucket) < 2:
            continue
        for left, right in combinations(bucket[:30], 2):
            conflict = _text_conflict_reason(left.get("content", ""), right.get("content", ""))
            if not conflict:
                continue
            candidates.append(
                {
                    "scope": {
                        "user_id": key[0],
                        "agent_id": key[1] or None,
                        "memory_type": key[2],
                        "tags": list(key[3]),
                    },
                    "reason": conflict,
                    "memory_ids": [left["id"], right["id"]],
                    "previews": [left.get("content", "")[:180], right.get("content", "")[:180]],
                }
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def _text_conflict_reason(left: str, right: str) -> str | None:
    left_l = left.lower()
    right_l = right.lower()
    opposite_pairs = [
        (" use ", " do not use "),
        (" should ", " should not "),
        (" enable ", " disable "),
        (" enabled ", " disabled "),
        (" allow ", " deny "),
        (" allowed ", " denied "),
        (" active ", " archived "),
        (" verified ", " unverified "),
        (" prefer ", " avoid "),
        ("\u63a8\u8350", "\u4e0d\u8981"),
        ("\u4f7f\u7528", "\u4e0d\u7528"),
        ("\u542f\u7528", "\u7981\u7528"),
        ("\u5141\u8bb8", "\u62d2\u7edd"),
    ]
    padded_left = f" {left_l} "
    padded_right = f" {right_l} "
    for positive, negative in opposite_pairs:
        if (positive in padded_left and negative in padded_right) or (negative in padded_left and positive in padded_right):
            return f"opposite markers detected: {positive.strip()} vs {negative.strip()}"
    return None


def update_memory_promotion(proposal_id: str, payload: MemoryPromotionUpdate) -> dict:
    current = memory_promotion_proposals_repo().get(proposal_id)
    if not current:
        raise ValueError("memory promotion proposal not found")
    changes = payload.model_dump(exclude_unset=True)
    status = changes.get("status") or current["status"]
    if status not in PROMOTION_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(PROMOTION_STATUSES))}")
    now = datetime.now(timezone.utc).isoformat()
    updated = {
        **current,
        **{key: value for key, value in changes.items() if value is not None},
        "status": status,
        "updated_at": now,
        "reviewed_at": now if status in {"approved", "rejected", "promoted"} else current.get("reviewed_at"),
        "metadata": changes.get("metadata") if changes.get("metadata") is not None else current.get("metadata", {}),
    }
    row = memory_promotion_proposals_repo().upsert(updated)
    _audit("memory_promotion.updated", proposal_id, payload.reviewed_by or "memory_quality", {"status": row["status"]})
    return row


def review_memory_promotion(proposal_id: str, payload: MemoryPromotionReview) -> dict:
    proposal = memory_promotion_proposals_repo().get(proposal_id)
    if not proposal:
        raise ValueError("memory promotion proposal not found")
    action = payload.action
    if action == "reject":
        return update_memory_promotion(
            proposal_id,
            MemoryPromotionUpdate(status="rejected", reviewed_by=payload.reviewed_by, metadata=payload.metadata),
        )
    if action not in {"approve", "promote"}:
        raise ValueError("action must be one of: approve, promote, reject")
    memory = add_memory(
        MemoryCreate(
            content=proposal["proposed_content"],
            cube_id=proposal.get("cube_id"),
            tags=proposal["tags"],
            user_id=proposal["user_id"],
            agent_id=proposal["agent_id"],
            session_id=proposal["source_session_id"],
            memory_type=proposal["memory_type"],
            status=payload.status_on_memory,
            source_kind="session_promotion",
            trust_level=payload.trust_level,
            metadata={
                **proposal.get("metadata", {}),
                **payload.metadata,
                "promotion_proposal_id": proposal_id,
                "project_path": proposal.get("project_path"),
            },
            evidence=[
                MemoryEvidenceCreate(
                    source_domain="session_event",
                    source_id=event_id,
                    quote=_event_quote(event_id),
                    confidence=1.0,
                    metadata={"promotion_proposal_id": proposal_id},
                )
                for event_id in proposal["source_event_ids"]
            ],
        )
    )
    now = datetime.now(timezone.utc).isoformat()
    promoted = memory_promotion_proposals_repo().upsert(
        {
            **proposal,
            "status": "promoted",
            "reviewed_by": payload.reviewed_by,
            "reviewed_at": now,
            "updated_at": now,
            "promoted_memory_id": memory["memory_id"],
            "metadata": {**proposal.get("metadata", {}), **payload.metadata},
        }
    )
    _audit("memory_promotion.promoted", proposal_id, payload.reviewed_by or "memory_quality", {"memory_id": memory["memory_id"]})
    return {"proposal": promoted, "memory": memory}


def _recent_session_event_ids(session_id: str, limit: int = 10) -> list[str]:
    return [event["id"] for event in reversed(session_events_repo().list_by_session(session_id, limit))]


def _event_quote(event_id: str) -> str:
    # The repo currently indexes events by session, so this is intentionally best-effort.
    return f"session_event:{event_id}"


def _decode_metadata(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def search_memory(
    query: str,
    top_k: int = 5,
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
    cube_ids: list[str] | None = None,
) -> dict:
    results = search_items(query, max(top_k * 5, top_k), kind="memory", cube_ids=cube_ids)
    cleaned = []
    for row in results:
        if user_id and row.get("user_id") != user_id:
            continue
        if agent_id and row.get("agent_id") != agent_id:
            continue
        if memory_type and row.get("memory_type") != memory_type:
            continue
        cleaned.append(
            {
                "id": row.get("id"),
                "kind": row.get("kind"),
                "text": row.get("text"),
                "cube_id": row.get("cube_id"),
                "tags": row.get("tags"),
                "user_id": row.get("user_id"),
                "agent_id": row.get("agent_id"),
                "session_id": row.get("session_id"),
                "conversation_id": row.get("conversation_id"),
                "memory_type": row.get("memory_type"),
                "context_domain": row.get("context_domain", "memory"),
                "status": row.get("status", "active"),
                "source_kind": row.get("source_kind", "agent_note"),
                "trust_level": row.get("trust_level", "verified"),
                "metadata": _decode_metadata(row.get("metadata")),
                "score": float(1.0 / (1.0 + max(row.get("_distance", 0.0), 0.0))),
            }
        )
    return {"results": cleaned[:top_k]}


def list_memories(user_id: str | None = None, agent_id: str | None = None, memory_type: str | None = None, limit: int = 100) -> list[dict]:
    return memories_repo().list_all(user_id=user_id, agent_id=agent_id, memory_type=memory_type, limit=limit)


def update_memory(memory_id: str, payload: MemoryUpdate) -> dict:
    current = memories_repo().get(memory_id)
    if current is None:
        raise ValueError("memory not found")
    updated = {
        **current,
        **{k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _version(memory_id, current, "before_update")
    memories_repo().upsert(updated)
    _version(memory_id, updated, "updated")
    _audit("memory.updated", memory_id, _actor(updated.get("agent_id"), updated.get("user_id")))
    delete_item(memory_id)
    upsert_items(
        [
            {
                "id": memory_id,
                "kind": "memory",
                "text": updated["content"],
                "vector": embed_text(updated["content"]).tolist(),
                "cube_id": updated.get("cube_id"),
                "tags": updated.get("tags", []),
                "user_id": updated.get("user_id", "default"),
                "agent_id": updated.get("agent_id"),
                "session_id": updated.get("session_id"),
                "conversation_id": updated.get("conversation_id"),
                "memory_type": updated.get("memory_type", "long_term"),
                "context_domain": updated.get("context_domain", "memory"),
                "status": updated.get("status", "active"),
                "source_kind": updated.get("source_kind", "agent_note"),
                "trust_level": updated.get("trust_level", "verified"),
                "metadata": updated.get("metadata", {}),
            }
        ]
    )
    return {"memory_id": memory_id, "memory": memories_repo().get(memory_id)}


def delete_memory(memory_id: str) -> dict:
    current = memories_repo().get(memory_id)
    existed = memories_repo().delete(memory_id)
    if current is not None:
        _version(memory_id, current, "deleted")
        _audit("memory.deleted", memory_id, _actor(current.get("agent_id"), current.get("user_id")))
    delete_item(memory_id)
    return {"deleted": existed, "memory_id": memory_id}


def list_memory_versions(memory_id: str, limit: int = 20) -> list[dict]:
    return memory_versions_repo().list_by_memory(memory_id, limit)


def list_audit_logs(limit: int = 100) -> list[dict]:
    return audit_logs_repo().list_recent(limit)
