
from hashlib import sha256
from typing import Any

from app.core.schemas import ReaderItem


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _provenance(source_domain: str, source_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"source_domain": source_domain, "source_id": source_id, **(extra or {})}


def _tags(*groups: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for item in group or []:
            tag = str(item).strip()
            if tag and tag not in seen:
                seen.add(tag)
                result.append(tag)
    return result


def read_text_fast(
    *,
    source: str,
    text: str,
    cube_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    content_kind: str = "note",
) -> ReaderItem:
    source_id = _hash(f"document:{source}:{text}")
    return ReaderItem(
        source_domain="document",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind=content_kind,
        tags=_tags(tags),
        confidence=1.0,
        provenance=_provenance("document", source_id, {"source": source}),
        metadata={**(metadata or {}), "source": source},
    )


def read_session_event_fast(
    *,
    session_id: str,
    event_type: str,
    content: str = "",
    cube_id: str | None = None,
    role: str | None = None,
    tool_name: str | None = None,
    tool_result: str | None = None,
    event_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReaderItem:
    source_id = event_id or _hash(f"session_event:{session_id}:{event_type}:{role or ''}:{content}:{tool_name or ''}")
    parts = [event_type, role or "", content, tool_name or "", tool_result or ""]
    text = "\n".join(part for part in parts if part)
    return ReaderItem(
        source_domain="session_event",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind="trace",
        tags=_tags([event_type, role or "session"]),
        confidence=1.0,
        provenance=_provenance("session_event", source_id, {"session_id": session_id, "event_type": event_type}),
        metadata={**(metadata or {}), "session_id": session_id, "event_type": event_type, "role": role, "tool_name": tool_name},
    )


def read_asset_manifest_fast(
    *,
    asset_id: str,
    asset_key: str | None = None,
    summary: str = "",
    uri: str | None = None,
    cube_id: str | None = None,
    tags: list[str] | None = None,
    title: str | None = None,
    asset_kind: str | None = None,
    media_type: str | None = None,
    artifact_text: str | None = None,
    artifact_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReaderItem:
    source_id = artifact_id or asset_id
    parts = [title or "", asset_key or "", asset_kind or "", media_type or "", summary or "", artifact_text or "", uri or ""]
    text = "\n".join(part for part in parts if part)
    return ReaderItem(
        source_domain="asset",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind="artifact_text",
        tags=_tags(tags, [asset_kind or "asset"]),
        confidence=1.0,
        provenance=_provenance("asset", source_id, {"asset_id": asset_id, "asset_key": asset_key, "artifact_id": artifact_id}),
        metadata={
            **(metadata or {}),
            "asset_id": asset_id,
            "asset_key": asset_key,
            "asset_kind": asset_kind,
            "media_type": media_type,
            "uri": uri,
            "artifact_id": artifact_id,
        },
    )


def read_tool_trace_fast(
    *,
    trace_id: str,
    origin_function: str,
    status: str = "ok",
    memory_query: str = "",
    memory_context: str = "",
    method_return_value: Any = None,
    error_message: str = "",
    feedback_text: str = "",
    cube_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReaderItem:
    parts = [origin_function, status, memory_query, memory_context, str(method_return_value or ""), error_message, feedback_text]
    text = "\n".join(part for part in parts if part)
    return ReaderItem(
        source_domain="tool_trace",
        source_id=trace_id,
        cube_id=cube_id,
        content=text,
        content_kind="trace",
        tags=_tags(["tool_trace", origin_function, status]),
        confidence=1.0,
        provenance=_provenance("tool_trace", trace_id, {"origin_function": origin_function, "status": status}),
        metadata={**(metadata or {}), "trace_id": trace_id, "origin_function": origin_function, "status": status},
    )


def reader_item_to_memory_candidate(
    item: ReaderItem,
    *,
    status: str = "candidate",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_domain = item.metadata.get("source_domain") or item.provenance.get("source_domain") or item.source_domain
    source_id = item.metadata.get("source_id") or item.provenance.get("source_id") or item.source_id
    candidate_id = _hash(f"memory_candidate:{item.cube_id or ''}:{source_domain}:{source_id}:{item.content}")
    return {
        "id": candidate_id,
        "cube_id": item.cube_id,
        "source_domain": source_domain,
        "source_id": source_id,
        "content": item.content,
        "content_kind": item.content_kind,
        "tags": item.tags,
        "status": status,
        "confidence": item.confidence,
        "provenance": item.provenance,
        "created_by": created_by,
        "metadata": {**item.metadata, **(metadata or {})},
        "promoted_memory_id": None,
    }
