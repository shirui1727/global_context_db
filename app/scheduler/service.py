from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.schemas import ImprovementTaskUpdate
from app.improvements.service import update_improvement_task
from app.storage.repo import improvement_tasks_repo


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def _now() -> str:
    return _iso(_now_dt())


def claim_next_task(queue_name: str = "default", worker_id: str = "local", lease_seconds: int = 300) -> dict | None:
    now_dt = _now_dt()
    return improvement_tasks_repo().claim_next(
        queue_name=queue_name or "default",
        worker_id=worker_id or "local",
        now=_iso(now_dt),
        claimed_until=_iso(now_dt + timedelta(seconds=lease_seconds)),
    )


def complete_task(task_id: str, result: dict[str, Any] | None = None) -> dict:
    task = improvement_tasks_repo().get(task_id)
    if not task:
        raise ValueError("improvement task not found")
    metadata = dict(task.get("metadata") or {})
    if result is not None:
        metadata["result"] = result
    return update_improvement_task(
        task_id,
        ImprovementTaskUpdate(
            status="done",
            finished_at=_now(),
            claimed_by=task.get("claimed_by"),
            worker_id=task.get("worker_id"),
            metadata=metadata,
        ),
    )


def fail_task(task_id: str, error: str, retry_delay_seconds: int = 60) -> dict:
    task = improvement_tasks_repo().get(task_id)
    if not task:
        raise ValueError("improvement task not found")
    retry_count = int(task.get("retry_count") or 0) + 1
    next_run_at = _iso(_now_dt() + timedelta(seconds=retry_delay_seconds))
    return update_improvement_task(
        task_id,
        ImprovementTaskUpdate(
            status="failed",
            finished_at=_now(),
            error_message=error,
            last_error=error,
            retry_count=retry_count,
            next_run_at=next_run_at,
            claimed_by=task.get("claimed_by"),
            worker_id=task.get("worker_id"),
        ),
    )


def release_expired_claims(now: str | None = None) -> int:
    return improvement_tasks_repo().release_expired_claims(now or _now())


def retry_failed_tasks(now: str | None = None) -> int:
    return improvement_tasks_repo().retry_failed(now or _now())


def run_pending_tasks(limit: int = 10, queue_name: str = "default", worker_id: str = "local") -> dict:
    summary: dict[str, Any] = {"claimed": 0, "done": 0, "failed": 0, "tasks": []}
    for _ in range(max(0, limit)):
        task = claim_next_task(queue_name=queue_name, worker_id=worker_id)
        if not task:
            break
        summary["claimed"] += 1
        try:
            from app.improvements import service as improvements_service

            result = improvements_service.execute_improvement_task(task, actor=worker_id)
        except Exception as error:
            failed = fail_task(task["id"], str(error))
            summary["failed"] += 1
            summary["tasks"].append({"task": failed, "ok": False, "error": str(error)})
            continue
        done = complete_task(task["id"], result)
        summary["done"] += 1
        summary["tasks"].append({"task": done, "ok": True, "result": result})
    return summary


def scheduler_status() -> dict:
    return {"status_counts": improvement_tasks_repo().status_counts()}
