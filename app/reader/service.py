
from hashlib import sha256
import re
from typing import Any

from app.core.schemas import ReaderEvidence, ReaderEvidenceSpan, ReaderItem


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _provenance(source_domain: str, source_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"source_domain": source_domain, "source_id": source_id, **(extra or {})}


def _span(quote: str, *, start: int | None = 0, selector: str | None = None) -> ReaderEvidenceSpan:
    return ReaderEvidenceSpan(
        start=start,
        end=(start + len(quote)) if start is not None else None,
        quote_hash=_hash(quote) if quote else None,
        selector=selector,
    )


def _evidence(
    *,
    source_domain: str,
    source_id: str,
    quote: str,
    confidence: float = 1.0,
    start: int | None = 0,
    metadata: dict[str, Any] | None = None,
) -> list[ReaderEvidence]:
    if not quote:
        return []
    return [
        ReaderEvidence(
            source_domain=source_domain,
            source_id=source_id,
            quote=quote,
            confidence=confidence,
            source_span=_span(quote, start=start),
            metadata=metadata or {},
        )
    ]


def _reader_metadata(item_metadata: dict[str, Any] | None, *, source: str | None = None, evidence_count: int = 0) -> dict[str, Any]:
    metadata = dict(item_metadata or {})
    if source is not None:
        metadata["source"] = source
    metadata["reader"] = {
        **(metadata.get("reader") if isinstance(metadata.get("reader"), dict) else {}),
        "mode": "fast",
        "evidence_count": evidence_count,
        "span_schema": "char@v1",
    }
    return metadata


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


FINE_MARKERS: dict[str, str] = {
    "decision": "Decision",
    "preference": "Preference",
    "todo": "Todo",
    "fact": "Fact",
    "insight": "Insight",
    "warning": "Warning",
}


def _fine_candidates(text: str, source_domain: str, source_id: str) -> tuple[list[dict[str, Any]], list[ReaderEvidence]]:
    candidates: list[dict[str, Any]] = []
    evidence_items: list[ReaderEvidence] = []
    marker_pattern = "|".join(re.escape(marker) for marker in FINE_MARKERS.values())
    pattern = re.compile(rf"(?im)^\s*(?P<label>{marker_pattern})\s*:\s*(?P<quote>.+?)\s*$")
    for match in pattern.finditer(text):
        label = match.group("label").lower()
        memory_type = next((key for key, marker in FINE_MARKERS.items() if marker.lower() == label), "fact")
        quote = match.group("quote").strip()
        if not quote:
            continue
        start = match.start("label")
        evidence = ReaderEvidence(
            source_domain=source_domain,
            source_id=source_id,
            quote=quote,
            confidence=0.92,
            source_span=_span(quote, start=start),
            metadata={
                "fine_marker": label,
                "extractor": "deterministic_marker_v1",
                "hallucination_filter": "source_quote_exact_match",
            },
        )
        evidence_items.append(evidence)
        candidates.append(
            {
                "memory_type": memory_type,
                "content": quote,
                "confidence": evidence.confidence,
                "tags": [f"fine:{memory_type}"],
                "evidence_index": len(evidence_items) - 1,
                "quality": {
                    "hallucination_risk": "low",
                    "source_quote_exact_match": quote in text,
                    "extractor": "deterministic_marker_v1",
                },
            }
        )
    return candidates, evidence_items


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
    evidence = _evidence(source_domain="document", source_id=source_id, quote=text)
    return ReaderItem(
        source_domain="document",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind=content_kind,
        tags=_tags(tags),
        confidence=1.0,
        provenance=_provenance("document", source_id, {"source": source}),
        evidence=evidence,
        metadata=_reader_metadata(metadata, source=source, evidence_count=len(evidence)),
    )


def read_text_fine(
    *,
    source: str,
    text: str,
    cube_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReaderItem:
    source_id = _hash(f"fine_document:{source}:{text}")
    candidates, evidence = _fine_candidates(text, "document", source_id)
    fine_tags = _tags(tags, ["reader_fine"], ["candidate"] if candidates else ["no_candidate"])
    metadata_base = _reader_metadata(metadata, source=source, evidence_count=len(evidence))
    return ReaderItem(
        source_domain="document",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind="fine_candidates",
        tags=fine_tags,
        confidence=0.9 if candidates else 0.4,
        provenance=_provenance("document", source_id, {"source": source, "reader_mode": "fine"}),
        evidence=evidence,
        metadata={
            **metadata_base,
            "reader": {
                **(metadata_base.get("reader") or {}),
                "mode": "fine",
                "llm_required": False,
                "candidate_count": len(candidates),
                "extractor": "deterministic_marker_v1",
            },
            "quality": {
                "hallucination_filter": "deterministic_source_quote",
                "source_quote_required": True,
                "llm_used": False,
            },
            "fine_candidates": candidates,
        },
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
    quote = content or tool_result or text
    start = text.index(quote) if quote and quote in text else 0
    evidence = _evidence(source_domain="session_event", source_id=source_id, quote=quote, start=start)
    return ReaderItem(
        source_domain="session_event",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind="trace",
        tags=_tags([event_type, role or "session"]),
        confidence=1.0,
        provenance=_provenance("session_event", source_id, {"session_id": session_id, "event_type": event_type}),
        evidence=evidence,
        metadata=_reader_metadata(
            {**(metadata or {}), "session_id": session_id, "event_type": event_type, "role": role, "tool_name": tool_name},
            evidence_count=len(evidence),
        ),
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
    quote = artifact_text or summary or title or uri or text
    start = text.index(quote) if quote and quote in text else 0
    evidence = _evidence(source_domain="asset", source_id=source_id, quote=quote, start=start)
    return ReaderItem(
        source_domain="asset",
        source_id=source_id,
        cube_id=cube_id,
        content=text,
        content_kind="artifact_text",
        tags=_tags(tags, [asset_kind or "asset"]),
        confidence=1.0,
        provenance=_provenance("asset", source_id, {"asset_id": asset_id, "asset_key": asset_key, "artifact_id": artifact_id}),
        evidence=evidence,
        metadata={
            **_reader_metadata(metadata, evidence_count=len(evidence)),
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
    quote = feedback_text or error_message or memory_context or memory_query or str(method_return_value or "") or text
    start = text.index(quote) if quote and quote in text else 0
    evidence = _evidence(source_domain="tool_trace", source_id=trace_id, quote=quote, start=start)
    return ReaderItem(
        source_domain="tool_trace",
        source_id=trace_id,
        cube_id=cube_id,
        content=text,
        content_kind="trace",
        tags=_tags(["tool_trace", origin_function, status]),
        confidence=1.0,
        provenance=_provenance("tool_trace", trace_id, {"origin_function": origin_function, "status": status}),
        evidence=evidence,
        metadata=_reader_metadata(
            {**(metadata or {}), "trace_id": trace_id, "origin_function": origin_function, "status": status},
            evidence_count=len(evidence),
        ),
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
        "evidence": [evidence.model_dump() for evidence in item.evidence],
        "created_by": created_by,
        "metadata": {
            **item.metadata,
            "reader": {
                **(item.metadata.get("reader") if isinstance(item.metadata.get("reader"), dict) else {}),
                "source_domain": source_domain,
                "source_id": source_id,
                "evidence_count": len(item.evidence),
            },
            **(metadata or {}),
        },
        "promoted_memory_id": None,
    }
