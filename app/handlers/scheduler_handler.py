from dataclasses import dataclass
from typing import Any

from app.runtime.components import RuntimeComponents
from app.scheduler import service as scheduler_service


@dataclass(frozen=True)
class SchedulerHandler:
    components: RuntimeComponents

    def claim_next(self, queue_name: str = "default", worker_id: str = "local", lease_seconds: int = 300) -> dict | None:
        return scheduler_service.claim_next_task(queue_name=queue_name, worker_id=worker_id, lease_seconds=lease_seconds)

    def run_pending(self, limit: int = 10, queue_name: str = "default", worker_id: str = "local") -> dict[str, Any]:
        return scheduler_service.run_pending_tasks(limit=limit, queue_name=queue_name, worker_id=worker_id)

    def release_expired(self) -> dict[str, int]:
        return {"released": scheduler_service.release_expired_claims(), "retried": scheduler_service.retry_failed_tasks()}

    def status(self) -> dict[str, Any]:
        return scheduler_service.scheduler_status()
