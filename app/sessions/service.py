from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from app.core.schemas import (
    ResumeContextRequest,
    SessionCreate,
    SessionEventCreate,
    SessionModelUsageCreate,
    SessionSummaryCreate,
    SessionTraceCreate,
    SessionUpdate,
)
from app.memory.service import search_memory
from app.retrieval.service import search_context
from app.storage.repo import (
    agent_sessions_repo,
    audit_logs_repo,
    improvement_tasks_repo,
    session_events_repo,
    session_model_usage_repo,
    session_summaries_repo,
    session_traces_repo,
)
from app.storage.vector_store import upsert_items
from app.retrieval.embedding import embed_text

SESSION_STATUSES = {"running", "paused", "ended", "failed", "archived"}
EVENT_TYPES = {
    "session_start",
    "user_prompt",
    "assistant_note",
    "tool_call",
    "tool_result",
    "pre_compact",
    "session_end",
    "system",
}
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
    "x_api_key",
    "x-api-key",
}
REDACTED = "[REDACTED]"


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
            "target_type": "session",
            "target_id": target_id,
            "created_at": now,
            "metadata": metadata or {},
        }
    )


def _validate_status(status: str) -> str:
    if status not in SESSION_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(SESSION_STATUSES))}")
    return status


def _validate_event_type(event_type: str) -> str:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of: {', '.join(sorted(EVENT_TYPES))}")
    return event_type


def create_session(payload: SessionCreate) -> dict:
    now = _now()
    status = _validate_status(payload.status)
    session_id = payload.id or _hash(f"session:{payload.source_agent}:{payload.project_path or ''}:{now}")
    row = {
        "id": session_id,
        "source_agent": payload.source_agent,
        "project_path": payload.project_path,
        "status": status,
        "title": payload.title,
        "summary": payload.summary,
        "started_at": now,
        "last_activity_at": now,
        "ended_at": None,
        "created_by": payload.created_by or payload.source_agent,
        "metadata": payload.metadata,
    }
    agent_sessions_repo().upsert(row)
    _audit("session.created", session_id, payload.created_by or payload.source_agent, {"project_path": payload.project_path})
    add_session_event(
        session_id,
        SessionEventCreate(
            event_type="session_start",
            role="system",
            content=payload.summary or payload.title or "session started",
            created_at=now,
            metadata={"source_agent": payload.source_agent, "project_path": payload.project_path},
        ),
    )
    return get_session(session_id)


def get_session(session_id: str) -> dict:
    session = agent_sessions_repo().get(session_id)
    if not session:
        raise ValueError("session not found")
    return {
        **session,
        "summaries": session_summaries_repo().list_by_session(session_id),
        "model_usage": session_model_usage_repo().list_by_session(session_id),
    }


def list_sessions(
    limit: int = 100,
    status: str | None = None,
    source_agent: str | None = None,
    project_path: str | None = None,
) -> list[dict]:
    return agent_sessions_repo().list_recent(limit, status=status, source_agent=source_agent, project_path=project_path)


def update_session(session_id: str, payload: SessionUpdate) -> dict:
    current = agent_sessions_repo().get(session_id)
    if not current:
        raise ValueError("session not found")
    now = _now()
    changes = payload.model_dump(exclude_unset=True)
    status = _validate_status(changes.get("status") or current["status"])
    ended_at = changes.get("ended_at")
    if status in {"ended", "failed", "archived"} and not ended_at:
        ended_at = now
    updated = {
        **current,
        **{key: value for key, value in changes.items() if value is not None and key != "metadata"},
        "status": status,
        "ended_at": ended_at,
        "last_activity_at": now,
        "metadata": changes.get("metadata") if changes.get("metadata") is not None else current.get("metadata", {}),
    }
    agent_sessions_repo().upsert(updated)
    _audit("session.updated", session_id, updated.get("created_by") or "session_writer", {"status": status})
    if status in {"ended", "failed", "archived"}:
        add_session_event(
            session_id,
            SessionEventCreate(event_type="session_end", role="system", content=f"session {status}", created_at=now),
        )
    return get_session(session_id)


def add_session_event(session_id: str, payload: SessionEventCreate) -> dict:
    session = agent_sessions_repo().get(session_id)
    if not session:
        raise ValueError("session not found")
    created_at = payload.created_at or _now()
    event_type = _validate_event_type(payload.event_type)
    event_id = _hash(f"event:{session_id}:{event_type}:{created_at}:{payload.content}:{payload.tool_name or ''}")
    row = {
        "id": event_id,
        "session_id": session_id,
        "event_type": event_type,
        "role": payload.role,
        "content": _sanitize_text(payload.content),
        "tool_name": payload.tool_name,
        "tool_args": _sanitize_value(payload.tool_args),
        "tool_result": _sanitize_text(payload.tool_result),
        "created_at": created_at,
        "metadata": _sanitize_value(payload.metadata),
    }
    session_events_repo().insert(row)
    agent_sessions_repo().touch(session_id, created_at)
    _upsert_session_event_vector(row, session)
    return row


def _upsert_session_event_vector(row: dict, session: dict) -> None:
    text_parts = [
        row.get("event_type") or "",
        row.get("role") or "",
        row.get("content") or "",
        row.get("tool_name") or "",
        row.get("tool_result") or "",
        session.get("project_path") or "",
    ]
    text = "\n".join(part for part in text_parts if part)
    if not text.strip():
        return
    upsert_items(
        [
            {
                "id": row["id"],
                "kind": "session_event",
                "text": text,
                "vector": embed_text(text).tolist(),
                "source": session.get("project_path") or "",
                "doc_id": session["id"],
                "chunk_index": 0,
                "tags": [row.get("event_type") or "session"],
                "session_id": session["id"],
                "context_domain": "session",
                "status": session.get("status") or "running",
                "source_kind": "agent_session",
                "trust_level": "unverified",
                "metadata": {
                    "domain": "session",
                    "session_id": session["id"],
                    "event_type": row.get("event_type"),
                    "project_path": session.get("project_path"),
                    "source_agent": session.get("source_agent"),
                },
            }
        ]
    )


def list_session_events(session_id: str, limit: int = 100) -> list[dict]:
    if not agent_sessions_repo().get(session_id):
        raise ValueError("session not found")
    return session_events_repo().list_by_session(session_id, limit)


def add_session_trace(session_id: str, payload: SessionTraceCreate) -> dict:
    session = agent_sessions_repo().get(session_id)
    if not session:
        raise ValueError("session not found")
    created_at = payload.created_at or _now()
    trace_id = payload.trace_id or _hash(f"trace:{session_id}:{payload.origin_function}:{created_at}")
    row = {
        "id": _hash(f"session_trace:{session_id}:{trace_id}"),
        "session_id": session_id,
        "trace_id": trace_id,
        "origin_function": payload.origin_function,
        "status": payload.status,
        "memory_query": _sanitize_text(payload.memory_query),
        "memory_context": _sanitize_text(payload.memory_context),
        "method_params": _sanitize_value(payload.method_params),
        "method_return_value": _sanitize_value(payload.method_return_value),
        "error_message": _sanitize_text(payload.error_message),
        "feedback_text": _sanitize_text(payload.feedback_text),
        "created_at": created_at,
        "metadata": _sanitize_value(payload.metadata),
    }
    session_traces_repo().insert(row)
    agent_sessions_repo().touch(session_id, created_at)
    add_session_event(
        session_id,
        SessionEventCreate(
            event_type="tool_result" if payload.status == "ok" else "tool_call",
            role="tool",
            content=_sanitize_text(payload.feedback_text or payload.error_message or payload.origin_function),
            tool_name=payload.origin_function,
            tool_args=_sanitize_value(payload.method_params),
            tool_result=_sanitize_text(str(payload.method_return_value)) if payload.method_return_value is not None else None,
            created_at=created_at,
            metadata={"trace_id": trace_id, "trace_status": payload.status},
        ),
    )
    return row


def list_session_traces(session_id: str, limit: int = 100) -> list[dict]:
    if not agent_sessions_repo().get(session_id):
        raise ValueError("session not found")
    return session_traces_repo().list_by_session(session_id, limit)


def add_session_summary(session_id: str, payload: SessionSummaryCreate) -> dict:
    if not agent_sessions_repo().get(session_id):
        raise ValueError("session not found")
    created_at = _now()
    row = {
        "id": _hash(f"summary:{session_id}:{payload.summary_kind}:{created_at}"),
        "session_id": session_id,
        "summary_kind": payload.summary_kind,
        "content": payload.content,
        "status": payload.status,
        "created_by": payload.created_by,
        "created_at": created_at,
        "metadata": payload.metadata,
    }
    session_summaries_repo().upsert(row)
    return row


def add_session_model_usage(session_id: str, payload: SessionModelUsageCreate) -> dict:
    if not agent_sessions_repo().get(session_id):
        raise ValueError("session not found")
    updated_at = _now()
    row = {
        "id": _hash(f"model_usage:{session_id}:{payload.model}"),
        "session_id": session_id,
        "model": payload.model,
        "tokens_in": payload.tokens_in,
        "tokens_out": payload.tokens_out,
        "cost_usd": payload.cost_usd,
        "updated_at": updated_at,
        "metadata": payload.metadata,
    }
    session_model_usage_repo().upsert(row)
    return row


def get_resume_context(payload: ResumeContextRequest) -> dict:
    session = None
    if payload.session_id:
        if not agent_sessions_repo().get(payload.session_id):
            raise ValueError("session not found")
        session = get_session(payload.session_id)
    project_path = payload.project_path or (session.get("project_path") if session else None)
    query = payload.query or (session.get("summary") if session else None) or project_path or ""
    recent_events = session_events_repo().list_by_session(session["id"], payload.recent_events_limit) if session else []
    open_tasks = improvement_tasks_repo().list_recent(
        limit=20,
        status="pending",
        target_domain="session" if session else None,
        target_id=session["id"] if session else None,
    )
    memories = search_memory(query, payload.top_k)["results"] if query else []
    context = search_context(query, payload.top_k, mode="context_search") if query else {"groups": {"asset": [], "document": [], "memory": []}}
    groups = context.get("groups") or {}
    ordered_events = list(reversed(recent_events))
    handoff = _build_handoff(session, ordered_events, open_tasks)
    response = {
        "project_path": project_path,
        "session": session,
        "handoff": handoff,
        "recent_events": ordered_events if payload.include_raw_events and payload.format != "brief" else [],
        "open_tasks": open_tasks,
        "relevant_memories": memories,
        "relevant_assets": groups.get("asset", []),
        "relevant_documents": groups.get("document", []),
        "warnings": [] if query else ["resume context has no query, project_path, or session summary"],
    }
    return _apply_context_budget(response, payload.context_budget_chars)


def _build_handoff(session: dict | None, events: list[dict], open_tasks: list[dict]) -> dict[str, Any]:
    user_events = [event for event in events if event.get("event_type") == "user_prompt"]
    progress_events = [
        event
        for event in events
        if event.get("event_type") in {"assistant_note", "tool_result", "pre_compact", "session_end"}
        and (event.get("content") or event.get("tool_result"))
    ]
    failed_events = [
        event
        for event in events
        if "failed" in (event.get("content") or "").lower()
        or "error" in (event.get("content") or "").lower()
        or (event.get("metadata") or {}).get("trace_status") not in {None, "ok"}
    ]
    tools_used = []
    for event in events:
        tool_name = event.get("tool_name")
        if tool_name and tool_name not in tools_used:
            tools_used.append(tool_name)
    current_focus = (
        (user_events[-1].get("content") if user_events else None)
        or (session or {}).get("summary")
        or (session or {}).get("title")
        or ""
    )
    recent_progress = [
        _compact_event_text(event)
        for event in progress_events[-6:]
        if _compact_event_text(event)
    ]
    next_steps = [
        task.get("reason") or f"{task.get('task_kind')}:{task.get('target_domain')}/{task.get('target_id')}"
        for task in open_tasks[:8]
    ]
    risks = [
        _compact_event_text(event)
        for event in failed_events[-5:]
        if _compact_event_text(event)
    ]
    return {
        "status": (session or {}).get("status"),
        "title": (session or {}).get("title"),
        "current_focus": current_focus,
        "recent_progress": recent_progress,
        "next_steps": next_steps,
        "risks": risks,
        "tools_used": tools_used,
        "open_task_count": len(open_tasks),
    }


def _compact_event_text(event: dict) -> str:
    content = event.get("content") or event.get("tool_result") or event.get("tool_name") or ""
    text = " ".join(str(content).split())
    if len(text) > 280:
        return text[:277] + "..."
    return text


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                sanitized[key] = REDACTED
            else:
                sanitized[key] = _sanitize_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    for marker in ("api_key=", "api-key=", "authorization:", "bearer ", "token=", "password=", "secret="):
        lower = text.lower()
        index = lower.find(marker)
        while index != -1:
            end = index + len(marker)
            while end < len(text) and not text[end].isspace() and text[end] not in {",", ";", "&"}:
                end += 1
            text = text[: index + len(marker)] + REDACTED + text[end:]
            lower = text.lower()
            index = lower.find(marker, index + len(marker) + len(REDACTED))
    return text


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(part in normalized for part in ("api_key", "authorization", "password", "secret", "token"))


def _apply_context_budget(response: dict, budget: int) -> dict:
    remaining = max(budget, 1000)
    trimmed = {**response, "budget": {"requested_chars": budget, "truncated": False}}

    def take_text(text: str) -> str:
        nonlocal remaining
        if len(text) <= remaining:
            remaining -= len(text)
            return text
        trimmed["budget"]["truncated"] = True
        if remaining <= 0:
            return ""
        allowed = remaining
        remaining = 0
        return text[: max(0, allowed - 3)] + "..."

    handoff = dict(trimmed.get("handoff") or {})
    handoff["current_focus"] = take_text(str(handoff.get("current_focus") or ""))
    handoff["recent_progress"] = [take_text(str(item)) for item in handoff.get("recent_progress", []) if remaining > 0]
    handoff["next_steps"] = [take_text(str(item)) for item in handoff.get("next_steps", []) if remaining > 0]
    handoff["risks"] = [take_text(str(item)) for item in handoff.get("risks", []) if remaining > 0]
    trimmed["handoff"] = handoff

    for key in ("recent_events", "open_tasks", "relevant_memories", "relevant_assets", "relevant_documents"):
        items = []
        for item in trimmed.get(key, []):
            if remaining <= 0:
                trimmed["budget"]["truncated"] = True
                break
            items.append(_trim_item(item, take_text))
        trimmed[key] = items
    trimmed["budget"]["remaining_chars"] = remaining
    return trimmed


def _trim_item(item: Any, take_text) -> Any:
    if isinstance(item, dict):
        trimmed = {}
        for key, value in item.items():
            if isinstance(value, str) and key in {"content", "text", "summary", "tool_result", "reason"}:
                trimmed[key] = take_text(value)
            elif isinstance(value, dict):
                trimmed[key] = _trim_item(value, take_text)
            elif isinstance(value, list):
                trimmed[key] = [_trim_item(child, take_text) for child in value]
            else:
                trimmed[key] = value
        return trimmed
    if isinstance(item, str):
        return take_text(item)
    return item
