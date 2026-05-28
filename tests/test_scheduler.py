
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import ImprovementTaskCreate
from app.improvements.service import create_improvement_task
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import improvement_tasks_repo


@pytest.fixture()
def scheduler_env(tmp_path: Path):
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


def _create_task(**overrides):
    payload = {
        "task_kind": "reindex_asset",
        "target_domain": "asset",
        "target_id": "asset-1",
        "cube_id": "cube-a",
        "priority": 10,
        "queue_name": "asset",
        "created_by": "tester",
    }
    payload.update(overrides)
    return create_improvement_task(ImprovementTaskCreate(**payload))


def test_scheduler_claims_pending_task_with_cube_and_queue(scheduler_env):
    from app.scheduler.service import claim_next_task

    task = _create_task()

    claimed = claim_next_task(queue_name="asset", worker_id="worker-1", lease_seconds=60)

    assert claimed is not None
    assert claimed["id"] == task["id"]
    assert claimed["cube_id"] == "cube-a"
    assert claimed["queue_name"] == "asset"
    assert claimed["worker_id"] == "worker-1"
    assert claimed["claimed_by"] == "worker-1"
    assert claimed["status"] == "running"
    assert claimed["claimed_at"]
    assert claimed["claimed_until"]


def test_scheduler_prevents_double_claim(scheduler_env):
    from app.scheduler.service import claim_next_task

    _create_task(target_id="asset-double")

    first = claim_next_task(queue_name="asset", worker_id="worker-1", lease_seconds=60)
    second = claim_next_task(queue_name="asset", worker_id="worker-2", lease_seconds=60)

    assert first is not None
    assert second is None
    assert improvement_tasks_repo().get(first["id"])["worker_id"] == "worker-1"


def test_scheduler_releases_expired_claim(scheduler_env):
    from app.scheduler.service import claim_next_task, release_expired_claims

    _create_task(target_id="asset-expired")
    first = claim_next_task(queue_name="asset", worker_id="worker-1", lease_seconds=-1)

    released = release_expired_claims()
    second = claim_next_task(queue_name="asset", worker_id="worker-2", lease_seconds=60)

    assert first is not None
    assert released == 1
    assert second is not None
    assert second["id"] == first["id"]
    assert second["worker_id"] == "worker-2"


def test_scheduler_retries_failed_until_max_retries(scheduler_env):
    from app.scheduler.service import claim_next_task, fail_task, retry_failed_tasks

    _create_task(target_id="asset-retry", max_retries=2)
    claimed = claim_next_task(queue_name="asset", worker_id="worker-1", lease_seconds=60)

    first_failure = fail_task(claimed["id"], "temporary failure", retry_delay_seconds=0)
    first_retried = retry_failed_tasks()
    retry_claim = claim_next_task(queue_name="asset", worker_id="worker-2", lease_seconds=60)
    second_failure = fail_task(retry_claim["id"], "permanent failure", retry_delay_seconds=0)
    second_retried = retry_failed_tasks()
    final = improvement_tasks_repo().get(claimed["id"])

    assert first_failure["status"] == "failed"
    assert first_failure["retry_count"] == 1
    assert first_retried == 1
    assert retry_claim["worker_id"] == "worker-2"
    assert second_failure["retry_count"] == 2
    assert second_retried == 0
    assert final["status"] == "failed"
    assert final["last_error"] == "permanent failure"


def test_scheduler_run_pending_tasks_executes_known_task(scheduler_env, monkeypatch):
    from app.scheduler.service import run_pending_tasks

    _create_task(target_id="asset-run")

    def fake_execute(task, *, actor="scheduler", clean_legacy=True):
        assert task["target_id"] == "asset-run"
        assert actor == "worker-run"
        return {"ok": True, "task_id": task["id"]}

    monkeypatch.setattr("app.improvements.service.execute_improvement_task", fake_execute)

    result = run_pending_tasks(limit=1, queue_name="asset", worker_id="worker-run")
    tasks = improvement_tasks_repo().list_recent(limit=10, status="done")

    assert result["claimed"] == 1
    assert result["done"] == 1
    assert result["failed"] == 0
    assert tasks[0]["metadata"]["result"]["ok"] is True


def test_scheduler_run_pending_summary_includes_queue_worker_and_task_ids(scheduler_env, monkeypatch):
    from app.scheduler.service import run_pending_tasks

    task = _create_task(target_id="asset-summary")

    def fake_execute(claimed_task, actor="scheduler", clean_legacy=True):
        return {"ok": True, "actor": actor}

    monkeypatch.setattr("app.improvements.service.execute_improvement_task", fake_execute)

    result = run_pending_tasks(limit=1, queue_name="asset", worker_id="worker-summary")

    assert result["queue_name"] == "asset"
    assert result["worker_id"] == "worker-summary"
    assert result["requested_limit"] == 1
    assert result["task_ids"] == [task["id"]]
    assert result["tasks"][0]["task_id"] == task["id"]
    assert result["tasks"][0]["task_kind"] == "reindex_asset"


def test_scheduler_status_reports_queue_counts(scheduler_env):
    from app.scheduler.service import scheduler_status

    _create_task(target_id="asset-status", queue_name="asset")
    _create_task(target_id="hygiene-status", task_kind="verify_memory_evidence", target_domain="memory", queue_name="memory_hygiene")

    status = scheduler_status()

    assert any(item["queue_name"] == "asset" and item["status"] == "pending" for item in status["queue_counts"])
    assert any(item["queue_name"] == "memory_hygiene" and item["status"] == "pending" for item in status["queue_counts"])
    assert status["pending_by_queue"]["asset"] == 1
    assert status["pending_by_queue"]["memory_hygiene"] == 1
