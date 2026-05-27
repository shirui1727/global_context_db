from datetime import UTC, datetime
from hashlib import sha256

from app.core.schemas import ImprovementTaskCreate, ImprovementTaskUpdate, ImproveRequest
from app.core.schemas import MemoryPromotionCreate, SessionSummaryCreate
from app.storage.repo import audit_logs_repo, improvement_tasks_repo
from app.storage.repo import session_events_repo

TASK_KINDS = {
    "rebuild_vectors",
    "summarize_session",
    "promote_session_memory",
    "refresh_asset_artifacts",
    "reindex_asset",
    "resolve_missing_asset",
    "verify_untrusted_memory",
    "verify_memory_evidence",
    "refresh_stale_memory",
    "resolve_memory_conflict",
    "cleanup_stale_vectors",
}
TASK_STATUSES = {"pending", "running", "done", "failed", "skipped"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _audit(action: str, target_id: str, actor: str, metadata: dict | None = None) -> None:
    now = _now()
    audit_logs_repo().insert(
        {
            "id": _hash(f"{now}:{actor}:{action}:{target_id}"),
            "actor": actor,
            "action": action,
            "target_type": "improvement_task",
            "target_id": target_id,
            "created_at": now,
            "metadata": metadata or {},
        }
    )


def _validate_task_kind(task_kind: str) -> str:
    if task_kind not in TASK_KINDS:
        raise ValueError(f"task_kind must be one of: {', '.join(sorted(TASK_KINDS))}")
    return task_kind


def _validate_status(status: str) -> str:
    if status not in TASK_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(TASK_STATUSES))}")
    return status


def create_improvement_task(payload: ImprovementTaskCreate) -> dict:
    now = _now()
    task_kind = _validate_task_kind(payload.task_kind)
    task_id = _hash(f"improvement:{task_kind}:{payload.target_domain}:{payload.target_id}")
    row = improvement_tasks_repo().upsert(
        {
            "id": task_id,
            "cube_id": payload.cube_id,
            "task_kind": task_kind,
            "target_domain": payload.target_domain,
            "target_id": payload.target_id,
            "status": "pending",
            "priority": payload.priority,
            "reason": payload.reason,
            "created_by": payload.created_by,
            "claimed_by": None,
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
            "error_message": None,
            "metadata": payload.metadata,
        }
    )
    _audit("improvement.created", row["id"], payload.created_by or "improvement_writer", {"task_kind": task_kind})
    return row


def list_improvement_tasks(
    limit: int = 100,
    status: str | None = None,
    task_kind: str | None = None,
    target_domain: str | None = None,
    target_id: str | None = None,
) -> list[dict]:
    return improvement_tasks_repo().list_recent(
        limit=limit,
        status=status,
        task_kind=task_kind,
        target_domain=target_domain,
        target_id=target_id,
    )


def update_improvement_task(task_id: str, payload: ImprovementTaskUpdate) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    now = _now()
    if "status" in changes and changes["status"] is not None:
        _validate_status(changes["status"])
        if changes["status"] in {"done", "failed", "skipped"}:
            changes.setdefault("finished_at", now)
    changes["updated_at"] = now
    updated = improvement_tasks_repo().update(task_id, changes)
    if not updated:
        raise ValueError("improvement task not found")
    _audit("improvement.updated", task_id, updated.get("claimed_by") or "improvement_writer", {"status": updated["status"]})
    return updated


def run_improve(payload: ImproveRequest) -> dict:
    task = create_improvement_task(
        ImprovementTaskCreate(
            task_kind=payload.task_kind,
            cube_id=payload.cube_id,
            target_domain=payload.target_domain,
            target_id=payload.target_id,
            priority=payload.priority,
            reason=payload.reason,
            created_by=payload.created_by,
            metadata=payload.metadata,
        )
    )
    if not payload.execute:
        return {"task": task, "executed": False}

    started = update_improvement_task(
        task["id"],
        ImprovementTaskUpdate(status="running", claimed_by=payload.created_by or "gcd_improve"),
    )
    try:
        result = _execute_task(started, payload)
    except Exception as error:
        failed = update_improvement_task(
            task["id"],
            ImprovementTaskUpdate(status="failed", error_message=str(error), claimed_by=payload.created_by or "gcd_improve"),
        )
        return {"task": failed, "executed": True, "ok": False, "error": str(error)}
    done = update_improvement_task(
        task["id"],
        ImprovementTaskUpdate(
            status="done",
            claimed_by=payload.created_by or "gcd_improve",
            metadata={**started.get("metadata", {}), "result": result},
        ),
    )
    return {"task": done, "executed": True, "ok": True, "result": result}


def _execute_task(task: dict, payload: ImproveRequest) -> dict:
    if task["task_kind"] in {"rebuild_vectors", "cleanup_stale_vectors"}:
        from app.assets.service import rebuild_asset_vectors

        return rebuild_asset_vectors(clean_legacy=payload.clean_legacy)
    if task["task_kind"] == "reindex_asset":
        from app.assets.service import execute_reindex_asset

        return execute_reindex_asset(task["target_id"], actor=payload.created_by or "gcd_improve")
    if task["task_kind"] == "summarize_session":
        return _execute_summarize_session(task, payload)
    if task["task_kind"] == "promote_session_memory":
        return _execute_promote_session_memory(task, payload)
    if task["task_kind"] in {
        "refresh_asset_artifacts",
        "resolve_missing_asset",
        "verify_untrusted_memory",
        "verify_memory_evidence",
        "refresh_stale_memory",
        "resolve_memory_conflict",
    }:
        return {"status": "skipped", "reason": "deterministic executor not implemented in v0.3 yet"}
    raise ValueError(f"unsupported task kind: {task['task_kind']}")


def _execute_summarize_session(task: dict, payload: ImproveRequest) -> dict:
    from app.sessions.service import add_session_summary, get_session

    if task["target_domain"] != "session":
        raise ValueError("summarize_session requires target_domain=session")
    session = get_session(task["target_id"])
    events = list(reversed(session_events_repo().list_by_session(session["id"], limit=8)))
    summary_text = _build_session_summary_text(session, events)
    summary = add_session_summary(
        session["id"],
        SessionSummaryCreate(
            summary_kind="improvement_summary",
            content=summary_text,
            created_by=payload.created_by or "gcd_improve",
            metadata={"improvement_task_id": task["id"]},
        ),
    )
    return {"summary": summary, "event_count": len(events)}


def _execute_promote_session_memory(task: dict, payload: ImproveRequest) -> dict:
    from app.memory.service import create_memory_promotion
    from app.sessions.service import get_session

    if task["target_domain"] != "session":
        raise ValueError("promote_session_memory requires target_domain=session")
    session = get_session(task["target_id"])
    events = list(reversed(session_events_repo().list_by_session(session["id"], limit=20)))
    candidates = [event for event in events if _is_promotable_event(event)]
    if not candidates:
        return {"status": "skipped", "reason": "no promotable session events found"}
    event = candidates[-1]
    proposal = create_memory_promotion(
        MemoryPromotionCreate(
            source_session_id=session["id"],
            cube_id=session.get("cube_id"),
            source_event_ids=[event["id"]],
            proposed_content=_promotion_content(event),
            tags=_promotion_tags(event, session),
            agent_id=session.get("source_agent"),
            project_path=session.get("project_path"),
            reason="deterministic promotion from session event",
            created_by=payload.created_by or "gcd_improve",
            metadata={"improvement_task_id": task["id"], "event_type": event.get("event_type")},
        )
    )
    return {"proposal": proposal, "event_id": event["id"]}


def _build_session_summary_text(session: dict, events: list[dict]) -> str:
    parts: list[str] = []
    if session.get("title"):
        parts.append(f"Session: {session['title']}")
    if session.get("summary"):
        parts.append(f"Summary: {session['summary']}")
    highlights = []
    for event in events:
        text = (event.get("content") or event.get("tool_result") or "").strip()
        if not text:
            continue
        normalized = " ".join(text.split())
        if normalized not in highlights:
            highlights.append(normalized)
        if len(highlights) >= 3:
            break
    if highlights:
        parts.append("Highlights: " + " | ".join(highlights))
    else:
        parts.append("Highlights: no notable session events recorded")
    return "\n".join(parts)


def _is_promotable_event(event: dict) -> bool:
    text = (event.get("content") or "").strip()
    if not text:
        return False
    event_type = event.get("event_type")
    if event_type not in {"assistant_note", "pre_compact", "session_end", "tool_result"}:
        return False
    lowered = f" {text.lower()} "
    markers = ["decision:", " rule:", " note:", " should ", " must ", " prefer ", " avoid "]
    return any(marker in lowered for marker in markers) or text.startswith("Decision:")


def _promotion_content(event: dict) -> str:
    content = (event.get("content") or "").strip()
    if content.lower().startswith("decision:"):
        return content.split(":", 1)[1].strip()
    return content


def _promotion_tags(event: dict, session: dict) -> list[str]:
    tags = ["session-promotion", event.get("event_type") or "session-event"]
    if session.get("source_agent"):
        tags.append(str(session["source_agent"]))
    return tags
