from dataclasses import dataclass
from typing import Any

from app.core.schemas import HookEventEmit, HookSubscriptionCreate
from app.hooks import service as hook_service
from app.runtime.components import RuntimeComponents


@dataclass(frozen=True)
class HookHandler:
    components: RuntimeComponents

    def create_subscription(self, payload: HookSubscriptionCreate) -> dict[str, Any]:
        return hook_service.create_hook_subscription(payload)

    def list_subscriptions(
        self,
        hook_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return hook_service.list_hook_subscriptions(hook_name=hook_name, status=status, limit=limit)

    def emit_event(self, payload: HookEventEmit) -> dict[str, Any]:
        return hook_service.emit_hook_event(payload)

    def list_events(
        self,
        hook_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return hook_service.list_hook_events(hook_name=hook_name, status=status, limit=limit)

    def mark_dispatched(self, event_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return hook_service.mark_hook_event_dispatched(event_id, metadata=metadata)
