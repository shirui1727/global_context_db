from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.schemas import HookEventEmit, HookSubscriptionCreate
from app.main import app
from app.storage.bootstrap import bootstrap, reset_bootstrap


@pytest.fixture()
def hook_env(tmp_path: Path):
    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
        "asset_allow_prefixes": settings.asset_allow_prefixes,
        "asset_deny_prefixes": settings.asset_deny_prefixes,
        "api_key": settings.api_key,
        "require_mcp_api_key": settings.require_mcp_api_key,
    }
    settings.data_dir = tmp_path / "data"
    settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
    settings.lancedb_dir = settings.data_dir / "lancedb"
    settings.asset_allow_prefixes = ""
    settings.asset_deny_prefixes = ""
    settings.api_key = None
    settings.require_mcp_api_key = False
    reset_bootstrap()
    bootstrap(settings)
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_hook_subscription_and_event_queue(hook_env):
    from app.hooks.service import (
        create_hook_subscription,
        emit_hook_event,
        list_hook_events,
        mark_hook_event_dispatched,
    )

    subscription = create_hook_subscription(
        HookSubscriptionCreate(
            hook_name="memory.created",
            target_ref="openclaw-worker",
            created_by="tester",
            metadata={"purpose": "notify-worker"},
        )
    )
    event = emit_hook_event(
        HookEventEmit(
            hook_name="memory.created",
            source_kind="memory",
            source_id="mem-1",
            payload={"memory_id": "mem-1"},
        )
    )
    listed = list_hook_events(hook_name="memory.created", status="queued")
    dispatched = mark_hook_event_dispatched(event["id"], metadata={"worker": "openclaw-worker"})

    assert subscription["status"] == "active"
    assert subscription["target_kind"] == "queue"
    assert event["status"] == "queued"
    assert event["subscription_id"] == subscription["id"]
    assert listed[0]["id"] == event["id"]
    assert dispatched["status"] == "dispatched"
    assert dispatched["metadata"]["worker"] == "openclaw-worker"


def test_hook_event_without_subscription_is_recorded(hook_env):
    from app.hooks.service import emit_hook_event, list_hook_events

    event = emit_hook_event(
        HookEventEmit(
            hook_name="asset.analyzed",
            source_kind="asset",
            source_id="asset-1",
            payload={"asset_id": "asset-1"},
        )
    )
    listed = list_hook_events(hook_name="asset.analyzed")

    assert event["status"] == "no_subscriber"
    assert event["subscription_id"] is None
    assert listed[0]["id"] == event["id"]


def test_hook_rest_and_mcp_surfaces(hook_env):
    client = TestClient(app)
    subscription_response = client.post(
        "/hooks/subscriptions",
        json={"hook_name": "feedback.planned", "target_ref": "review-queue", "created_by": "rest-test"},
    )
    event_response = client.post(
        "/hooks/events",
        json={
            "hook_name": "feedback.planned",
            "source_kind": "memory_feedback",
            "source_id": "feedback-1",
            "payload": {"feedback_id": "feedback-1"},
        },
    )
    events_response = client.get("/hooks/events", params={"hook_name": "feedback.planned"})
    dispatch_response = client.post(f"/hooks/events/{event_response.json()['id']}/dispatch", json={"reviewed": True})

    from app.mcp_server import (
        gcd_create_hook_subscription,
        gcd_emit_hook_event,
        gcd_list_hook_events,
        gcd_list_hook_subscriptions,
        gcd_mark_hook_event_dispatched,
    )

    mcp_subscription = gcd_create_hook_subscription(
        hook_name="session.ended",
        target_ref="summary-worker",
        created_by="mcp-test",
    )
    mcp_event = gcd_emit_hook_event(
        hook_name="session.ended",
        source_kind="session",
        source_id="session-1",
        payload={"session_id": "session-1"},
    )
    mcp_dispatched = gcd_mark_hook_event_dispatched(mcp_event["id"], metadata={"worker": "summary-worker"})

    assert subscription_response.status_code == 200
    assert event_response.status_code == 200
    assert events_response.status_code == 200
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["status"] == "dispatched"
    assert mcp_subscription["status"] == "active"
    assert gcd_list_hook_subscriptions(hook_name="session.ended")[0]["id"] == mcp_subscription["id"]
    assert gcd_list_hook_events(hook_name="session.ended")[0]["id"] == mcp_event["id"]
    assert mcp_dispatched["status"] == "dispatched"
