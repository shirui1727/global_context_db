from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_RETRIEVAL_EVAL_CASES: list[dict[str, Any]] = [
    {"query": "deterministic handoff summaries resume context", "expected_domain": "memory", "metadata": {"category": "memory_lifecycle"}},
    {"query": "manual feedback action applies memory correction", "expected_domain": "memory", "metadata": {"category": "feedback"}},
    {"query": "reader evidence span source quote hash", "expected_domain": "memory", "metadata": {"category": "reader"}},
    {"query": "context cube readable shared kb memories", "expected_domain": "memory", "metadata": {"category": "cubes"}},
    {"query": "writable cube ids fan out memory writes", "expected_domain": "memory", "metadata": {"category": "cubes"}},
    {"query": "memory promotion proposal session event evidence", "expected_domain": "memory", "metadata": {"category": "promotion"}},
    {"query": "low evidence stale conflicting memory quality", "expected_domain": "memory", "metadata": {"category": "quality"}},
    {"query": "NAS asset manifest thumbnail keyframe artifact", "expected_domain": "asset", "metadata": {"category": "asset_manifest"}},
    {"query": "asset analysis manifest OCR ASR scene summary", "expected_domain": "asset", "metadata": {"category": "asset_manifest"}},
    {"query": "scan run missing NAS asset locations", "expected_domain": "asset", "metadata": {"category": "asset_scan"}},
    {"query": "asset writable cube ids separate cube scoped assets", "expected_domain": "asset", "metadata": {"category": "asset_cubes"}},
    {"query": "asset status stale failed pending analysis status", "expected_domain": "asset", "metadata": {"category": "asset_governance"}},
    {"query": "document chunk ingestion retrieval eval budget", "expected_domain": "document", "metadata": {"category": "document"}},
    {"query": "captured web document beautifulsoup text preview", "expected_domain": "document", "metadata": {"category": "capture"}},
    {"query": "session tool trace failed error redacted", "expected_domain": "session", "metadata": {"category": "session"}},
    {"query": "session pre compact handoff current focus", "expected_domain": "session", "metadata": {"category": "session"}},
    {"query": "agent hook session end event", "expected_domain": "session", "metadata": {"category": "hooks"}},
    {"query": "scheduler pending running lease retry", "expected_domain": "memory", "metadata": {"category": "scheduler"}},
    {"query": "hook subscription queued no subscriber dispatched", "expected_domain": "memory", "metadata": {"category": "hooks"}},
    {"query": "diagnostics pending promotion high risk audit", "expected_domain": "memory", "metadata": {"category": "diagnostics"}},
]


def build_project_retrieval_eval_cases() -> list[dict[str, Any]]:
    return [dict(case) for case in PROJECT_RETRIEVAL_EVAL_CASES]


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    if path is None:
        return build_project_retrieval_eval_cases()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("retrieval eval fixture must be a JSON list")
    return [dict(item) for item in data]


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Global Context DB retrieval eval fixture cases as JSON.")
    parser.add_argument("--input", type=Path, default=None, help="Optional JSON fixture file to normalize.")
    args = parser.parse_args()
    print(json.dumps(load_cases(args.input), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
