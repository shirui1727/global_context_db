from pathlib import Path

import pytest

from app.assets.service import create_asset
from app.control.service import recall, remember
from app.core.config import settings
from app.core.schemas import (
    AssetCreate,
    IngestRequest,
    MemoryCreate,
    MemoryPromotionCreate,
    MemoryPromotionReview,
    RecallRequest,
    RememberRequest,
    SessionCreate,
    SessionEventCreate,
    SessionTraceCreate,
)
from app.memory.service import (
    add_memory,
    create_memory_promotion,
    enqueue_memory_quality_improvements,
    list_memory_evidence,
    list_memory_promotions,
    memory_quality_report,
    review_memory_promotion,
)
from app.retrieval.service import run_retrieval_eval, search_context
from app.ingest.pipeline import ingest_text
from app.improvements.service import list_improvement_tasks, run_improve
from app.core.schemas import ImproveRequest
from app.sessions.service import add_session_event, add_session_trace, create_session, get_resume_context
from app.core.schemas import ResumeContextRequest
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import db_counts


@pytest.fixture()
def v03_env(tmp_path: Path):
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


def test_session_events_traces_and_resume_context(v03_env):
    session = create_session(
        SessionCreate(source_agent="codex", project_path="S:/project/a", title="v0.3 work", summary="building session layer")
    )
    event = add_session_event(
        session["id"],
        SessionEventCreate(event_type="user_prompt", role="user", content="continue v0.3 session layer"),
    )
    trace = add_session_trace(
        session["id"],
        SessionTraceCreate(origin_function="pytest", status="ok", feedback_text="tests are being added"),
    )

    resume = get_resume_context(ResumeContextRequest(session_id=session["id"], query="v0.3 session", top_k=5))
    assert resume["session"]["id"] == session["id"]
    assert resume["handoff"]["current_focus"] == "continue v0.3 session layer"
    assert "pytest" in resume["handoff"]["tools_used"]
    assert any(item["id"] == event["id"] for item in resume["recent_events"])
    assert trace["session_id"] == session["id"]
    assert "session" in recall(RecallRequest(query="tests are being added", top_k=5))["groups"]


def test_resume_context_budget_and_secret_redaction(v03_env):
    session = create_session(SessionCreate(source_agent="codex", project_path="S:/project/secret"))
    event = add_session_event(
        session["id"],
        SessionEventCreate(
            event_type="tool_call",
            role="tool",
            content="authorization: Bearer should-not-leak",
            tool_name="curl",
            tool_args={"headers": {"authorization": "Bearer should-not-leak"}, "nested": {"api_key": "secret-key"}},
        ),
    )
    trace = add_session_trace(
        session["id"],
        SessionTraceCreate(
            origin_function="curl",
            status="failed",
            method_params={"token": "secret-token", "query": "visible"},
            method_return_value={"password": "secret-password", "ok": False},
            error_message="token=secret-token failed",
        ),
    )

    hidden = get_resume_context(
        ResumeContextRequest(
            session_id=session["id"],
            query="secret",
            include_raw_events=False,
            context_budget_chars=1000,
        )
    )
    visible = get_resume_context(
        ResumeContextRequest(
            session_id=session["id"],
            query="secret",
            include_raw_events=True,
            context_budget_chars=1000,
        )
    )

    assert hidden["recent_events"] == []
    assert visible["budget"]["requested_chars"] == 1000
    assert visible["recent_events"][1]["tool_args"]["headers"]["authorization"] == "[REDACTED]"
    assert visible["recent_events"][1]["tool_args"]["nested"]["api_key"] == "[REDACTED]"
    assert "should-not-leak" not in visible["recent_events"][1]["content"]
    assert trace["method_params"]["token"] == "[REDACTED]"
    assert trace["method_return_value"]["password"] == "[REDACTED]"
    assert event["tool_args"]["nested"]["api_key"] == "[REDACTED]"


def test_resume_context_formats_are_distinct(v03_env):
    session = create_session(
        SessionCreate(source_agent="codex", project_path="S:/project/formats", title="format work", summary="format summary")
    )
    add_session_event(
        session["id"],
        SessionEventCreate(event_type="user_prompt", role="user", content="tighten resume context formats"),
    )
    add_session_event(
        session["id"],
        SessionEventCreate(event_type="assistant_note", role="assistant", content="handoff keeps structured progress"),
    )

    raw = get_resume_context(
        ResumeContextRequest(session_id=session["id"], query="resume context formats", format="raw", include_raw_events=True)
    )
    brief = get_resume_context(
        ResumeContextRequest(session_id=session["id"], query="resume context formats", format="brief", include_raw_events=True)
    )

    assert raw["format"] == "raw"
    assert len(raw["recent_events"]) >= 2
    assert brief["format"] == "brief"
    assert brief["recent_events"] == []
    assert brief["open_tasks"] == []
    assert brief["relevant_memories"] == []
    assert brief["summary"]["recent_event_count"] >= 2


def test_resume_context_rejects_unknown_format(v03_env):
    with pytest.raises(ValueError, match="format must be one of"):
        get_resume_context(ResumeContextRequest(format="verbose"))

def test_asset_version_change_creates_improvement_tasks(v03_env):
    first = create_asset(AssetCreate(uri="smb://NAS/photos/a.jpg", asset_key="photo:a", checksum="sha-a"))
    changed = create_asset(AssetCreate(uri="smb://NAS/photos/a.jpg", asset_key="photo:a", checksum="sha-b"))

    tasks = list_improvement_tasks(target_domain="asset", target_id=first["id"])
    kinds = {task["task_kind"] for task in tasks}
    assert changed["version_changed"] is True
    assert {"reindex_asset", "refresh_asset_artifacts"} <= kinds


def test_remember_recall_and_improve(v03_env):
    remembered = remember(
        RememberRequest(
            content_type="memory",
            content="v0.3 prefers deterministic resume context",
            tags=["v03"],
            agent_id="codex",
        )
    )
    recalled = recall(RecallRequest(query="deterministic resume", top_k=5))
    improved = run_improve(ImproveRequest(task_kind="rebuild_vectors", target_domain="system", target_id="all", execute=True))

    assert remembered["result"]["status"] == "created"
    assert recalled["groups"]["memory"]
    assert improved["ok"] is True
    assert improved["task"]["status"] == "done"


def test_memory_promotion_creates_memory_with_evidence(v03_env):
    session = create_session(SessionCreate(source_agent="codex", project_path="S:/project/memory-quality"))
    event = add_session_event(
        session["id"],
        SessionEventCreate(
            event_type="assistant_note",
            role="assistant",
            content="Decision: session events must be promoted through proposals before becoming long-term memory.",
        ),
    )
    proposal = create_memory_promotion(
        MemoryPromotionCreate(
            source_session_id=session["id"],
            source_event_ids=[event["id"]],
            proposed_content="Session events must be promoted through proposals before becoming long-term memory.",
            tags=["memory-quality"],
            agent_id="codex",
            project_path="S:/project/memory-quality",
            reason="confirmed architecture decision",
        )
    )
    reviewed = review_memory_promotion(
        proposal["id"],
        MemoryPromotionReview(action="approve", reviewed_by="tester", trust_level="verified"),
    )
    memory_id = reviewed["memory"]["memory_id"]
    evidence = list_memory_evidence(memory_id)

    assert reviewed["proposal"]["status"] == "promoted"
    assert reviewed["proposal"]["promoted_memory_id"] == memory_id
    assert evidence[0]["source_domain"] == "session_event"
    assert evidence[0]["source_id"] == event["id"]


def test_memory_quality_report_flags_low_evidence_stale_and_conflicts(v03_env):
    low = add_memory(
        MemoryCreate(
            content="Use deterministic handoff for resume context.",
            tags=["quality"],
            agent_id="codex",
            trust_level="agent_inferred",
        )
    )
    stale = add_memory(
        MemoryCreate(
            content="Temporary direction expired yesterday.",
            tags=["quality"],
            agent_id="codex",
            metadata={"valid_until": "2000-01-01T00:00:00+00:00", "stale_reason": "test expiry"},
        )
    )
    add_memory(
        MemoryCreate(
            content="We should enable raw session events by default.",
            tags=["conflict"],
            agent_id="codex",
        )
    )
    add_memory(
        MemoryCreate(
            content="We should not enable raw session events by default.",
            tags=["conflict"],
            agent_id="codex",
        )
    )

    report = memory_quality_report(limit=20)
    assert any(item["memory_id"] == low["memory_id"] for item in report["low_evidence"])
    assert any(item["memory_id"] == stale["memory_id"] for item in report["stale"])
    assert report["summary"]["status_counts"]["active"] >= 4
    assert report["summary"]["trust_level_counts"]["agent_inferred"] == 1
    assert any("stale_reason=test expiry" in item["reasons"] for item in report["stale"])
    assert all(item["evidence_count"] == 0 for item in report["low_evidence"])
    assert report["conflicts"]


def test_memory_quality_candidates_can_be_enqueued_as_improvement_tasks(v03_env):
    low = add_memory(
        MemoryCreate(
            content="Low evidence memory should be verified before reuse.",
            tags=["queue-quality"],
            agent_id="codex",
            trust_level="agent_inferred",
        )
    )
    stale = add_memory(
        MemoryCreate(
            content="Expired memory should be refreshed.",
            tags=["queue-quality"],
            agent_id="codex",
            metadata={"valid_until": "2000-01-01T00:00:00+00:00"},
        )
    )
    add_memory(MemoryCreate(content="We should enable queue conflicts.", tags=["queue-conflict"], agent_id="codex"))
    add_memory(MemoryCreate(content="We should not enable queue conflicts.", tags=["queue-conflict"], agent_id="codex"))

    result = enqueue_memory_quality_improvements(limit=20, created_by="tester")
    tasks = list_improvement_tasks(target_domain="memory")
    task_kinds = {task["task_kind"] for task in tasks}

    assert result["created_count"] >= 3
    assert {"verify_memory_evidence", "refresh_stale_memory", "resolve_memory_conflict"} <= task_kinds
    assert any(task["target_id"] == low["memory_id"] for task in tasks)
    assert any(task["target_id"] == stale["memory_id"] for task in tasks)


def test_retrieval_eval_scores_expected_domain_hits(v03_env):
    add_memory(
        MemoryCreate(
            content="Resume context must use deterministic handoff summaries.",
            tags=["eval-memory"],
            agent_id="codex",
        )
    )
    ingest_text(
        IngestRequest(
            source="eval-doc",
            text="Manifest scan runs mark missing NAS asset locations when files are absent.",
        )
    )
    asset = create_asset(
        AssetCreate(
            uri="smb://NAS/photos/eval.jpg",
            asset_key="photo:eval",
            checksum="sha-eval",
            summary="Keyframe artifact registration tracks visual derivatives.",
            tags=["eval-asset"],
        )
    )

    report = run_retrieval_eval(
        [
            {
                "query": "deterministic handoff summaries",
                "expected_domain": "memory",
                "expected_id": None,
            },
            {
                "query": "manifest missing NAS locations",
                "expected_domain": "document",
                "expected_id": None,
            },
            {
                "query": "visual derivatives keyframe artifact",
                "expected_domain": "asset",
                "expected_id": asset["id"],
            },
        ],
        top_k=5,
    )

    assert report["summary"]["total"] == 3
    assert report["summary"]["domain_hits"] == 3
    assert report["summary"]["id_hits"] == 1
    assert all(case["domain_hit"] for case in report["cases"])


def test_search_and_recall_apply_context_budget(v03_env):
    add_memory(
        MemoryCreate(
            content=("budget token " * 140).strip(),
            tags=["budget"],
            agent_id="codex",
        )
    )
    add_memory(
        MemoryCreate(
            content=("budget second " * 140).strip(),
            tags=["budget"],
            agent_id="codex",
        )
    )

    searched = search_context("budget", top_k=5, context_budget_chars=1000)
    recalled = recall(RecallRequest(query="budget", top_k=5, context_budget_chars=1000))

    assert searched["budget"]["requested_chars"] == 1000
    assert searched["budget"]["used_chars"] <= 1000
    assert searched["budget"]["truncated"] is True
    assert len(searched["groups"]["memory"]) == 1
    assert recalled["budget"]["used_chars"] <= 1000


def test_v03_tables_are_counted(v03_env):
    counts = db_counts()
    assert "agent_sessions" in counts
    assert "session_events" in counts
    assert "improvement_tasks" in counts
    assert "memory_evidence" in counts
    assert "memory_promotion_proposals" in counts


def test_improve_promote_session_memory_creates_promotion_proposal(v03_env):
    session = create_session(
        SessionCreate(source_agent="codex", project_path="S:/project/auto-promote", title="auto promote")
    )
    note = add_session_event(
        session["id"],
        SessionEventCreate(
            event_type="assistant_note",
            role="assistant",
            content="Decision: asset manifests should be registered before vector rebuild runs.",
        ),
    )

    improved = run_improve(
        ImproveRequest(
            task_kind="promote_session_memory",
            target_domain="session",
            target_id=session["id"],
            execute=True,
            created_by="tester",
        )
    )
    proposals = list_memory_promotions(source_session_id=session["id"])

    assert improved["ok"] is True
    assert improved["task"]["status"] == "done"
    assert improved["result"]["proposal"]["source_session_id"] == session["id"]
    assert note["id"] in improved["result"]["proposal"]["source_event_ids"]
    assert proposals[0]["id"] == improved["result"]["proposal"]["id"]


def test_improve_summarize_session_creates_summary(v03_env):
    session = create_session(
        SessionCreate(
            source_agent="codex",
            project_path="S:/project/auto-summary",
            title="summary target",
            summary="working on automatic summaries",
        )
    )
    add_session_event(
        session["id"],
        SessionEventCreate(event_type="user_prompt", role="user", content="summarize the latest progress"),
    )
    add_session_event(
        session["id"],
        SessionEventCreate(
            event_type="assistant_note",
            role="assistant",
            content="Implemented deterministic improvement executors for session workflows.",
        ),
    )

    improved = run_improve(
        ImproveRequest(
            task_kind="summarize_session",
            target_domain="session",
            target_id=session["id"],
            execute=True,
            created_by="tester",
        )
    )
    refreshed = get_resume_context(ResumeContextRequest(session_id=session["id"], query="automatic summaries", top_k=5))

    assert improved["ok"] is True
    assert improved["task"]["status"] == "done"
    assert improved["result"]["summary"]["summary_kind"] == "improvement_summary"
    assert "Implemented deterministic improvement executors" in improved["result"]["summary"]["content"]
    assert refreshed["session"]["summaries"][0]["id"] == improved["result"]["summary"]["id"]

