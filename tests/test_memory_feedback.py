
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import MemoryCreate, MemoryFeedbackActionCreate, MemoryFeedbackCreate
from app.memory.feedback_service import (
    add_memory_feedback_action,
    apply_memory_feedback,
    create_memory_feedback,
)
from app.memory.service import add_memory, list_memory_evidence, list_memory_versions
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import memories_repo


@pytest.fixture()
def feedback_env(tmp_path: Path):
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


def _memory(content="Old memory content", cube_id="cube-feedback"):
    return add_memory(
        MemoryCreate(
            cube_id=cube_id,
            content=content,
            tags=["feedback"],
            agent_id="codex",
            metadata={"case": "feedback"},
        )
    )["memory"]


def _feedback(target_memory_id=None, cube_id="cube-feedback"):
    return create_memory_feedback(
        MemoryFeedbackCreate(
            cube_id=cube_id,
            feedback_text="Please correct this memory.",
            target_memory_id=target_memory_id,
            created_by="tester",
            metadata={"source": "unit-test"},
        )
    )


def test_feedback_update_memory_action_applies_and_versions(feedback_env):
    memory = _memory("Project tone is cold and industrial.")
    feedback = _feedback(memory["id"])
    add_memory_feedback_action(
        feedback["id"],
        MemoryFeedbackActionCreate(
            action_type="update",
            target_memory_id=memory["id"],
            payload={"content": "Project tone is warm and residential.", "tags": ["feedback", "corrected"]},
        ),
    )

    result = apply_memory_feedback(feedback["id"], actor="reviewer")
    updated = memories_repo().get(memory["id"])
    versions = list_memory_versions(memory["id"], limit=10)

    assert result["feedback"]["status"] == "applied"
    assert result["applied"] == 1
    assert updated["content"] == "Project tone is warm and residential."
    assert "corrected" in updated["tags"]
    assert {item["change_type"] for item in versions} >= {"before_update", "updated"}


def test_feedback_archive_memory_action_applies(feedback_env):
    memory = _memory("Temporary memory that should be archived.")
    feedback = _feedback(memory["id"])
    add_memory_feedback_action(
        feedback["id"],
        MemoryFeedbackActionCreate(
            action_type="archive",
            target_memory_id=memory["id"],
            payload={"reason": "outdated"},
        ),
    )

    result = apply_memory_feedback(feedback["id"], actor="reviewer")
    archived = memories_repo().get(memory["id"])

    assert result["applied"] == 1
    assert archived["status"] == "archived"


def test_feedback_add_evidence_action_applies(feedback_env):
    memory = _memory("Memory needs evidence.")
    feedback = _feedback(memory["id"])
    add_memory_feedback_action(
        feedback["id"],
        MemoryFeedbackActionCreate(
            action_type="add_evidence",
            target_memory_id=memory["id"],
            payload={
                "source_domain": "session_event",
                "source_id": "event-1",
                "quote": "User explicitly confirmed this.",
                "confidence": 0.9,
            },
        ),
    )

    result = apply_memory_feedback(feedback["id"], actor="reviewer")
    evidence = list_memory_evidence(memory["id"])

    assert result["applied"] == 1
    assert evidence[0]["source_domain"] == "session_event"
    assert evidence[0]["quote"] == "User explicitly confirmed this."
    assert evidence[0]["confidence"] == 0.9


def test_feedback_create_memory_action_applies(feedback_env):
    feedback = _feedback(target_memory_id=None)
    add_memory_feedback_action(
        feedback["id"],
        MemoryFeedbackActionCreate(
            action_type="create_memory",
            payload={
                "content": "New corrected memory from feedback.",
                "cube_id": "cube-feedback",
                "tags": ["feedback", "new"],
                "agent_id": "codex",
            },
        ),
    )

    result = apply_memory_feedback(feedback["id"], actor="reviewer")
    created_memory_id = result["actions"][0]["result"]["memory_id"]
    created = memories_repo().get(created_memory_id)

    assert result["applied"] == 1
    assert created["content"] == "New corrected memory from feedback."
    assert created["cube_id"] == "cube-feedback"
    assert "new" in created["tags"]


def test_feedback_apply_is_idempotent(feedback_env):
    memory = _memory("Apply once only.")
    feedback = _feedback(memory["id"])
    add_memory_feedback_action(
        feedback["id"],
        MemoryFeedbackActionCreate(
            action_type="add_evidence",
            target_memory_id=memory["id"],
            payload={"source_domain": "manual", "source_id": "note-1", "quote": "first apply"},
        ),
    )

    first = apply_memory_feedback(feedback["id"], actor="reviewer")
    second = apply_memory_feedback(feedback["id"], actor="reviewer")
    evidence = list_memory_evidence(memory["id"])

    assert first["applied"] == 1
    assert second["applied"] == 0
    assert len(evidence) == 1
