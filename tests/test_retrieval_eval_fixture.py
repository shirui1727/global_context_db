from pathlib import Path

from tools.retrieval_eval_fixture import build_project_retrieval_eval_cases, load_cases


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
