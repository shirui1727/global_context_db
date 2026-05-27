
from pathlib import Path

import pytest

from app.assets.service import create_asset
from app.control.service import remember
from app.core.config import settings
from app.core.schemas import AssetCreate, IngestRequest, RememberRequest, SessionCreate, SessionEventCreate
from app.cubes.service import create_cube
from app.core.schemas import ContextCubeCreate
from app.ingest.pipeline import ingest_text
from app.reader.service import (
    ReaderItem,
    read_asset_manifest_fast,
    read_session_event_fast,
    read_text_fast,
    read_tool_trace_fast,
)
from app.retrieval.service import search_context
from app.sessions.service import add_session_event, create_session
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.memory.service import (
    create_memory_candidate_from_reader,
    list_memory_evidence,
    promote_memory_candidate,
)


@pytest.fixture()
def reader_env(tmp_path: Path):
    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
        "asset_allow_prefixes": settings.asset_allow_prefixes,
        "asset_deny_prefixes": settings.asset_deny_prefixes,
    }
    settings.data_dir = tmp_path / "data"
    settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
    settings.lancedb_dir = settings.data_dir / "lancedb"
    settings.asset_allow_prefixes = ""
    settings.asset_deny_prefixes = ""
    reset_bootstrap()
    bootstrap(settings)
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_reader_fast_modes_emit_standard_items(reader_env):
    cube = create_cube(ContextCubeCreate(name="Reader Project", cube_type="project", owner_id="reader"))

    text_item = read_text_fast(
        source="manual-note",
        text="Reader fast mode normalizes plain notes.",
        cube_id=cube["id"],
        tags=["reader"],
        metadata={"origin": "test"},
    )
    session_item = read_session_event_fast(
        session_id="session-1",
        event_type="user_prompt",
        content="User asked to preserve provenance.",
        cube_id=cube["id"],
        role="user",
        metadata={"turn": 1},
    )
    asset_item = read_asset_manifest_fast(
        asset_id="asset-1",
        asset_key="asset:key",
        summary="Architectural image reference summary.",
        uri="smb://NAS/ref.png",
        cube_id=cube["id"],
        tags=["asset"],
        metadata={"media_type": "image/png"},
    )
    trace_item = read_tool_trace_fast(
        trace_id="trace-1",
        origin_function="search",
        status="ok",
        memory_query="reader provenance",
        memory_context="found relevant context",
        cube_id=cube["id"],
        metadata={"latency_ms": 12},
    )

    for item in [text_item, session_item, asset_item, trace_item]:
        assert isinstance(item, ReaderItem)
        assert item.cube_id == cube["id"]
        assert item.confidence == 1.0
        assert item.content.strip()
        assert item.provenance["source_domain"] == item.source_domain
        assert item.provenance["source_id"] == item.source_id

    assert text_item.source_domain == "document"
    assert text_item.content_kind == "note"
    assert text_item.tags == ["reader"]
    assert text_item.metadata["origin"] == "test"
    assert session_item.source_domain == "session_event"
    assert session_item.content_kind == "trace"
    assert "user_prompt" in session_item.tags
    assert asset_item.source_domain == "asset"
    assert asset_item.content_kind == "artifact_text"
    assert "asset:key" in asset_item.content
    assert trace_item.source_domain == "tool_trace"
    assert trace_item.content_kind == "trace"
    assert "search" in trace_item.content


def test_reader_fast_modes_emit_evidence_spans(reader_env):
    text = "Reader span evidence pins the exact quote."
    text_item = read_text_fast(source="manual-note", text=text, metadata={"origin": "span-test"})
    session_item = read_session_event_fast(
        session_id="session-span",
        event_type="user_prompt",
        content="Please preserve this exact session quote.",
        role="user",
        event_id="event-span-1",
    )

    assert text_item.evidence[0].source_domain == "document"
    assert text_item.evidence[0].source_id == text_item.source_id
    assert text_item.evidence[0].quote == text
    assert text_item.evidence[0].source_span is not None
    assert text_item.evidence[0].source_span.start == 0
    assert text_item.evidence[0].source_span.end == len(text)
    assert text_item.evidence[0].source_span.quote_hash
    assert text_item.metadata["reader"]["evidence_count"] == 1

    session_evidence = session_item.evidence[0]
    assert session_evidence.source_domain == "session_event"
    assert session_evidence.source_id == "event-span-1"
    assert session_evidence.quote == "Please preserve this exact session quote."
    assert session_evidence.source_span.start == session_item.content.index(session_evidence.quote)
    assert session_evidence.source_span.end == session_evidence.source_span.start + len(session_evidence.quote)


def test_reader_candidate_promotion_persists_evidence_span(reader_env):
    reader_item = read_text_fast(
        source="candidate-source",
        text="Candidate promotion should preserve source-span evidence.",
        cube_id="cube-span",
        tags=["candidate", "span"],
    )

    candidate = create_memory_candidate_from_reader(reader_item, created_by="reader-test")
    promoted = promote_memory_candidate(candidate["id"], reviewed_by="reviewer")
    evidence = list_memory_evidence(promoted["memory_id"])

    assert candidate["evidence"][0]["quote"] == "Candidate promotion should preserve source-span evidence."
    assert candidate["metadata"]["reader"]["evidence_count"] == 1
    assert evidence[0]["source_domain"] == "document"
    assert evidence[0]["quote"] == "Candidate promotion should preserve source-span evidence."
    assert evidence[0]["source_span"]["start"] == 0
    assert evidence[0]["source_span"]["end"] == len(evidence[0]["quote"])


def test_reader_integration_tags_vectors_with_reader_metadata(reader_env):
    cube = create_cube(ContextCubeCreate(name="Reader Integration", cube_type="project", owner_id="reader-int"))

    memory_result = remember(
        RememberRequest(
            content_type="memory",
            content="Reader integration memory keeps provenance marker.",
            source="manual",
            cube_id=cube["id"],
            tags=["integration"],
            agent_id="codex",
            metadata={"case": "memory"},
        )
    )["result"]
    document_result = ingest_text(
        IngestRequest(
            source="reader-doc",
            text="Reader integration document chunk keeps provenance marker.",
            cube_id=cube["id"],
        )
    )
    session = create_session(
        SessionCreate(
            cube_id=cube["id"],
            source_agent="codex",
            project_path="S:/reader-int",
            title="Reader integration session",
        )
    )
    event = add_session_event(
        session["id"],
        SessionEventCreate(
            event_type="assistant_note",
            role="assistant",
            content="Reader integration session event keeps provenance marker.",
        ),
    )
    asset = create_asset(
        AssetCreate(
            cube_id=cube["id"],
            uri="smb://NAS/reader/ref.png",
            asset_key="reader:ref",
            checksum="reader-ref-sha",
            summary="Reader integration asset keeps provenance marker.",
        )
    )

    result = search_context("Reader integration provenance marker", top_k=20, cube_id=cube["id"])
    items = [item for group in result["groups"].values() for item in group]
    by_id = {item["id"]: item for item in items}

    assert memory_result["memory_id"] in by_id
    assert by_id[memory_result["memory_id"]]["metadata"]["reader"]["source_domain"] == "memory"
    assert any(
        item["doc_id"] == document_result["document_id"]
        and item["metadata"]["reader"]["source_domain"] == "document"
        for item in items
    )
    assert event["id"] in by_id
    assert by_id[event["id"]]["metadata"]["reader"]["source_domain"] == "session_event"
    assert asset["id"] in by_id
    assert by_id[asset["id"]]["metadata"]["reader"]["source_domain"] == "asset"
