from hashlib import sha256
from collections import Counter
from datetime import datetime, timezone
import json
from itertools import combinations

from app.core.schemas import (
    FineReaderRequest,
    ImprovementTaskCreate,
    MemoryCreate,
    MemoryEvidenceCreate,
    MemoryPromotionCreate,
    MemoryPromotionReview,
    MemoryPromotionUpdate,
    MemoryUpdate,
    ReaderItem,
)
from app.cubes.service import resolve_default_cube
from app.improvements.service import create_improvement_task
from app.hooks.service import emit_domain_event
from app.reader.service import read_text_fast, read_text_fine, reader_item_to_memory_candidate
from app.retrieval.embedding import embed_text
from app.storage.repo import (
    audit_logs_repo,
    memory_candidates_repo,
    memories_repo,
    memory_evidence_repo,
    memory_lifecycle_events_repo,
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


def _record_lifecycle(
    memory_id: str,
    *,
    event_kind: str,
    from_status: str | None,
    to_status: str | None,
    actor: str | None,
    metadata: dict | None = None,
) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    row = {
        "id": sha256(
            f"lifecycle:{created_at}:{memory_id}:{event_kind}:{from_status or ''}:{to_status or ''}:{actor or ''}".encode(
                "utf-8"
            )
        ).hexdigest(),
        "memory_id": memory_id,
        "from_status": from_status,
        "to_status": to_status,
        "event_kind": event_kind,
        "actor": actor or "unknown",
        "created_at": created_at,
        "metadata": metadata or {},
    }
    return memory_lifecycle_events_repo().insert(row)


def _update_event_kind(current: dict, updated: dict, changes: dict) -> str:
    old_status = current.get("status") or "active"
    new_status = updated.get("status") or old_status
    if new_status == "archived" and old_status != "archived":
        return "archived"
    if new_status == "deleted" and old_status != "deleted":
        return "deleted"
    if new_status == "conflicted" and old_status != "conflicted":
        return "conflicted"
    if new_status == "verified" or changes.get("trust_level") == "verified":
        return "verified"
    if new_status == "stale" and old_status != "stale":
        return "expired"
    return "corrected"


def add_memory(payload: MemoryCreate) -> dict:
    writable_cube_ids = _unique_tags(payload.writable_cube_ids)
    if writable_cube_ids:
        results = []
        for writable_cube_id in writable_cube_ids:
            scoped_payload = payload.model_copy(update={"cube_id": writable_cube_id, "writable_cube_ids": []})
            results.append(add_memory(scoped_payload))
        created_count = sum(1 for result in results if result.get("status") == "created")
        deduplicated_count = sum(1 for result in results if result.get("status") == "deduplicated")
        primary = results[0] if results else {}
        return {
            **primary,
            "status": "created" if created_count else primary.get("status", "deduplicated"),
            "memories": [result.get("memory") for result in results if result.get("memory")],
            "write_scope": {
                "writable_cube_ids": writable_cube_ids,
                "created_count": created_count,
                "deduplicated_count": deduplicated_count,
                "results": [
                    {
                        "cube_id": (result.get("memory") or {}).get("cube_id"),
                        "memory_id": result.get("memory_id"),
                        "status": result.get("status"),
                    }
                    for result in results
                ],
            },
        }

    now = datetime.now(timezone.utc).isoformat()
    cube_id = resolve_default_cube(
        cube_id=payload.cube_id,
        session_id=payload.session_id,
        agent_id=payload.agent_id,
        user_id=payload.user_id,
        created_by=payload.agent_id or payload.user_id,
    )
    memory_id = sha256(
        "|".join(
            [
                cube_id or "",
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
        cube_id=cube_id,
        tags=payload.tags,
        metadata={**payload.metadata, "source_domain": "memory"},
    )
    reader_metadata = {
        **(reader_item.metadata.get("reader") if isinstance(reader_item.metadata.get("reader"), dict) else {}),
        "source_domain": "memory",
        "source_id": memory_id,
        "content_kind": reader_item.content_kind,
        "provenance": {**reader_item.provenance, "source_domain": "memory", "source_id": memory_id},
        "evidence_count": len(reader_item.evidence),
    }
    metadata = {**payload.metadata, "reader": reader_metadata}
    row = {
        "id": memory_id,
        "content": payload.content,
        "cube_id": cube_id,
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
    _record_lifecycle(
        memory_id,
        event_kind="created",
        from_status=None,
        to_status=payload.status,
        actor=_actor(payload.agent_id, payload.user_id),
        metadata={"source_kind": payload.source_kind, "cube_id": cube_id},
    )
    _audit("memory.created", memory_id, _actor(payload.agent_id, payload.user_id))
    upsert_items(
        [
            {
                "id": memory_id,
                "kind": "memory",
                "text": payload.content,
                "vector": embed_text(payload.content).tolist(),
                "cube_id": cube_id,
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
    saved = memories_repo().get(memory_id)
    emit_domain_event(
        "memory.created",
        source_kind="memory",
        source_id=memory_id,
        payload={
            "memory_id": memory_id,
            "cube_id": cube_id,
            "status": payload.status,
            "source_kind": payload.source_kind,
            "trust_level": payload.trust_level,
        },
    )
    return {"memory_id": memory_id, "memory": saved, "status": "created"}


def create_memory_candidate_from_reader(
    item: ReaderItem,
    *,
    created_by: str | None = None,
    status: str = "candidate",
    metadata: dict | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    row = reader_item_to_memory_candidate(item, status=status, created_by=created_by, metadata=metadata)
    row.update({"created_at": now, "updated_at": now})
    return memory_candidates_repo().upsert(row)


def create_memory_candidates_from_fine_reader(
    *,
    source: str,
    text: str,
    cube_id: str | None = None,
    tags: list[str] | None = None,
    created_by: str | None = None,
    metadata: dict | None = None,
) -> dict:
    reader_item = read_text_fine(source=source, text=text, cube_id=cube_id, tags=tags, metadata=metadata)
    candidates = []
    fine_candidates = reader_item.metadata.get("fine_candidates", [])
    for fine_candidate in fine_candidates:
        evidence_index = fine_candidate.get("evidence_index")
        selected_evidence = reader_item.evidence[evidence_index] if isinstance(evidence_index, int) and 0 <= evidence_index < len(reader_item.evidence) else None
        item = ReaderItem(
            source_domain=reader_item.source_domain,
            source_id=f"{reader_item.source_id}:{evidence_index}",
            cube_id=reader_item.cube_id,
            content=fine_candidate["content"],
            content_kind=f"fine_{fine_candidate['memory_type']}",
            tags=_unique_tags(reader_item.tags, fine_candidate.get("tags", [])),
            confidence=fine_candidate.get("confidence", reader_item.confidence),
            provenance={
                **reader_item.provenance,
                "reader_mode": "fine",
                "parent_source_id": reader_item.source_id,
                "fine_memory_type": fine_candidate["memory_type"],
            },
            evidence=[selected_evidence] if selected_evidence is not None else [],
            metadata={
                **(metadata or {}),
                "fine": fine_candidate,
                "reader": {
                    **(reader_item.metadata.get("reader") if isinstance(reader_item.metadata.get("reader"), dict) else {}),
                    "parent_source_id": reader_item.source_id,
                    "memory_type": fine_candidate["memory_type"],
                },
            },
        )
        candidates.append(create_memory_candidate_from_reader(item, created_by=created_by, metadata={"fine": fine_candidate}))
    reader_payload = reader_item.model_dump()
    return {"created_count": len(candidates), "reader_item": reader_payload, "reader_item_obj": reader_item, "candidates": candidates}


def create_memory_candidates_from_fine_request(payload: FineReaderRequest) -> dict:
    return create_memory_candidates_from_fine_reader(
        source=payload.source,
        text=payload.text,
        cube_id=payload.cube_id,
        tags=payload.tags,
        created_by=payload.created_by,
        metadata=payload.metadata,
    )


def _unique_tags(*groups: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for group in groups:
        for value in group or []:
            tag = str(value).strip()
            if tag and tag not in seen:
                seen.add(tag)
                tags.append(tag)
    return tags


def list_memory_candidates(
    limit: int = 100,
    status: str | None = None,
    source_domain: str | None = None,
) -> list[dict]:
    return memory_candidates_repo().list_recent(limit=limit, status=status, source_domain=source_domain)


def promote_memory_candidate(
    candidate_id: str,
    *,
    reviewed_by: str | None = None,
    trust_level: str = "verified",
    status_on_memory: str = "active",
) -> dict:
    candidate = memory_candidates_repo().get(candidate_id)
    if candidate is None:
        raise ValueError("memory candidate not found")
    if candidate.get("promoted_memory_id"):
        promoted_memory = memories_repo().get(candidate["promoted_memory_id"])
        return {"candidate": candidate, "memory_id": candidate["promoted_memory_id"], "memory": promoted_memory}
    memory_result = add_memory(
        MemoryCreate(
            content=candidate["content"],
            cube_id=candidate.get("cube_id"),
            tags=candidate.get("tags", []),
            status=status_on_memory,
            source_kind="reader_candidate",
            trust_level=trust_level,
            metadata={
                **candidate.get("metadata", {}),
                "candidate_id": candidate["id"],
                "candidate_source_domain": candidate.get("source_domain"),
                "candidate_source_id": candidate.get("source_id"),
                "candidate_provenance": candidate.get("provenance", {}),
            },
            evidence=[
                MemoryEvidenceCreate(
                    source_domain=evidence.get("source_domain") or candidate.get("source_domain"),
                    source_id=evidence.get("source_id") or candidate.get("source_id"),
                    quote=evidence.get("quote", ""),
                    confidence=evidence.get("confidence", candidate.get("confidence", 1.0)),
                    source_span=evidence.get("source_span"),
                    metadata={**(evidence.get("metadata") or {}), "candidate_id": candidate["id"]},
                )
                for evidence in candidate.get("evidence", [])
            ],
        )
    )
    now = datetime.now(timezone.utc).isoformat()
    updated_candidate = memory_candidates_repo().upsert(
        {
            **candidate,
            "status": status_on_memory,
            "updated_at": now,
            "promoted_memory_id": memory_result["memory_id"],
            "metadata": {**candidate.get("metadata", {}), "reviewed_by": reviewed_by},
        }
    )
    _record_lifecycle(
        memory_result["memory_id"],
        event_kind="promoted",
        from_status="candidate",
        to_status=status_on_memory,
        actor=reviewed_by or "memory_quality",
        metadata={"candidate_id": candidate["id"], "source_domain": candidate.get("source_domain")},
    )
    emit_domain_event(
        "memory_candidate.promoted",
        source_kind="memory_candidate",
        source_id=candidate["id"],
        payload={
            "candidate_id": candidate["id"],
            "memory_id": memory_result["memory_id"],
            "cube_id": candidate.get("cube_id"),
            "status": status_on_memory,
        },
    )
    return {"candidate": updated_candidate, "memory_id": memory_result["memory_id"], "memory": memory_result["memory"]}


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
        "source_span": payload.source_span.model_dump() if payload.source_span is not None else {},
        "created_at": now,
        "metadata": payload.metadata,
    }
    memory_evidence_repo().insert(row)
    _audit("memory_evidence.created", memory_id, "memory_quality", {"evidence_id": evidence_id, "source_domain": payload.source_domain})
    emit_domain_event(
        "memory_evidence.created",
        source_kind="memory",
        source_id=memory_id,
        payload={"memory_id": memory_id, "evidence_id": evidence_id, "source_domain": payload.source_domain, "source_id": payload.source_id},
    )
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
    emit_domain_event(
        "memory_promotion.created",
        source_kind="memory_promotion",
        source_id=proposal_id,
        payload={"proposal_id": proposal_id, "source_session_id": payload.source_session_id, "cube_id": payload.cube_id},
    )
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


def enqueue_memory_hygiene(limit: int = 100, created_by: str | None = None, queue_name: str = "memory_hygiene") -> dict:
    report = memory_quality_report(limit)
    tasks = []
    actor = created_by or "memory_hygiene"
    for item in report["low_evidence"]:
        tasks.append(
            create_improvement_task(
                ImprovementTaskCreate(
                    task_kind="verify_memory_evidence",
                    target_domain="memory",
                    target_id=item["memory_id"],
                    priority=70,
                    reason=item["reason"],
                    created_by=actor,
                    queue_name=queue_name,
                    metadata={"quality_category": "low_evidence", "candidate": item, "hygiene": True},
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
                    created_by=actor,
                    queue_name=queue_name,
                    metadata={"quality_category": "stale", "candidate": item, "hygiene": True},
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
                    created_by=actor,
                    queue_name=queue_name,
                    metadata={"quality_category": "conflict", "candidate": item, "hygiene": True},
                )
            )
        )
    _audit(
        "memory_hygiene.enqueued",
        "memory_hygiene",
        actor,
        {"created_count": len(tasks), "queue_name": queue_name, "summary": report["summary"]},
    )
    return {"created_count": len(tasks), "queue_name": queue_name, "tasks": tasks, "quality": report}


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
    emit_domain_event(
        "memory_promotion.updated",
        source_kind="memory_promotion",
        source_id=proposal_id,
        payload={"proposal_id": proposal_id, "status": row["status"], "promoted_memory_id": row.get("promoted_memory_id")},
    )
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
    _record_lifecycle(
        memory["memory_id"],
        event_kind="promoted",
        from_status="candidate",
        to_status=memory["memory"].get("status", payload.status_on_memory),
        actor=payload.reviewed_by or "memory_quality",
        metadata={"promotion_proposal_id": proposal_id, "source_session_id": proposal.get("source_session_id")},
    )
    emit_domain_event(
        "memory_promotion.promoted",
        source_kind="memory_promotion",
        source_id=proposal_id,
        payload={"proposal_id": proposal_id, "memory_id": memory["memory_id"], "source_session_id": proposal.get("source_session_id")},
    )
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
    changes = payload.model_dump(exclude_unset=True)
    updated = {
        **current,
        **{k: v for k, v in changes.items() if v is not None},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _version(memory_id, current, "before_update")
    memories_repo().upsert(updated)
    _version(memory_id, updated, "updated")
    _record_lifecycle(
        memory_id,
        event_kind=_update_event_kind(current, updated, changes),
        from_status=current.get("status") or "active",
        to_status=updated.get("status") or current.get("status") or "active",
        actor=_actor(updated.get("agent_id"), updated.get("user_id")),
        metadata={"changed_fields": sorted(k for k, value in changes.items() if value is not None)},
    )
    _audit("memory.updated", memory_id, _actor(updated.get("agent_id"), updated.get("user_id")))
    emit_domain_event(
        "memory.updated",
        source_kind="memory",
        source_id=memory_id,
        payload={
            "memory_id": memory_id,
            "cube_id": updated.get("cube_id"),
            "status": updated.get("status"),
            "changed_fields": sorted(k for k, value in changes.items() if value is not None),
        },
    )
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
        _record_lifecycle(
            memory_id,
            event_kind="deleted",
            from_status=current.get("status") or "active",
            to_status="deleted",
            actor=_actor(current.get("agent_id"), current.get("user_id")),
        )
        _audit("memory.deleted", memory_id, _actor(current.get("agent_id"), current.get("user_id")))
        emit_domain_event(
            "memory.deleted",
            source_kind="memory",
            source_id=memory_id,
            payload={"memory_id": memory_id, "cube_id": current.get("cube_id"), "status": "deleted"},
        )
    delete_item(memory_id)
    return {"deleted": existed, "memory_id": memory_id}


def list_memory_versions(memory_id: str, limit: int = 20) -> list[dict]:
    return memory_versions_repo().list_by_memory(memory_id, limit)


def list_memory_lifecycle_events(memory_id: str, limit: int = 50) -> list[dict]:
    return memory_lifecycle_events_repo().list_by_memory(memory_id, limit)


def list_audit_logs(limit: int = 100) -> list[dict]:
    return audit_logs_repo().list_recent(limit)
