from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from app.core.schemas import HookEventEmit, HookSubscriptionCreate
from app.storage.repo import hook_events_repo, hook_subscriptions_repo

HOOK_SUBSCRIPTION_STATUSES = {"active", "paused", "disabled"}
HOOK_EVENT_STATUSES = {"queued", "no_subscriber", "dispatched"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _validate_hook_name(hook_name: str) -> str:
    normalized = (hook_name or "").strip()
    if not normalized:
        raise ValueError("hook_name is required")
    return normalized


def _validate_subscription_status(status: str) -> str:
    normalized = (status or "active").strip()
    if normalized not in HOOK_SUBSCRIPTION_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(HOOK_SUBSCRIPTION_STATUSES))}")
    return normalized


def create_hook_subscription(payload: HookSubscriptionCreate) -> dict[str, Any]:
    now = _now()
    hook_name = _validate_hook_name(payload.hook_name)
    target_kind = (payload.target_kind or "queue").strip() or "queue"
    target_ref = payload.target_ref.strip() if payload.target_ref else None
    status = _validate_subscription_status(payload.status)
    subscription_id = _hash(f"hook-subscription:{hook_name}:{target_kind}:{target_ref or ''}:{payload.created_by or ''}:{now}")
    return hook_subscriptions_repo().upsert(
        {
            "id": subscription_id,
            "hook_name": hook_name,
            "target_kind": target_kind,
            "target_ref": target_ref,
            "status": status,
            "created_by": payload.created_by,
            "created_at": now,
            "updated_at": now,
            "metadata": payload.metadata,
        }
    )


def list_hook_subscriptions(
    hook_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return hook_subscriptions_repo().list_recent(limit=limit, hook_name=hook_name, status=status)


def emit_hook_event(payload: HookEventEmit) -> dict[str, Any]:
    now = _now()
    hook_name = _validate_hook_name(payload.hook_name)
    subscription = hook_subscriptions_repo().first_active_for_hook(hook_name)
    status = "queued" if subscription else "no_subscriber"
    event_id = _hash(
        f"hook-event:{hook_name}:{subscription['id'] if subscription else ''}:{payload.source_kind}:{payload.source_id or ''}:{payload.payload}:{now}"
    )
    metadata = dict(payload.metadata or {})
    if subscription:
        metadata.setdefault(
            "subscription",
            {
                "target_kind": subscription.get("target_kind"),
                "target_ref": subscription.get("target_ref"),
            },
        )
    return hook_events_repo().upsert(
        {
            "id": event_id,
            "hook_name": hook_name,
            "subscription_id": subscription["id"] if subscription else None,
            "source_kind": payload.source_kind or "manual",
            "source_id": payload.source_id,
            "payload": payload.payload,
            "status": status,
            "created_at": now,
            "dispatched_at": None,
            "metadata": metadata,
        }
    )


def list_hook_events(
    hook_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return hook_events_repo().list_recent(limit=limit, hook_name=hook_name, status=status)


def mark_hook_event_dispatched(event_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    event = hook_events_repo().get(event_id)
    if not event:
        raise ValueError("hook event not found")
    now = _now()
    merged_metadata = {**(event.get("metadata") or {}), **(metadata or {})}
    return hook_events_repo().upsert(
        {
            **event,
            "status": "dispatched",
            "dispatched_at": now,
            "metadata": merged_metadata,
        }
    )
