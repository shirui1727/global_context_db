
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import ContextCubeCreate, MemoryFeedbackCreate
from app.storage.bootstrap import reset_bootstrap


@pytest.fixture()
def runtime_env(tmp_path: Path):
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
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_runtime_components_bootstrap_is_idempotent(runtime_env):
    from app.runtime.components import get_runtime_components

    first = get_runtime_components(settings)
    second = get_runtime_components(settings)

    assert first.settings is settings
    assert second.settings is settings
    assert first.sqlite_path == settings.sqlite_path
    assert first.data_dir == settings.data_dir
    assert settings.sqlite_path.exists()


def test_cube_handler_wraps_service_errors(runtime_env):
    from app.handlers.cube_handler import CubeHandler
    from app.runtime.components import get_runtime_components

    handler = CubeHandler(get_runtime_components(settings))
    cube = handler.create_cube(ContextCubeCreate(name="Handler Cube", cube_type="project"))

    assert handler.get_cube(cube["id"])["name"] == "Handler Cube"
    with pytest.raises(ValueError, match="context cube not found"):
        handler.get_cube("missing-cube")


def test_scheduler_handler_delegates_claim_and_status(runtime_env):
    from app.core.schemas import ImprovementTaskCreate
    from app.handlers.scheduler_handler import SchedulerHandler
    from app.improvements.service import create_improvement_task
    from app.runtime.components import get_runtime_components

    handler = SchedulerHandler(get_runtime_components(settings))
    create_improvement_task(
        ImprovementTaskCreate(
            task_kind="reindex_asset",
            target_domain="asset",
            target_id="asset-handler",
            queue_name="handler",
        )
    )

    claimed = handler.claim_next(queue_name="handler", worker_id="handler-worker", lease_seconds=60)
    status = handler.status()

    assert claimed["target_id"] == "asset-handler"
    assert claimed["worker_id"] == "handler-worker"
    assert any(item["status"] == "running" for item in status["status_counts"])


def test_feedback_handler_creates_action_and_applies(runtime_env):
    from app.core.schemas import MemoryCreate, MemoryFeedbackActionCreate
    from app.handlers.feedback_handler import FeedbackHandler
    from app.memory.service import add_memory
    from app.runtime.components import get_runtime_components
    from app.storage.repo import memories_repo

    components = get_runtime_components(settings)
    memory = add_memory(MemoryCreate(content="Old handler memory", agent_id="codex"))["memory"]
    handler = FeedbackHandler(components)
    feedback = handler.create_feedback(
        MemoryFeedbackCreate(feedback_text="Fix handler memory", target_memory_id=memory["id"])
    )
    handler.add_action(
        feedback["id"],
        MemoryFeedbackActionCreate(
            action_type="update",
            target_memory_id=memory["id"],
            payload={"content": "New handler memory"},
        ),
    )

    result = handler.apply(feedback["id"], actor="handler-test")

    assert result["applied"] == 1
    assert memories_repo().get(memory["id"])["content"] == "New handler memory"



def test_memory_asset_session_handlers_delegate(runtime_env):
    from app.core.schemas import AssetCreate, MemoryCreate, SessionCreate
    from app.handlers.asset_handler import AssetHandler
    from app.handlers.memory_handler import MemoryHandler
    from app.handlers.session_handler import SessionHandler
    from app.runtime.components import get_runtime_components

    components = get_runtime_components(settings)
    memory_handler = MemoryHandler(components)
    asset_handler = AssetHandler(components)
    session_handler = SessionHandler(components)

    memory = memory_handler.add_memory(MemoryCreate(content="Handler memory delegates to service.", agent_id="codex"))
    asset = asset_handler.create_asset(
        AssetCreate(
            uri="smb://NAS/handler/asset.png",
            asset_key="handler:asset",
            checksum="handler-asset-sha",
            summary="Handler asset delegates to service.",
        )
    )
    session = session_handler.create_session(SessionCreate(source_agent="codex", title="Handler session"))

    assert memory["memory"]["content"] == "Handler memory delegates to service."
    assert asset["asset_key"] == "handler:asset"
    assert session["title"] == "Handler session"
    assert session_handler.get_session(session["id"])["id"] == session["id"]
