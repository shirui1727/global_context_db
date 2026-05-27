from dataclasses import dataclass
from typing import Any

from app.core.schemas import MemoryFeedbackActionCreate, MemoryFeedbackCreate
from app.memory import feedback_service
from app.runtime.components import RuntimeComponents


@dataclass(frozen=True)
class FeedbackHandler:
    components: RuntimeComponents

    def create_feedback(self, payload: MemoryFeedbackCreate) -> dict:
        return feedback_service.create_memory_feedback(payload)

    def list_feedback(self, limit: int = 100, status: str | None = None, target_memory_id: str | None = None) -> list[dict]:
        return feedback_service.list_memory_feedback(limit=limit, status=status, target_memory_id=target_memory_id)

    def add_action(self, feedback_id: str, payload: MemoryFeedbackActionCreate) -> dict:
        return feedback_service.add_memory_feedback_action(feedback_id, payload)

    def list_actions(self, feedback_id: str, limit: int = 100) -> list[dict]:
        return feedback_service.list_memory_feedback_actions(feedback_id, limit=limit)

    def apply(self, feedback_id: str, actor: str = "memory_feedback") -> dict[str, Any]:
        return feedback_service.apply_memory_feedback(feedback_id, actor=actor)
