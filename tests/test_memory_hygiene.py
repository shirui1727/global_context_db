from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import MemoryCreate
from app.memory.service import add_memory, enqueue_memory_hygiene
from app.scheduler.service import run_pending_tasks
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import improvement_tasks_repo


@pytest.fixture()
def hygiene_env(tmp_path: Path):
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


def test_memory_hygiene_enqueues_quality_tasks_on_hygiene_queue(hygiene_env):
    low = add_memory(
        MemoryCreate(
            content="Low trust memories should enter hygiene verification.",
            tags=["hygiene"],
            agent_id="codex",
            trust_level="agent_inferred",
        )
    )
    stale = add_memory(
        MemoryCreate(
            content="Expired hygiene memory should refresh.",
            tags=["hygiene"],
            agent_id="codex",
            metadata={"valid_until": "2000-01-01T00:00:00+00:00"},
        )
    )

    result = enqueue_memory_hygiene(limit=20, created_by="hygiene-test")
    tasks = improvement_tasks_repo().list_recent(limit=20, target_domain="memory")

    assert result["queue_name"] == "memory_hygiene"
    assert result["created_count"] >= 2
    assert {task["queue_name"] for task in tasks} == {"memory_hygiene"}
    assert any(task["target_id"] == low["memory_id"] for task in tasks)
    assert any(task["target_id"] == stale["memory_id"] for task in tasks)


def test_memory_hygiene_tasks_have_deterministic_executor_results(hygiene_env):
    add_memory(
        MemoryCreate(
            content="Low evidence memory should produce hygiene executor proposal.",
            tags=["hygiene-exec"],
            agent_id="codex",
            trust_level="agent_inferred",
        )
    )
    enqueue_memory_hygiene(limit=10, created_by="hygiene-test")

    result = run_pending_tasks(limit=5, queue_name="memory_hygiene", worker_id="hygiene-worker")

    assert result["done"] >= 1
    assert all(item["result"]["status"] == "proposal" for item in result["tasks"] if item["ok"])
    assert any(item["result"]["recommended_action"] == "attach_evidence_or_verify" for item in result["tasks"] if item["ok"])


def test_memory_hygiene_executor_includes_review_snapshots(hygiene_env):
    created = add_memory(
        MemoryCreate(
            content="Review snapshot memory should carry current state.",
            tags=["hygiene-snapshot"],
            agent_id="codex",
            trust_level="agent_inferred",
        )
    )["memory"]
    enqueue_memory_hygiene(limit=10, created_by="hygiene-test")

    result = run_pending_tasks(limit=5, queue_name="memory_hygiene", worker_id="hygiene-worker")
    proposal = next(item["result"] for item in result["tasks"] if item["task"]["target_id"] == created["id"])

    assert proposal["status"] == "proposal"
    assert proposal["auto_mutation"] is False
    assert proposal["review_snapshot"]["id"] == created["id"]
    assert proposal["review_snapshot"]["content_preview"].startswith("Review snapshot memory")
    assert proposal["review_snapshot"]["trust_level"] == "agent_inferred"
    assert proposal["review_snapshot"]["tags"] == ["hygiene-snapshot"]
    assert proposal["affected_memory_ids"] == [created["id"]]


def test_memory_hygiene_conflict_proposal_includes_both_memory_snapshots(hygiene_env):
    left = add_memory(
        MemoryCreate(
            content="Project policy should enable relation review.",
            tags=["conflict-review"],
            agent_id="codex",
        )
    )["memory"]
    right = add_memory(
        MemoryCreate(
            content="Project policy should not enable relation review.",
            tags=["conflict-review"],
            agent_id="codex",
        )
    )["memory"]
    enqueue_memory_hygiene(limit=10, created_by="hygiene-test")

    result = run_pending_tasks(limit=10, queue_name="memory_hygiene", worker_id="hygiene-worker")
    conflict = next(item["result"] for item in result["tasks"] if item["result"]["task_kind"] == "resolve_memory_conflict")

    assert conflict["status"] == "proposal"
    assert conflict["recommended_action"] == "compare_conflicting_memories"
    assert set(conflict["affected_memory_ids"]) == {left["id"], right["id"]}
    snapshots = [conflict["review_snapshot"], *conflict["related_snapshots"]]
    assert {snapshot["id"] for snapshot in snapshots} == {left["id"], right["id"]}
    assert all(snapshot["content_preview"] for snapshot in snapshots)
