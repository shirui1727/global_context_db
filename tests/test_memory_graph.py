from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import MemoryCreate, MemoryEvidenceCreate
from app.memory.graph_service import build_memory_relation_index, list_memory_relations
from app.memory.service import add_memory, add_memory_evidence
from app.storage.bootstrap import bootstrap, reset_bootstrap


@pytest.fixture()
def graph_env(tmp_path: Path):
    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
    }
    settings.data_dir = tmp_path / "data"
    settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
    settings.lancedb_dir = settings.data_dir / "lancedb"
    reset_bootstrap()
    bootstrap(settings)
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_memory_relation_index_links_shared_tags_and_evidence(graph_env):
    first = add_memory(MemoryCreate(content="Use relation index for memory graph.", tags=["graph", "memory"], agent_id="codex"))["memory"]
    second = add_memory(MemoryCreate(content="Graph relation index stays SQLite only.", tags=["graph"], agent_id="codex"))["memory"]
    add_memory_evidence(
        first["id"],
        MemoryEvidenceCreate(source_domain="session_event", source_id="event-graph-1", quote="graph evidence"),
    )

    result = build_memory_relation_index(limit=100, created_by="graph-test")
    relations = list_memory_relations(source_id=first["id"], limit=20)

    assert result["created_count"] >= 2
    assert any(edge["relation_kind"] == "shared_tag" and edge["target_id"] == second["id"] for edge in relations)
    assert any(edge["relation_kind"] == "supported_by" and edge["target_id"] == "event-graph-1" for edge in relations)
    assert all(edge["source_domain"] == "memory" for edge in relations)
