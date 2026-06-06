from pathlib import Path

import pytest

from tools.retrieval_eval_fixture import (
    build_project_retrieval_eval_cases,
    load_cases,
    summarize_cases,
    validate_cases,
)


def test_project_retrieval_eval_fixture_has_nas_acceptance_coverage():
    cases = build_project_retrieval_eval_cases()

    assert len(cases) >= 20
    domains = {case["expected_domain"] for case in cases}
    assert {"memory", "document", "asset", "session"} <= domains
    assert all(case["query"] for case in cases)
    assert all("category" in case["metadata"] for case in cases)


def test_project_retrieval_eval_fixture_loads_json_file(tmp_path: Path):
    fixture = tmp_path / "cases.json"
    fixture.write_text(
        '[{"query":"find asset","expected_domain":"asset","expected_id":"asset-1"}]',
        encoding="utf-8",
    )

    cases = load_cases(fixture)

    assert cases == [{"query": "find asset", "expected_domain": "asset", "expected_id": "asset-1"}]


def test_retrieval_eval_fixture_validation_reports_required_coverage():
    cases = build_project_retrieval_eval_cases()

    summary = validate_cases(cases)

    assert summary["ok"] is True
    assert summary["case_count"] >= 30
    assert set(summary["domains"]) >= {"memory", "document", "asset", "session"}
    assert set(summary["categories"]) >= {
        "memory_lifecycle",
        "feedback",
        "reader",
        "cubes",
        "promotion",
        "quality",
        "asset_manifest",
        "asset_scan",
        "asset_cubes",
        "asset_governance",
        "document",
        "capture",
        "session",
        "hooks",
        "scheduler",
        "diagnostics",
    }
    assert summary["errors"] == []


def test_retrieval_eval_fixture_validation_rejects_missing_domain():
    with pytest.raises(ValueError, match="expected_domain"):
        validate_cases([{"query": "missing domain", "metadata": {"category": "broken"}}])


def test_retrieval_eval_fixture_summary_is_bounded_and_deterministic():
    cases = build_project_retrieval_eval_cases()

    summary = summarize_cases(cases)

    assert summary["case_count"] == len(cases)
    assert summary["domains"] == sorted(summary["domains"])
    assert summary["categories"] == sorted(summary["categories"])
