from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import ImprovementTaskCreate, MemoryCreate, MemoryPromotionCreate, MemoryUpdate
from app.governance.service import diagnostics
from app.memory.graph_service import build_memory_relation_index
from app.memory.service import add_memory, create_memory_promotion, update_memory
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.improvements.service import create_improvement_task


@pytest.fixture()
def diagnostics_env(tmp_path: Path):
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


def test_diagnostics_reports_pending_promotions_and_write_audit_counts(diagnostics_env):
    memory = add_memory(MemoryCreate(content="diagnostics write audit memory", agent_id="codex"))["memory"]
    update_memory(memory["id"], MemoryUpdate(content="diagnostics updated write audit memory"))
    create_memory_promotion(
        MemoryPromotionCreate(
            source_session_id="session-diag",
            proposed_content="Promote this pending diagnostic memory.",
            agent_id="codex",
        )
    )

    report = diagnostics()

    improvement = report["governance"]["improvement"]
    audit = report["governance"]["audit"]
    assert improvement["pending_promotion_count"] == 1
    assert audit["write_action_count"] >= 2
    assert audit["high_risk_write_action_count"] >= 1
    assert any(item["action"] == "memory.updated" for item in audit["write_action_counts"])


def test_diagnostics_reports_relation_index_kind_counts(diagnostics_env):
    first = add_memory(MemoryCreate(content="diagnostics relation one", tags=["diag-relation"], agent_id="codex"))["memory"]
    second = add_memory(MemoryCreate(content="diagnostics relation two", tags=["diag-relation"], agent_id="codex"))["memory"]
    duplicate = add_memory(MemoryCreate(content="diagnostics relation one", tags=["other"], agent_id="other-agent"))["memory"]

    build_memory_relation_index(limit=100, created_by="diagnostics-test")

    relation_index = diagnostics()["governance"]["memory"]["relation_index"]

    assert relation_index["total_count"] >= 4
    assert relation_index["kind_counts"]["shared_tag"] >= 2
    assert relation_index["kind_counts"]["duplicate_candidate"] >= 2
    assert relation_index["sample_count"] <= relation_index["total_count"]
    assert relation_index["sample_limit"] == 20


def test_diagnostics_reports_scheduler_queue_pressure(diagnostics_env):
    create_improvement_task(
        ImprovementTaskCreate(
            task_kind="reindex_asset",
            target_domain="asset",
            target_id="asset-diag-queue",
            queue_name="asset",
            created_by="diag-test",
        )
    )
    create_improvement_task(
        ImprovementTaskCreate(
            task_kind="verify_memory_evidence",
            target_domain="memory",
            target_id="memory-diag-queue",
            queue_name="memory_hygiene",
            created_by="diag-test",
        )
    )

    improvement = diagnostics()["governance"]["improvement"]

    assert any(item["queue_name"] == "asset" and item["status"] == "pending" for item in improvement["queue_counts"])
    assert any(item["queue_name"] == "memory_hygiene" and item["status"] == "pending" for item in improvement["queue_counts"])
    assert improvement["pending_by_queue"]["asset"] == 1
    assert improvement["pending_by_queue"]["memory_hygiene"] == 1


def test_diagnostics_reports_failed_queue_pressure(diagnostics_env):
    from app.scheduler.service import claim_next_task, fail_task

    create_improvement_task(
        ImprovementTaskCreate(
            task_kind="reindex_asset",
            target_domain="asset",
            target_id="asset-diag-failed-queue",
            queue_name="asset",
            created_by="diag-test",
        )
    )
    claimed = claim_next_task(queue_name="asset", worker_id="diag-worker")
    fail_task(claimed["id"], "diagnostic queue failure", retry_delay_seconds=60)

    improvement = diagnostics()["governance"]["improvement"]

    assert improvement["failed_by_queue"]["asset"] == 1
    assert any(item["queue_name"] == "asset" and item["status"] == "failed" for item in improvement["queue_counts"])


def test_diagnostics_reports_retryable_and_exhausted_failed_queue_pressure(diagnostics_env):
    from app.scheduler.service import claim_next_task, fail_task

    create_improvement_task(
        ImprovementTaskCreate(
            task_kind="reindex_asset",
            target_domain="asset",
            target_id="asset-diag-retryable-failed",
            queue_name="asset",
            max_retries=2,
            created_by="diag-test",
        )
    )
    retryable = claim_next_task(queue_name="asset", worker_id="diag-retryable")
    fail_task(retryable["id"], "retryable diagnostic failure", retry_delay_seconds=60)

    create_improvement_task(
        ImprovementTaskCreate(
            task_kind="reindex_asset",
            target_domain="asset",
            target_id="asset-diag-exhausted-failed",
            queue_name="asset",
            max_retries=1,
            created_by="diag-test",
        )
    )
    exhausted = claim_next_task(queue_name="asset", worker_id="diag-exhausted")
    fail_task(exhausted["id"], "exhausted diagnostic failure", retry_delay_seconds=60)

    improvement = diagnostics()["governance"]["improvement"]

    assert improvement["failed_by_queue"]["asset"] == 2
    assert improvement["retryable_failed_by_queue"]["asset"] == 1
    assert improvement["exhausted_failed_by_queue"]["asset"] == 1
