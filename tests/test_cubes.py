from pathlib import Path

import pytest

from app.assets.service import create_asset
from app.core.config import settings
from app.core.schemas import (
    AssetCreate,
    ContextCubeBindingCreate,
    ContextCubeCreate,
    MemoryCreate,
    RecallRequest,
    SearchRequest,
    SessionCreate,
)
from app.control.service import recall
from app.cubes.service import bind_to_cube, create_cube, get_cube, list_cube_bindings, list_cubes
from app.memory.service import add_memory
from app.retrieval.service import search_context
from app.sessions.service import create_session
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import db_counts


@pytest.fixture()
def cube_env(tmp_path: Path):
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


def test_context_cube_crud_and_bindings(cube_env):
    cube = create_cube(
        ContextCubeCreate(
            name="Archviz Project",
            cube_type="project",
            owner_id="project:archviz",
            visibility="shared",
            created_by="tester",
            metadata={"path": "S:/project/archviz"},
        )
    )
    loaded = get_cube(cube["id"])

    memory = add_memory(
        MemoryCreate(
            cube_id=cube["id"],
            content="Archviz project uses NAS-backed shared context cubes.",
            tags=["archviz"],
            agent_id="codex",
        )
    )
    binding = bind_to_cube(
        cube["id"],
        ContextCubeBindingCreate(
            target_domain="memory",
            target_id=memory["memory_id"],
            binding_kind="owns",
            metadata={"reason": "project fact"},
        ),
    )
    bindings = list_cube_bindings(cube["id"])

    assert loaded["id"] == cube["id"]
    assert loaded["cube_type"] == "project"
    assert cube["id"] in {item["id"] for item in list_cubes()}
    assert binding["cube_id"] == cube["id"]
    assert bindings[0]["target_id"] == memory["memory_id"]
    assert db_counts()["context_cubes"] == 1
    assert db_counts()["cube_bindings"] == 1


def test_cube_id_is_written_to_memory_asset_session_vectors(cube_env):
    cube = create_cube(ContextCubeCreate(name="Client A", cube_type="project", owner_id="client-a"))

    memory = add_memory(
        MemoryCreate(
            cube_id=cube["id"],
            content="Client A requires warm minimalist lobby renders.",
            tags=["client-a"],
            agent_id="codex",
        )
    )
    asset = create_asset(
        AssetCreate(
            cube_id=cube["id"],
            uri="smb://NAS/client-a/lobby.jpg",
            asset_key="client-a:lobby",
            checksum="sha-client-a",
            summary="Warm minimalist lobby render reference.",
        )
    )
    session = create_session(
        SessionCreate(
            cube_id=cube["id"],
            source_agent="codex",
            project_path="S:/client-a",
            title="Client A lobby",
        )
    )

    result = search_context("warm minimalist lobby", top_k=10, cube_id=cube["id"])

    ids = {item["id"] for group in result["groups"].values() for item in group}
    assert memory["memory"]["cube_id"] == cube["id"]
    assert asset["cube_id"] == cube["id"]
    assert session["cube_id"] == cube["id"]
    assert memory["memory_id"] in ids
    assert asset["id"] in ids


def test_cube_search_isolation_and_explicit_shared_cube(cube_env):
    private_a = create_cube(ContextCubeCreate(name="Private A", cube_type="project", owner_id="a", visibility="private"))
    private_b = create_cube(ContextCubeCreate(name="Private B", cube_type="project", owner_id="b", visibility="private"))
    shared = create_cube(ContextCubeCreate(name="Shared Style", cube_type="shared", owner_id="team", visibility="shared"))

    add_memory(MemoryCreate(cube_id=private_a["id"], content="Project A secret material is blue marble.", tags=["secret"]))
    add_memory(MemoryCreate(cube_id=private_b["id"], content="Project B secret material is green slate.", tags=["secret"]))
    add_memory(MemoryCreate(cube_id=shared["id"], content="Shared render rule prefers soft global illumination.", tags=["shared"]))

    only_a = recall(RecallRequest(query="secret material", top_k=10, cube_id=private_a["id"]))
    a_plus_shared = recall(
        RecallRequest(query="render rule secret material", top_k=10, cube_ids=[private_a["id"], shared["id"]])
    )

    only_a_text = "\n".join(item["text"] for group in only_a["groups"].values() for item in group)
    shared_text = "\n".join(item["text"] for group in a_plus_shared["groups"].values() for item in group)
    assert "blue marble" in only_a_text
    assert "green slate" not in only_a_text
    assert "soft global illumination" in shared_text


def test_default_cube_resolver_assigns_session_project_and_agent_scopes(cube_env):
    from app.assets.service import create_asset
    from app.core.schemas import AssetCreate, MemoryCreate, SessionCreate
    from app.cubes.service import list_cubes
    from app.memory.service import add_memory
    from app.sessions.service import create_session

    session = create_session(SessionCreate(source_agent="codex", project_path="S:/client-a", title="Client A"))
    memory = add_memory(
        MemoryCreate(
            content="Session-scoped memory inherits the session cube.",
            session_id=session["id"],
            agent_id="codex",
        )
    )["memory"]
    project_asset = create_asset(
        AssetCreate(
            uri="file:///S:/client-a/ref.png",
            asset_key="client-a-ref",
            checksum="client-a-ref-checksum",
            summary="Project asset inherits the project cube.",
            metadata={"project_path": "S:/client-a"},
        )
    )
    agent_memory = add_memory(MemoryCreate(content="Agent-scoped memory gets an agent cube.", agent_id="codex"))["memory"]
    cubes = list_cubes(limit=20)

    assert session["cube_id"]
    assert memory["cube_id"] == session["cube_id"]
    assert project_asset["cube_id"] == session["cube_id"]
    assert agent_memory["cube_id"]
    assert agent_memory["cube_id"] != session["cube_id"]
    assert any(cube["id"] == session["cube_id"] and cube["cube_type"] == "project" for cube in cubes)
    assert any(cube["id"] == agent_memory["cube_id"] and cube["cube_type"] == "agent" for cube in cubes)


def test_recall_with_project_cube_includes_shared_and_kb_cubes(cube_env):
    project = create_cube(ContextCubeCreate(name="Project Scoped", cube_type="project", owner_id="project:scoped"))
    other = create_cube(ContextCubeCreate(name="Other Project", cube_type="project", owner_id="project:other"))
    shared = create_cube(ContextCubeCreate(name="Shared Rendering", cube_type="shared", owner_id="team", visibility="shared"))
    kb = create_cube(ContextCubeCreate(name="KB Materials", cube_type="kb", owner_id="kb:materials", visibility="shared"))

    add_memory(MemoryCreate(cube_id=project["id"], content="Scoped project lobby uses bronze mesh panels."))
    add_memory(MemoryCreate(cube_id=other["id"], content="Other project private rule uses red terrazzo."))
    add_memory(MemoryCreate(cube_id=shared["id"], content="Shared rendering rule uses soft contact shadows."))
    add_memory(MemoryCreate(cube_id=kb["id"], content="Knowledge base material note recommends low-iron glass."))

    result = recall(RecallRequest(query="rendering material project rule", top_k=10, cube_id=project["id"]))
    text = "\n".join(item["text"] for group in result["groups"].values() for item in group)

    assert "bronze mesh" in text
    assert "soft contact shadows" in text
    assert "low-iron glass" in text
    assert "red terrazzo" not in text
    assert result["cube_scope"]["base_cube_ids"] == [project["id"]]
    assert shared["id"] in result["cube_scope"]["readable_cube_ids"]
    assert kb["id"] in result["cube_scope"]["readable_cube_ids"]


def test_cube_snapshot_export_import_round_trip(cube_env, tmp_path):
    from app.backup.service import export_cube_snapshot, import_cube_snapshot
    from app.core.config import settings
    from app.core.schemas import ContextCubeBindingCreate, ContextCubeCreate, MemoryCreate
    from app.cubes.service import bind_to_cube, create_cube, get_cube, list_cube_bindings
    from app.memory.service import add_memory, list_memories
    from app.storage.bootstrap import bootstrap, reset_bootstrap

    cube = create_cube(ContextCubeCreate(name="Portable Cube", cube_type="project", owner_id="portable"))
    memory = add_memory(MemoryCreate(cube_id=cube["id"], content="Portable cube memory survives import.", tags=["portable"]))["memory"]
    bind_to_cube(cube["id"], ContextCubeBindingCreate(target_domain="memory", target_id=memory["id"]))

    snapshot = export_cube_snapshot(cube["id"])

    assert snapshot["kind"] == "context_cube_snapshot"
    assert snapshot["cube"]["id"] == cube["id"]
    assert snapshot["counts"]["memories"] == 1
    assert snapshot["memories"][0]["content"] == "Portable cube memory survives import."

    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
    }
    try:
        settings.data_dir = tmp_path / "imported"
        settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
        settings.lancedb_dir = settings.data_dir / "lancedb"
        reset_bootstrap()
        bootstrap(settings)

        imported = import_cube_snapshot(snapshot)
        imported_cube = get_cube(cube["id"])
        imported_memories = list_memories(limit=20)
        imported_bindings = list_cube_bindings(cube["id"])

        assert imported["ok"] is True
        assert imported["counts"]["memories"] == 1
        assert imported_cube["name"] == "Portable Cube"
        assert imported_memories[0]["content"] == "Portable cube memory survives import."
        assert imported_memories[0]["cube_id"] == cube["id"]
        assert imported_bindings[0]["target_id"] == memory["id"]
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
        reset_bootstrap()
        bootstrap(settings)


def test_writable_cube_ids_fan_out_memory_writes(cube_env):
    from app.core.schemas import MemoryCreate
    from app.cubes.service import create_cube
    from app.memory.service import add_memory, list_memories

    project = create_cube(ContextCubeCreate(name="Writable Project", cube_type="project", owner_id="project:writable"))
    shared = create_cube(ContextCubeCreate(name="Writable Shared", cube_type="shared", owner_id="team", visibility="shared"))

    result = add_memory(
        MemoryCreate(
            content="Writable cube fan-out stores this memory in project and shared cubes.",
            writable_cube_ids=[project["id"], shared["id"]],
            agent_id="codex",
            tags=["fanout"],
        )
    )
    memories = list_memories(limit=20)
    by_cube = {memory["cube_id"]: memory for memory in memories}

    assert result["status"] == "created"
    assert result["write_scope"]["writable_cube_ids"] == [project["id"], shared["id"]]
    assert result["write_scope"]["created_count"] == 2
    assert project["id"] in by_cube
    assert shared["id"] in by_cube
    assert by_cube[project["id"]]["content"] == "Writable cube fan-out stores this memory in project and shared cubes."
    assert by_cube[shared["id"]]["content"] == "Writable cube fan-out stores this memory in project and shared cubes."
    assert by_cube[project["id"]]["id"] != by_cube[shared["id"]]["id"]
