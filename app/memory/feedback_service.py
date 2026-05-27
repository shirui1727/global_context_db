
from datetime import timezone, datetime
from hashlib import sha256
from typing import Any

from app.core.schemas import MemoryCreate, MemoryEvidenceCreate, MemoryFeedbackActionCreate, MemoryFeedbackCreate, MemoryUpdate
from app.memory.service import add_memory, add_memory_evidence, update_memory
from app.storage.repo import audit_logs_repo, memory_feedback_actions_repo, memory_feedback_repo, memories_repo

ACTION_TYPES = {"update", "archive", "add_evidence", "create_memory", "reject"}
FEEDBACK_STATUSES = {"pending", "planned", "applied", "rejected"}
ACTION_STATUSES = {"proposed", "pending", "applied", "rejected", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _audit(action: str, target_id: str, actor: str, metadata: dict[str, Any] | None = None) -> None:
    now = _now()
    audit_logs_repo().insert(
        {
            "id": _hash(f"{now}:{actor}:{action}:{target_id}"),
            "actor": actor,
            "action": action,
            "target_type": "memory_feedback",
            "target_id": target_id,
            "created_at": now,
            "metadata": metadata or {},
        }
    )


def _validate_action_type(action_type: str) -> str:
    if action_type not in ACTION_TYPES:
        raise ValueError(f"action_type must be one of: {', '.join(sorted(ACTION_TYPES))}")
    return action_type


def create_memory_feedback(payload: MemoryFeedbackCreate) -> dict:
    now = _now()
    feedback_id = _hash(f"feedback:{payload.cube_id or ''}:{payload.target_memory_id or ''}:{payload.feedback_text}:{now}")
    row = memory_feedback_repo().upsert(
        {
            "id": feedback_id,
            "cube_id": payload.cube_id,
            "feedback_text": payload.feedback_text,
            "target_memory_id": payload.target_memory_id,
            "status": "pending",
            "created_by": payload.created_by,
            "created_at": now,
            "updated_at": now,
            "metadata": payload.metadata,
        }
    )
    _audit("memory_feedback.created", feedback_id, payload.created_by or "memory_feedback", {"target_memory_id": payload.target_memory_id})
    return row


def list_memory_feedback(limit: int = 100, status: str | None = None, target_memory_id: str | None = None) -> list[dict]:
    return memory_feedback_repo().list_recent(limit=limit, status=status, target_memory_id=target_memory_id)


def add_memory_feedback_action(feedback_id: str, payload: MemoryFeedbackActionCreate) -> dict:
    feedback = memory_feedback_repo().get(feedback_id)
    if not feedback:
        raise ValueError("memory feedback not found")
    action_type = _validate_action_type(payload.action_type)
    now = _now()
    action_id = _hash(f"feedback-action:{feedback_id}:{action_type}:{payload.target_memory_id or ''}:{payload.payload}")
    row = memory_feedback_actions_repo().upsert(
        {
            "id": action_id,
            "feedback_id": feedback_id,
            "action_type": action_type,
            "target_memory_id": payload.target_memory_id,
            "payload": payload.payload,
            "status": "pending",
            "applied_at": None,
            "metadata": payload.metadata,
        }
    )
    if feedback["status"] == "pending":
        memory_feedback_repo().upsert({**feedback, "status": "planned", "updated_at": now})
    _audit("memory_feedback_action.created", feedback_id, feedback.get("created_by") or "memory_feedback", {"action_id": action_id, "action_type": action_type})
    return row


def list_memory_feedback_actions(feedback_id: str, limit: int = 100) -> list[dict]:
    if not memory_feedback_repo().get(feedback_id):
        raise ValueError("memory feedback not found")
    return memory_feedback_actions_repo().list_by_feedback(feedback_id, limit)


def propose_memory_feedback_actions(feedback_id: str, planner: str = "deterministic") -> dict:
    if planner != "deterministic":
        raise ValueError("only deterministic planner is available")
    feedback = memory_feedback_repo().get(feedback_id)
    if not feedback:
        raise ValueError("memory feedback not found")
    proposals = _plan_actions(feedback)
    actions = []
    for index, proposal in enumerate(proposals):
        action_id = _hash(f"feedback-action-proposal:{feedback_id}:{index}:{proposal['action_type']}:{proposal.get('payload')}")
        metadata = {
            **(proposal.get("metadata") or {}),
            "proposal": {
                "planner": planner,
                "mode": "deterministic",
                "requires_review": True,
                "proposal_index": index,
            },
        }
        actions.append(
            memory_feedback_actions_repo().upsert(
                {
                    "id": action_id,
                    "feedback_id": feedback_id,
                    "action_type": _validate_action_type(proposal["action_type"]),
                    "target_memory_id": proposal.get("target_memory_id") or feedback.get("target_memory_id"),
                    "payload": proposal.get("payload") or {},
                    "status": "proposed",
                    "applied_at": None,
                    "metadata": metadata,
                }
            )
        )
    now = _now()
    saved_feedback = memory_feedback_repo().upsert(
        {
            **feedback,
            "status": "planned" if actions else feedback["status"],
            "updated_at": now,
            "metadata": {
                **(feedback.get("metadata") or {}),
                "proposal": {"planner": planner, "mode": "deterministic", "proposed_count": len(actions), "updated_at": now},
            },
        }
    )
    _audit("memory_feedback.proposed_actions", feedback_id, feedback.get("created_by") or "memory_feedback", {"proposed_count": len(actions), "planner": planner})
    return {"feedback": saved_feedback, "actions": actions, "proposed_count": len(actions), "planner": {"mode": planner, "llm_used": False}}


def _plan_actions(feedback: dict) -> list[dict]:
    text = feedback.get("feedback_text") or ""
    lowered = text.lower()
    actions: list[dict[str, Any]] = []
    update_content = _extract_after_marker(text, ["update content to:", "correct content to:", "set content to:"])
    if update_content:
        actions.append(
            {
                "action_type": "update",
                "payload": {"content": update_content},
                "metadata": {"reason": "deterministic update marker"},
            }
        )
    if any(marker in lowered for marker in ["archive", "obsolete", "outdated", "deprecated"]):
        actions.append(
            {
                "action_type": "archive",
                "payload": {"reason": "obsolete" if "obsolete" in lowered else "outdated" if "outdated" in lowered else "feedback requested archive"},
                "metadata": {"reason": "deterministic archive marker"},
            }
        )
    evidence_quote = _extract_after_marker(text, ["evidence:", "source quote:", "quote:"])
    if evidence_quote:
        actions.append(
            {
                "action_type": "add_evidence",
                "payload": {
                    "source_domain": "feedback",
                    "source_id": feedback["id"],
                    "quote": evidence_quote,
                    "confidence": 0.9,
                },
                "metadata": {"reason": "deterministic evidence marker"},
            }
        )
    if not actions and feedback.get("target_memory_id"):
        actions.append(
            {
                "action_type": "add_evidence",
                "payload": {
                    "source_domain": "feedback",
                    "source_id": feedback["id"],
                    "quote": text,
                    "confidence": 0.7,
                },
                "metadata": {"reason": "fallback evidence proposal"},
            }
        )
    if not actions and not feedback.get("target_memory_id") and text.strip():
        actions.append(
            {
                "action_type": "create_memory",
                "payload": {
                    "content": text.strip(),
                    "cube_id": feedback.get("cube_id"),
                    "tags": ["feedback"],
                    "source_kind": "feedback_proposal",
                },
                "metadata": {"reason": "fallback create memory proposal"},
            }
        )
    return actions


def _extract_after_marker(text: str, markers: list[str]) -> str | None:
    lowered = text.lower()
    best: tuple[int, str] | None = None
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0 and (best is None or index < best[0]):
            best = (index, marker)
    if best is None:
        return None
    start = best[0] + len(best[1])
    tail = text[start:].strip()
    for separator in ["\n", "。", "；", ";"]:
        if separator in tail:
            tail = tail.split(separator, 1)[0].strip()
    return tail or None


def apply_memory_feedback(feedback_id: str, actor: str = "memory_feedback") -> dict:
    feedback = memory_feedback_repo().get(feedback_id)
    if not feedback:
        raise ValueError("memory feedback not found")
    actions = memory_feedback_actions_repo().list_by_feedback(feedback_id)
    applied = 0
    rejected = 0
    results: list[dict[str, Any]] = []
    now = _now()
    for action in actions:
        if action["status"] in {"applied", "rejected"}:
            results.append({"action": action, "skipped": True, "reason": f"already {action['status']}"})
            continue
        try:
            result = _apply_action(feedback, action, actor)
        except Exception as error:
            failed = memory_feedback_actions_repo().upsert({**action, "status": "failed", "metadata": {**action.get("metadata", {}), "error": str(error)}})
            results.append({"action": failed, "ok": False, "error": str(error)})
            raise
        status = "rejected" if action["action_type"] == "reject" else "applied"
        saved = memory_feedback_actions_repo().upsert({**action, "status": status, "applied_at": now, "metadata": {**action.get("metadata", {}), "result": result}})
        if status == "applied":
            applied += 1
        else:
            rejected += 1
        results.append({"action": saved, "ok": True, "result": result})
        _audit("memory_feedback_action.applied", feedback_id, actor, {"action_id": action["id"], "action_type": action["action_type"], "status": status})
    final_status = "rejected" if rejected and not applied else "applied" if applied or all(a["status"] in {"applied", "rejected"} for a in memory_feedback_actions_repo().list_by_feedback(feedback_id)) else feedback["status"]
    final_feedback = memory_feedback_repo().upsert({**feedback, "status": final_status, "updated_at": _now()})
    _audit("memory_feedback.applied", feedback_id, actor, {"applied": applied, "rejected": rejected})
    return {"feedback": final_feedback, "actions": results, "applied": applied, "rejected": rejected}


def _target_memory_id(feedback: dict, action: dict) -> str:
    memory_id = action.get("target_memory_id") or feedback.get("target_memory_id")
    if not memory_id:
        raise ValueError("target_memory_id is required for this feedback action")
    if memories_repo().get(memory_id) is None:
        raise ValueError("memory not found")
    return memory_id


def _apply_action(feedback: dict, action: dict, actor: str) -> dict:
    payload = action.get("payload") or {}
    action_type = action["action_type"]
    if action_type == "update":
        memory_id = _target_memory_id(feedback, action)
        update_payload = MemoryUpdate(**{key: value for key, value in payload.items() if key in MemoryUpdate.model_fields})
        return update_memory(memory_id, update_payload)
    if action_type == "archive":
        memory_id = _target_memory_id(feedback, action)
        current = memories_repo().get(memory_id)
        metadata = {**(current.get("metadata") or {}), "archived_by_feedback": feedback["id"], "archive_reason": payload.get("reason", "")}
        return update_memory(memory_id, MemoryUpdate(status="archived", metadata=metadata))
    if action_type == "add_evidence":
        memory_id = _target_memory_id(feedback, action)
        evidence_payload = MemoryEvidenceCreate(
            source_domain=payload.get("source_domain", "feedback"),
            source_id=payload.get("source_id", feedback["id"]),
            quote=payload.get("quote", feedback.get("feedback_text") or ""),
            confidence=payload.get("confidence", 1.0),
            metadata={**payload.get("metadata", {}), "feedback_id": feedback["id"], "applied_by": actor},
        )
        return add_memory_evidence(memory_id, evidence_payload)
    if action_type == "create_memory":
        memory_payload = MemoryCreate(
            content=payload["content"],
            cube_id=payload.get("cube_id") or feedback.get("cube_id"),
            tags=payload.get("tags", []),
            user_id=payload.get("user_id", "default"),
            agent_id=payload.get("agent_id"),
            session_id=payload.get("session_id"),
            conversation_id=payload.get("conversation_id"),
            memory_type=payload.get("memory_type", "long_term"),
            context_domain=payload.get("context_domain", "memory"),
            status=payload.get("status", "active"),
            source_kind=payload.get("source_kind", "feedback"),
            trust_level=payload.get("trust_level", "verified"),
            metadata={**payload.get("metadata", {}), "feedback_id": feedback["id"], "created_by_feedback": True},
        )
        return add_memory(memory_payload)
    if action_type == "reject":
        return {"status": "rejected", "reason": payload.get("reason", "")}
    raise ValueError(f"unsupported action_type: {action_type}")
