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
