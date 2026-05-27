from pathlib import Path

import pytest

from app.core.config import settings
from app.core.schemas import MemoryCreate, MemoryPromotionCreate, MemoryPromotionReview
from app.memory.service import (
    add_memory,
    create_memory_candidate_from_reader,
    create_memory_promotion,
    delete_memory,
    list_memory_candidates,
    list_memory_lifecycle_events,
    promote_memory_candidate,
    review_memory_promotion,
    update_memory,
)
from app.reader.service import read_text_fast, reader_item_to_memory_candidate
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import db_counts, memories_repo
from app.core.schemas import MemoryUpdate


@pytest.fixture()
def lifecycle_env(tmp_path: Path):
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


def test_add_memory_records_created_lifecycle_event(lifecycle_env):
    memory = add_memory(
        MemoryCreate(
            cube_id="cube-lifecycle",
            content="Lifecycle-created memory is durable.",
            tags=["lifecycle"],
            agent_id="codex",
        )
    )["memory"]

    counts = db_counts()
    events = list_memory_lifecycle_events(memory["id"])

    assert "memory_lifecycle_events" in counts
    assert "memory_candidates" in counts
    assert events[0]["event_kind"] == "created"
    assert events[0]["from_status"] is None
    assert events[0]["to_status"] == "active"
    assert events[0]["actor"] == "codex"


def test_update_archive_and_delete_record_lifecycle_events(lifecycle_env):
    memory = add_memory(
        MemoryCreate(
            content="Lifecycle memory before correction.",
            tags=["lifecycle"],
            agent_id="codex",
        )
    )["memory"]

    update_memory(memory["id"], MemoryUpdate(content="Lifecycle memory after correction."))
    update_memory(memory["id"], MemoryUpdate(status="archived", metadata={"archive_reason": "obsolete"}))
    delete_memory(memory["id"])

    events = list_memory_lifecycle_events(memory["id"], limit=10)
    event_kinds = [event["event_kind"] for event in events]

    assert event_kinds[:4] == ["deleted", "archived", "corrected", "created"]
    assert events[0]["from_status"] == "archived"
    assert events[0]["to_status"] == "deleted"
    assert events[1]["from_status"] == "active"
    assert events[1]["to_status"] == "archived"


def test_reader_item_can_be_saved_as_candidate_and_promoted(lifecycle_env):
    reader_item = read_text_fast(
        source="session-note",
        text="Candidate memory from reader should wait for review.",
        cube_id="cube-reader",
        tags=["reader", "candidate"],
        metadata={"source_domain": "session_event", "source_id": "event-1"},
    )
    normalized = reader_item_to_memory_candidate(reader_item, created_by="reader-fast")

    candidate = create_memory_candidate_from_reader(reader_item, created_by="reader-fast")
    listed = list_memory_candidates(status="candidate")
    promoted = promote_memory_candidate(candidate["id"], reviewed_by="reviewer")
    memory = memories_repo().get(promoted["memory_id"])
    events = list_memory_lifecycle_events(promoted["memory_id"], limit=10)

    assert normalized["status"] == "candidate"
    assert candidate["status"] == "candidate"
    assert candidate["cube_id"] == "cube-reader"
    assert candidate["source_domain"] == "session_event"
    assert candidate["source_id"] == "event-1"
    assert listed[0]["id"] == candidate["id"]
    assert promoted["candidate"]["status"] == "active"
    assert promoted["candidate"]["promoted_memory_id"] == promoted["memory_id"]
    assert memory["source_kind"] == "reader_candidate"
    assert "promoted" in [event["event_kind"] for event in events]


def test_review_memory_promotion_records_promoted_lifecycle_event(lifecycle_env):
    proposal = create_memory_promotion(
        MemoryPromotionCreate(
            source_session_id="session-1",
            source_event_ids=["event-1"],
            proposed_content="Promoted session insight becomes lifecycle-tracked memory.",
            tags=["promotion"],
            agent_id="codex",
            created_by="tester",
        )
    )

    reviewed = review_memory_promotion(
        proposal["id"],
        MemoryPromotionReview(action="promote", reviewed_by="reviewer", status_on_memory="active"),
    )
    memory_id = reviewed["memory"]["memory_id"]
    events = list_memory_lifecycle_events(memory_id, limit=10)

    assert events[0]["event_kind"] == "promoted"
    assert events[0]["from_status"] == "candidate"
    assert events[0]["to_status"] == "active"
    assert events[0]["actor"] == "reviewer"
