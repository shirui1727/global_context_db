from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.schemas import MemoryCreate, MemoryEvidenceCreate, ReaderItem
from app.main import app
from app.memory.service import add_memory, add_memory_evidence
from app.storage.bootstrap import bootstrap, reset_bootstrap


@pytest.fixture()
def memory_surface_env(tmp_path: Path):
    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
        "asset_allow_prefixes": settings.asset_allow_prefixes,
        "asset_deny_prefixes": settings.asset_deny_prefixes,
        "api_key": settings.api_key,
        "require_mcp_api_key": settings.require_mcp_api_key,
    }
    settings.data_dir = tmp_path / "data"
    settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
    settings.lancedb_dir = settings.data_dir / "lancedb"
    settings.asset_allow_prefixes = ""
    settings.asset_deny_prefixes = ""
    settings.api_key = None
    settings.require_mcp_api_key = False
    reset_bootstrap()
    bootstrap(settings)
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_rest_exposes_lifecycle_and_candidate_promotion(memory_surface_env):
    client = TestClient(app)
    memory = add_memory(MemoryCreate(content="REST lifecycle surface memory.", agent_id="codex"))["memory"]

    lifecycle_response = client.get(f"/memories/{memory['id']}/lifecycle")
    candidate_response = client.post(
        "/memory-candidates",
        json=ReaderItem(
            source_domain="session_event",
            source_id="event-rest-1",
            cube_id="cube-rest",
            content="REST candidate becomes promoted memory.",
            content_kind="note",
            tags=["rest", "candidate"],
            confidence=0.92,
            provenance={"source_domain": "session_event", "source_id": "event-rest-1"},
            metadata={"session_id": "session-rest"},
        ).model_dump(),
    )
    listed_response = client.get("/memory-candidates", params={"status": "candidate"})
    promote_response = client.post(
        f"/memory-candidates/{candidate_response.json()['id']}/promote",
        params={"reviewed_by": "api-reviewer"},
    )

    assert lifecycle_response.status_code == 200
    assert lifecycle_response.json()[0]["event_kind"] == "created"
    assert candidate_response.status_code == 200
    assert candidate_response.json()["status"] == "candidate"
    assert listed_response.status_code == 200
    assert listed_response.json()[0]["id"] == candidate_response.json()["id"]
    assert promote_response.status_code == 200
    assert promote_response.json()["candidate"]["status"] == "active"
    assert promote_response.json()["memory"]["source_kind"] == "reader_candidate"


def test_mcp_exposes_lifecycle_and_candidate_promotion(memory_surface_env):
    from app.mcp_server import (
        gcd_create_memory_candidate,
        gcd_list_memory_candidates,
        gcd_list_memory_lifecycle_events,
        gcd_promote_memory_candidate,
    )

    memory = add_memory(MemoryCreate(content="MCP lifecycle surface memory.", agent_id="codex"))["memory"]
    candidate = gcd_create_memory_candidate(
        source_domain="tool_trace",
        source_id="trace-mcp-1",
        content="MCP candidate becomes promoted memory.",
        cube_id="cube-mcp",
        tags=["mcp", "candidate"],
        confidence=0.88,
        created_by="mcp-test",
    )
    listed = gcd_list_memory_candidates(status="candidate")
    promoted = gcd_promote_memory_candidate(candidate["id"], reviewed_by="mcp-reviewer")
    lifecycle = gcd_list_memory_lifecycle_events(memory["id"])

    assert lifecycle[0]["event_kind"] == "created"
    assert listed[0]["id"] == candidate["id"]
    assert promoted["candidate"]["promoted_memory_id"] == promoted["memory_id"]
    assert promoted["memory"]["source_kind"] == "reader_candidate"


def test_rest_and_mcp_expose_fine_reader_candidate_creation(memory_surface_env):
    client = TestClient(app)
    rest_response = client.post(
        "/memory-candidates/from-fine-reader",
        json={"source": "rest-note", "text": "Decision: REST fine reader creates candidates.", "cube_id": "cube-rest"},
    )

    from app.mcp_server import gcd_create_memory_candidates_from_fine_reader

    mcp_result = gcd_create_memory_candidates_from_fine_reader(
        source="mcp-note",
        text="Preference: MCP fine reader keeps deterministic source quotes.",
        cube_id="cube-mcp",
        created_by="mcp-test",
    )

    assert rest_response.status_code == 200
    assert rest_response.json()["created_count"] == 1
    assert rest_response.json()["reader_item"]["metadata"]["reader"]["mode"] == "fine"
    assert rest_response.json()["candidates"][0]["metadata"]["fine"]["memory_type"] == "decision"
    assert mcp_result["created_count"] == 1
    assert mcp_result["candidates"][0]["metadata"]["fine"]["memory_type"] == "preference"


def test_rest_exposes_memory_relation_index_rebuild_and_list(memory_surface_env):
    client = TestClient(app)
    first = add_memory(MemoryCreate(content="REST relation surface one", tags=["surface-relation"], agent_id="codex"))["memory"]
    second = add_memory(MemoryCreate(content="REST relation surface two", tags=["surface-relation"], agent_id="codex"))["memory"]
    add_memory_evidence(
        first["id"],
        MemoryEvidenceCreate(source_domain="session_event", source_id="event-rest-relation", quote="surface relation evidence"),
    )

    rebuild_response = client.post("/memories/relations/rebuild", params={"limit": 100, "created_by": "rest-test"})
    list_response = client.get("/memories/relations", params={"source_id": first["id"], "limit": 20})

    assert rebuild_response.status_code == 200
    assert rebuild_response.json()["created_count"] >= 2
    assert list_response.status_code == 200
    relations = list_response.json()
    assert any(edge["relation_kind"] == "shared_tag" and edge["target_id"] == second["id"] for edge in relations)
    assert any(edge["relation_kind"] == "supported_by" and edge["target_id"] == "event-rest-relation" for edge in relations)


def test_mcp_exposes_memory_relation_index_rebuild_and_list(memory_surface_env):
    from app.mcp_server import gcd_build_memory_relation_index, gcd_list_memory_relations

    first = add_memory(MemoryCreate(content="MCP relation surface one", tags=["mcp-relation"], agent_id="codex"))["memory"]
    second = add_memory(MemoryCreate(content="MCP relation surface two", tags=["mcp-relation"], agent_id="codex"))["memory"]

    rebuilt = gcd_build_memory_relation_index(limit=100, created_by="mcp-test")
    relations = gcd_list_memory_relations(source_id=first["id"], limit=20)

    assert rebuilt["created_count"] >= 2
    assert any(edge["relation_kind"] == "shared_tag" and edge["target_id"] == second["id"] for edge in relations)
    assert all(edge["source_id"] == first["id"] for edge in relations)
