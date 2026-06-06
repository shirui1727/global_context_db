# Global Context DB Roadmap Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the long roadmap after the completed MemOS maturity, runtime acceptance, field acceptance, ops diagnostics, and ops report governance slices by delivering evidence-backed retrieval evaluation, feedback governance, asset manifest versioning, session recovery reporting, hygiene/relation governance, client smoke hardening, and final release acceptance gates.

**Architecture:** Keep the current NAS-first, diagnostics-first, SQLite-first, human-review-first architecture. Each slice adds bounded scripts, docs, tests, and package/acceptance gates before considering heavier dependencies. Redis, dashboard/subgraph, LLM planner, and ACL remain explicitly untriggered unless real evidence later satisfies the trigger records.

**Tech Stack:** Python 3, FastAPI/TestClient, SQLite repositories, PowerShell operational scripts, pytest, compileall, NAS overlay packaging scripts, Markdown runbooks.

---

## Current baseline and operating rules

**Repository root:** `S:\项目开发\全局数据库\global_context_db`

**Current known state before executing this plan:**

- Branch: `main`
- Local branch may still be ahead of `origin/main` by `6f336ea chore: add ops report governance slice`.
- Do not use destructive git commands.
- Do not modify AiMaMi proxy, relay, local agent, or auth configuration.
- Prefer Windows PowerShell commands.
- Before claiming any slice is complete, run the exact verification commands listed in that slice.

**Completed foundation:**

- `docs/superpowers/plans/2026-05-27-memos-maturity-rebuild.md`: 45 tasks, complete.
- `docs/superpowers/plans/2026-06-05-runtime-acceptance-hardening.md`: 5 tasks, complete.
- `docs/superpowers/plans/2026-06-06-field-acceptance-first-use-loop.md`: 7 tasks, complete.
- `docs/superpowers/plans/2026-06-06-long-roadmap.md`: long roadmap plus first executable ops diagnostics slice.
- Ops report governance slice exists locally and should be pushed before major new commits when network allows.

**Non-triggered heavy dependencies:**

- Redis Streams: not triggered.
- Dashboard/subgraph UI: not triggered.
- LLM feedback planner: not triggered.
- ACL/user-manager: not triggered.

---

## File responsibility map

### Retrieval evaluation slice

- Modify: `tools/retrieval_eval_fixture.py`
  - Owns canonical project retrieval eval cases.
  - Adds case validation and coverage summary helpers.
- Modify: `tests/test_retrieval_eval_fixture.py`
  - Tests fixture shape, domain coverage, category coverage, duplicate query rejection, and JSON fixture loading.
- Create: `scripts/run-retrieval-eval-fixture-check.ps1`
  - Runs fixture validation and writes a bounded JSON summary.
- Create: `docs/ops/retrieval-eval-report-template.md`
  - Manual report template for retrieval eval runs and release-gate decisions.

### Feedback governance slice

- Modify: `app/memory/feedback_service.py`
  - Adds a read-only governance summary helper.
  - Must not auto-apply feedback or call an LLM.
- Modify: `tests/test_memory_feedback.py`
  - Tests deterministic planner summary, status counts, action counts, and `llm_used = false`.
- Create: `scripts/export-feedback-review.ps1`
  - Calls REST endpoints and exports reviewable feedback/actions JSON.
- Create: `scripts/report-feedback-governance.ps1`
  - Produces a Markdown governance report from exported JSON.
- Create: `docs/ops/feedback-governance-report-template.md`
  - Defines acceptance-rate and deterministic failure-mode reporting.

### Asset manifest schema/version slice

- Modify: `tools/media_manifest_worker.py`
  - Adds manifest version metadata to scan item, scan run, and analysis manifest payloads.
  - Keeps original NAS files outside the database.
- Modify: `tests/test_media_manifest_worker.py`
  - Tests manifest version fields and artifact payload shape.
- Create: `docs/asset-manifest-schema.md`
  - Documents scan item, scan run, analysis manifest, artifact, and worker contract metadata.
- Modify: `docs/external-worker-contract.md`
  - References manifest schema and worker versioning requirements.

### Session recovery reporting slice

- Create: `scripts/report-session-recovery.ps1`
  - Produces a Markdown report from exported session JSON.
- Create: `docs/ops/session-recovery-report-template.md`
  - Defines what makes a session recoverable.

### Hygiene and relation governance slice

- Create: `scripts/report-memory-governance.ps1`
  - Produces relation and hygiene status summary from diagnostics JSON.
- Create: `docs/ops/memory-governance-report-template.md`
  - Defines review workflow before graph UI or automated hygiene changes.

### Client ecosystem smoke hardening slice

- Modify: `docs/clients/codex-mcp.md`
- Modify: `docs/clients/openclaw-mcp.md`
- Modify: `docs/mcp-tool-inventory.md`
- Create: `scripts/check-mcp-tool-inventory.ps1`
  - Checks expected diagnostic, read/search, and high-risk MCP tools are documented.
- Create: `docs/ops/client-smoke-report-template.md`
  - Records Codex/OpenClaw/client smoke results without secrets.

### Release and packaging gates

- Modify: `scripts/package-nas-update.ps1`
  - Adds new scripts/docs/tools to required entries.
- Modify: `scripts/verify-nas-package.ps1`
  - Mirrors required entries from package script.
- Modify: `scripts/run-release-acceptance.ps1`
  - Adds new slice sanity checks.
- Create: `docs/releases/2026-06-06-roadmap-completion.md`
  - Release record for the completed roadmap execution package.

---

## Task 0: Synchronize current local commit when network allows

**Files:**
- No file modifications.

- [x] **Step 1: Confirm current branch state**

Run:

```powershell
git status --branch --short
git log -5 --oneline
```

Expected if the previous handoff is still current:

```text
## main...origin/main [ahead 1]
6f336ea chore: add ops report governance slice
b08ba6a chore: add ops diagnostics roadmap slice
```

- [x] **Step 2: Push the already-created ops report governance commit**

Run:

```powershell
git push
```

Expected on success:

```text
... main -> main
```

If GitHub fails with connection reset or port 443 unavailable, capture the exact error, do not change proxy/AiMaMi settings, continue local work, and retry before the next publish point.

- [x] **Step 3: Verify remote head when push succeeds**

Run:

```powershell
git ls-remote origin refs/heads/main
git rev-parse HEAD
```

Expected:

- The SHA from `git rev-parse HEAD` matches the SHA shown by `git ls-remote`.

---

## Task 1: Retrieval eval fixture coverage and validation

**Files:**
- Modify: `tools/retrieval_eval_fixture.py`
- Modify: `tests/test_retrieval_eval_fixture.py`
- Create: `scripts/run-retrieval-eval-fixture-check.ps1`
- Create: `docs/ops/retrieval-eval-report-template.md`

- [x] **Step 1: Write failing tests for retrieval fixture validation**

Append these tests to `tests/test_retrieval_eval_fixture.py`:

```python
import pytest

from tools.retrieval_eval_fixture import summarize_cases, validate_cases


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
```

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
python -m pytest tests\test_retrieval_eval_fixture.py -q
```

Expected:

```text
FAILED ... cannot import name 'summarize_cases'
```

or failure for missing `validate_cases`.

- [x] **Step 3: Add validation and summary helpers**

Add to `tools/retrieval_eval_fixture.py` after `load_cases`:

```python
REQUIRED_DOMAINS = {"memory", "document", "asset", "session"}


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    domains = sorted({case.get("expected_domain", "") for case in cases if case.get("expected_domain")})
    categories = sorted({
        (case.get("metadata") or {}).get("category", "")
        for case in cases
        if (case.get("metadata") or {}).get("category")
    })
    return {
        "case_count": len(cases),
        "domains": domains,
        "categories": categories,
    }


def validate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    seen_queries: set[str] = set()
    for index, case in enumerate(cases):
        query = case.get("query")
        expected_domain = case.get("expected_domain")
        metadata = case.get("metadata") or {}
        if not query:
            errors.append(f"case {index} missing query")
        if not expected_domain:
            errors.append(f"case {index} missing expected_domain")
        if expected_domain and expected_domain not in REQUIRED_DOMAINS:
            errors.append(f"case {index} has unsupported expected_domain: {expected_domain}")
        if not metadata.get("category"):
            errors.append(f"case {index} missing metadata.category")
        if query in seen_queries:
            errors.append(f"case {index} duplicates query: {query}")
        if query:
            seen_queries.add(query)
    summary = summarize_cases(cases)
    for domain in sorted(REQUIRED_DOMAINS - set(summary["domains"])):
        errors.append(f"missing required domain coverage: {domain}")
    if errors:
        raise ValueError("; ".join(errors))
    return {**summary, "ok": True, "errors": []}
```

- [x] **Step 4: Expand fixture to at least 30 cases**

Add these cases to `PROJECT_RETRIEVAL_EVAL_CASES`:

```python
    {"query": "retrieval eval report quality regression baseline", "expected_domain": "memory", "metadata": {"category": "retrieval_eval"}},
    {"query": "feedback governance deterministic planner requires review", "expected_domain": "memory", "metadata": {"category": "feedback"}},
    {"query": "NAS release acceptance package verify blocked entries", "expected_domain": "document", "metadata": {"category": "release"}},
    {"query": "asset manifest version generated by external worker", "expected_domain": "asset", "metadata": {"category": "asset_manifest"}},
    {"query": "session recovery report missing useful summary", "expected_domain": "session", "metadata": {"category": "session_recovery"}},
    {"query": "memory relation index health shared tag supported by duplicate", "expected_domain": "memory", "metadata": {"category": "relations"}},
    {"query": "memory hygiene low evidence stale conflict review proposal", "expected_domain": "memory", "metadata": {"category": "hygiene"}},
    {"query": "MCP client high risk tool inventory smoke checklist", "expected_domain": "document", "metadata": {"category": "client_ecosystem"}},
    {"query": "queue pressure continue sqlite recommendation", "expected_domain": "memory", "metadata": {"category": "scheduler"}},
    {"query": "dashboard trigger review diagnostics too slow evidence", "expected_domain": "document", "metadata": {"category": "dashboard_trigger"}},
```

- [x] **Step 5: Add the fixture check script**

Create `scripts/run-retrieval-eval-fixture-check.ps1`:

```powershell
param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
try {
    if (-not $OutputPath) {
        $OutputPath = Join-Path $RepoRoot "docs\ops\retrieval-eval-fixture-summary.json"
    }
    python -c @"
import json
from pathlib import Path
from tools.retrieval_eval_fixture import build_project_retrieval_eval_cases, validate_cases
summary = validate_cases(build_project_retrieval_eval_cases())
Path(r'$OutputPath').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
"@
}
finally {
    Pop-Location
}
```

- [x] **Step 6: Add retrieval eval report template**

Create `docs/ops/retrieval-eval-report-template.md`:

```markdown
# Retrieval Eval Report

- **Run date:**
- **Commit:**
- **Environment:** local / NAS / other
- **Fixture source:** `tools/retrieval_eval_fixture.py`
- **Case count:**
- **Domains covered:** memory, document, asset, session

## Result summary

| Domain | Cases | Expected hit rate | Actual hit rate | Decision |
| --- | ---: | ---: | ---: | --- |
| memory | | | | |
| document | | | | |
| asset | | | | |
| session | | | | |

## Regressions

| Query | Expected domain | Observed result | Suspected cause | Follow-up |
| --- | --- | --- | --- | --- |

## Release gate decision

- [ ] Baseline only; do not gate release yet.
- [ ] Stable enough to add warning-only gate.
- [ ] Stable enough to add blocking gate.

Do not add a blocking release gate until repeated eval runs show stable data and failures are actionable.
```

- [x] **Step 7: Verify retrieval eval slice**

Run:

```powershell
python -m pytest tests\test_retrieval_eval_fixture.py -q
powershell -ExecutionPolicy Bypass -File scripts\run-retrieval-eval-fixture-check.ps1
```

Expected:

```text
passed
"ok": true
```

- [x] **Step 8: Commit retrieval eval slice**

Run:

```powershell
git add tools\retrieval_eval_fixture.py tests\test_retrieval_eval_fixture.py scripts\run-retrieval-eval-fixture-check.ps1 docs\ops\retrieval-eval-report-template.md docs\ops\retrieval-eval-fixture-summary.json
git commit -m "chore: add retrieval eval governance slice"
```

---

## Task 2: Feedback governance export and report

**Files:**
- Modify: `app/memory/feedback_service.py`
- Modify: `tests/test_memory_feedback.py`
- Create: `scripts/export-feedback-review.ps1`
- Create: `scripts/report-feedback-governance.ps1`
- Create: `docs/ops/feedback-governance-report-template.md`

- [x] **Step 1: Write failing test for feedback governance summary**

Append to `tests/test_memory_feedback.py`:

```python
from app.memory.feedback_service import summarize_memory_feedback_governance


def test_feedback_governance_summary_counts_statuses_and_planner_mode(feedback_env):
    memory = _memory("Feedback governance summary target.")
    feedback = create_memory_feedback(
        MemoryFeedbackCreate(
            feedback_text="Evidence: reviewer confirmed this memory.",
            target_memory_id=memory["id"],
            created_by="tester",
        )
    )
    propose_memory_feedback_actions(feedback["id"], planner="deterministic")

    summary = summarize_memory_feedback_governance(limit=20)

    assert summary["feedback_count"] >= 1
    assert summary["status_counts"]["planned"] >= 1
    assert summary["action_status_counts"]["proposed"] >= 1
    assert summary["planner_modes"]["deterministic"] >= 1
    assert summary["llm_used"] is False
```

- [x] **Step 2: Run focused test and verify it fails**

Run:

```powershell
python -m pytest tests\test_memory_feedback.py::test_feedback_governance_summary_counts_statuses_and_planner_mode -q
```

Expected:

```text
FAILED ... cannot import name 'summarize_memory_feedback_governance'
```

- [x] **Step 3: Implement read-only governance summary helper**

Add to `app/memory/feedback_service.py`:

```python
def summarize_memory_feedback_governance(limit: int = 100) -> dict[str, Any]:
    feedback_rows = list_memory_feedback(limit=limit)
    status_counts: dict[str, int] = {}
    action_status_counts: dict[str, int] = {}
    action_type_counts: dict[str, int] = {}
    planner_modes: dict[str, int] = {}
    for feedback in feedback_rows:
        status = feedback.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        metadata = feedback.get("metadata") or {}
        proposal = metadata.get("proposal") or {}
        mode = proposal.get("mode") or proposal.get("planner")
        if mode:
            planner_modes[mode] = planner_modes.get(mode, 0) + 1
        for action in memory_feedback_actions_repo().list_by_feedback(feedback["id"], limit=100):
            action_status = action.get("status") or "unknown"
            action_type = action.get("action_type") or "unknown"
            action_status_counts[action_status] = action_status_counts.get(action_status, 0) + 1
            action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1
            action_metadata = action.get("metadata") or {}
            action_proposal = action_metadata.get("proposal") or {}
            action_mode = action_proposal.get("mode") or action_proposal.get("planner")
            if action_mode:
                planner_modes[action_mode] = planner_modes.get(action_mode, 0) + 1
    return {
        "feedback_count": len(feedback_rows),
        "status_counts": status_counts,
        "action_status_counts": action_status_counts,
        "action_type_counts": action_type_counts,
        "planner_modes": planner_modes,
        "llm_used": False,
    }
```

- [x] **Step 4: Create feedback export script**

Create `scripts/export-feedback-review.ps1`:

```powershell
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OutputPath = "",
    [int]$Limit = 100
)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) {
    $OutputPath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")) "docs\ops\feedback-review-export.json"
}

function Invoke-GcdJson($Path) {
    Invoke-RestMethod -Method GET -Uri "$BaseUrl$Path"
}

$Feedback = Invoke-GcdJson "/memory-feedback?limit=$Limit"
$Rows = @()
foreach ($Item in $Feedback) {
    $Actions = Invoke-GcdJson "/memory-feedback/$($Item.id)/actions"
    $Rows += [pscustomobject]@{
        feedback = $Item
        actions = $Actions
    }
}

$Payload = [pscustomobject]@{
    exported_at = (Get-Date).ToUniversalTime().ToString("o")
    base_url = $BaseUrl
    limit = $Limit
    feedback_count = $Rows.Count
    rows = $Rows
}
$Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
```

- [x] **Step 5: Create feedback governance report script**

Create `scripts/report-feedback-governance.ps1`:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) {
    $OutputPath = [System.IO.Path]::ChangeExtension($InputPath, ".md")
}
$Data = Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json
$StatusCounts = @{}
$ActionStatusCounts = @{}
foreach ($Row in $Data.rows) {
    $Status = [string]$Row.feedback.status
    if (-not $StatusCounts.ContainsKey($Status)) { $StatusCounts[$Status] = 0 }
    $StatusCounts[$Status] += 1
    foreach ($Action in $Row.actions) {
        $ActionStatus = [string]$Action.status
        if (-not $ActionStatusCounts.ContainsKey($ActionStatus)) { $ActionStatusCounts[$ActionStatus] = 0 }
        $ActionStatusCounts[$ActionStatus] += 1
    }
}
$Lines = @(
    "# Feedback Governance Report",
    "",
    "- **Exported at:** $($Data.exported_at)",
    "- **Feedback count:** $($Data.feedback_count)",
    "- **LLM planner used:** false",
    "",
    "## Feedback status counts"
)
foreach ($Key in ($StatusCounts.Keys | Sort-Object)) {
    $Lines += "- ${Key}: $($StatusCounts[$Key])"
}
$Lines += ""
$Lines += "## Action status counts"
foreach ($Key in ($ActionStatusCounts.Keys | Sort-Object)) {
    $Lines += "- ${Key}: $($ActionStatusCounts[$Key])"
}
$Lines += ""
$Lines += "## Decision"
$Lines += ""
$Lines += "Keep deterministic proposal and human review. Do not start an LLM planner without a real sample corpus and measured review cost."
$Lines | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
```

- [x] **Step 6: Add report template**

Create `docs/ops/feedback-governance-report-template.md`:

```markdown
# Feedback Governance Report

- **Period:**
- **Commit/package:**
- **Feedback sample size:**
- **Planner mode:** deterministic
- **LLM used:** false

## Counts

| Status | Count |
| --- | ---: |
| pending | |
| planned | |
| applied | |
| rejected | |
| failed | |

## Deterministic planner failures

| Feedback id | Failure mode | Manual correction | Should this justify LLM work? |
| --- | --- | --- | --- |

## Decision

- [ ] Continue deterministic planner.
- [ ] Add more marker coverage.
- [ ] Collect more samples before deciding.
- [ ] Start LLM planner design only after sample corpus proves deterministic review cost is too high.
```

- [x] **Step 7: Verify feedback governance slice**

Run:

```powershell
python -m pytest tests\test_memory_feedback.py -q
python -m compileall app tools
```

Expected:

```text
passed
compile success
```

- [x] **Step 8: Commit feedback governance slice**

Run:

```powershell
git add app\memory\feedback_service.py tests\test_memory_feedback.py scripts\export-feedback-review.ps1 scripts\report-feedback-governance.ps1 docs\ops\feedback-governance-report-template.md
git commit -m "chore: add feedback governance reporting slice"
```

---

## Task 3: Asset manifest schema and versioning

**Files:**
- Modify: `tools/media_manifest_worker.py`
- Modify: `tests/test_media_manifest_worker.py`
- Create: `docs/asset-manifest-schema.md`
- Modify: `docs/external-worker-contract.md`

- [x] **Step 1: Write failing tests for manifest version fields**

Append to `tests/test_media_manifest_worker.py`:

```python
def test_scan_item_includes_manifest_version(tmp_path: Path):
    source = tmp_path / "image.png"
    source.write_bytes(b"fake image")

    item = build_scan_item(source, uri_prefix="smb://NAS/images", root=tmp_path)

    assert item["metadata"]["manifest_version"] == "asset-manifest/v1"
    assert item["metadata"]["worker_contract"] == "external-worker/v1"


def test_scan_run_includes_manifest_version(tmp_path: Path):
    (tmp_path / "brief.md").write_text("brief", encoding="utf-8")

    payload = build_scan_run(tmp_path, scope_prefix="smb://NAS/library")

    assert payload["metadata"]["manifest_version"] == "asset-scan-run/v1"
    assert payload["metadata"]["worker_contract"] == "external-worker/v1"


def test_analysis_manifest_includes_manifest_version(tmp_path: Path):
    source = tmp_path / "brief.md"
    source.write_text("brief", encoding="utf-8")

    manifest = build_analysis_manifest(source, "asset-1", "/data/artifacts", tmp_path / "artifacts")

    assert manifest["payload"]["metadata"]["manifest_version"] == "asset-analysis-manifest/v1"
    assert manifest["payload"]["metadata"]["worker_contract"] == "external-worker/v1"
```

- [x] **Step 2: Run focused media tests and verify failure**

Run:

```powershell
python -m pytest tests\test_media_manifest_worker.py -q
```

Expected:

```text
FAILED ... KeyError: 'manifest_version'
```

- [x] **Step 3: Add version constants and metadata fields**

Add near the top of `tools/media_manifest_worker.py`:

```python
SCAN_ITEM_MANIFEST_VERSION = "asset-manifest/v1"
SCAN_RUN_MANIFEST_VERSION = "asset-scan-run/v1"
ANALYSIS_MANIFEST_VERSION = "asset-analysis-manifest/v1"
WORKER_CONTRACT_VERSION = "external-worker/v1"
```

Update `build_scan_item` metadata:

```python
"metadata": {
    "source_path": str(path),
    "relative_path": relative,
    "manifest_version": SCAN_ITEM_MANIFEST_VERSION,
    "worker_contract": WORKER_CONTRACT_VERSION,
},
```

Update `build_scan_run` metadata:

```python
"metadata": {
    "source_root": str(root),
    "generated_by": created_by,
    "observed_count": len(observed),
    "manifest_version": SCAN_RUN_MANIFEST_VERSION,
    "worker_contract": WORKER_CONTRACT_VERSION,
},
```

Update `build_analysis_manifest` payload metadata:

```python
"metadata": {
    "source_path": str(path),
    "asset_kind": asset_kind,
    "manifest_version": ANALYSIS_MANIFEST_VERSION,
    "worker_contract": WORKER_CONTRACT_VERSION,
},
```

- [x] **Step 4: Add schema doc**

Create `docs/asset-manifest-schema.md`:

```markdown
# Asset Manifest Schema

Global Context DB registers asset references, scan results, and derived artifacts. It does not copy original NAS media into the database.

## Versions

| Payload | Version |
| --- | --- |
| Scan item metadata | `asset-manifest/v1` |
| Scan run metadata | `asset-scan-run/v1` |
| Analysis manifest metadata | `asset-analysis-manifest/v1` |
| Worker contract | `external-worker/v1` |

## Artifact rule

Artifacts may include derived text, probe JSON, thumbnails, OCR, ASR, or keyframe references. Original NAS files remain external and must not be copied into `global_context_db/data` or the SQLite database.
```

- [x] **Step 5: Update external worker contract doc**

Add to `docs/external-worker-contract.md`:

```markdown
## Manifest versions

Workers must write versioned payload metadata:

- Scan item: `metadata.manifest_version = asset-manifest/v1`
- Scan run: `metadata.manifest_version = asset-scan-run/v1`
- Analysis manifest: `payload.metadata.manifest_version = asset-analysis-manifest/v1`
- Worker contract: `external-worker/v1`

The schema reference is `docs/asset-manifest-schema.md`. Version fields are operational metadata; they do not authorize copying original NAS files into Global Context DB storage.
```

- [x] **Step 6: Verify asset manifest slice**

Run:

```powershell
python -m pytest tests\test_media_manifest_worker.py -q
python -m compileall tools
```

Expected:

```text
passed
compile success
```

- [x] **Step 7: Commit asset manifest slice**

Run:

```powershell
git add tools\media_manifest_worker.py tests\test_media_manifest_worker.py docs\asset-manifest-schema.md docs\external-worker-contract.md
git commit -m "chore: version asset manifest worker payloads"
```

---

## Task 4: Session recovery report

**Files:**
- Create: `scripts/report-session-recovery.ps1`
- Create: `docs/ops/session-recovery-report-template.md`

- [x] **Step 1: Create session recovery report script**

Create `scripts/report-session-recovery.ps1`:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) {
    $OutputPath = [System.IO.Path]::ChangeExtension($InputPath, ".md")
}
$Data = Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json
$Sessions = @($Data.sessions)
$Recoverable = 0
$NeedsSummary = 0
foreach ($Session in $Sessions) {
    $Summary = [string]$Session.summary
    if ($Summary.Trim().Length -ge 40) {
        $Recoverable += 1
    } else {
        $NeedsSummary += 1
    }
}
$Lines = @(
    "# Session Recovery Report",
    "",
    "- **Generated at:** $((Get-Date).ToUniversalTime().ToString('o'))",
    "- **Session count:** $($Sessions.Count)",
    "- **Recoverable sessions:** $Recoverable",
    "- **Needs summary:** $NeedsSummary",
    "",
    "## Sessions needing summary",
    "",
    "| Session id | Title | Source agent | Last activity | Reason |",
    "| --- | --- | --- | --- | --- |"
)
foreach ($Session in $Sessions) {
    $Summary = [string]$Session.summary
    if ($Summary.Trim().Length -lt 40) {
        $Lines += "| $($Session.id) | $($Session.title) | $($Session.source_agent) | $($Session.last_activity_at) | summary shorter than 40 characters |"
    }
}
$Lines | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
```

- [x] **Step 2: Add session recovery template**

Create `docs/ops/session-recovery-report-template.md`:

```markdown
# Session Recovery Report

- **Period:**
- **Commit/package:**
- **Session sample size:**

## Summary

| Metric | Count |
| --- | ---: |
| Sessions reviewed | |
| Recoverable sessions | |
| Sessions missing useful summary | |
| Sessions missing recent events | |
| Sessions with redaction concern | |

## Sessions needing attention

| Session id | Project | Source agent | Problem | Follow-up |
| --- | --- | --- | --- | --- |

## Recovery quality rule

A session is recoverable when `resume-context` gives enough current focus, recent events, open tasks, and relevant memory/document/asset links for a new agent to continue without asking the user to restate the work.
```

- [x] **Step 3: Verify script with bounded sample**

Run:

```powershell
$tmp = Join-Path $env:TEMP "gcd-session-recovery-sample.json"
@'
{
  "sessions": [
    {"id":"s-1","title":"Good session","source_agent":"codex","last_activity_at":"2026-06-06T00:00:00Z","summary":"This session has enough detail for another agent to continue the implementation safely."},
    {"id":"s-2","title":"Weak session","source_agent":"codex","last_activity_at":"2026-06-06T01:00:00Z","summary":"short"}
  ]
}
'@ | Set-Content -LiteralPath $tmp -Encoding UTF8
powershell -ExecutionPolicy Bypass -File scripts\report-session-recovery.ps1 -InputPath $tmp
```

Expected:

```text
FullName ... gcd-session-recovery-sample.md
```

- [x] **Step 4: Commit session recovery slice**

Run:

```powershell
git add scripts\report-session-recovery.ps1 docs\ops\session-recovery-report-template.md
git commit -m "chore: add session recovery reporting slice"
```

---

## Task 5: Memory hygiene and relation governance report

**Files:**
- Create: `scripts/report-memory-governance.ps1`
- Create: `docs/ops/memory-governance-report-template.md`

- [x] **Step 1: Create memory governance report script**

Create `scripts/report-memory-governance.ps1`:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$DiagnosticsPath,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) {
    $OutputPath = [System.IO.Path]::ChangeExtension($DiagnosticsPath, ".memory-governance.md")
}
$Diagnostics = Get-Content -LiteralPath $DiagnosticsPath -Raw | ConvertFrom-Json
$Memory = $Diagnostics.governance.memory
$Improvement = $Diagnostics.governance.improvement
$Lines = @(
    "# Memory Governance Report",
    "",
    "- **Generated at:** $((Get-Date).ToUniversalTime().ToString('o'))",
    "",
    "## Relation index",
    "",
    "- **Sample count:** $($Memory.relation_index.sample_count)",
    "- **Kind counts:** $($Memory.relation_index.kind_counts | ConvertTo-Json -Compress)",
    "",
    "## Hygiene queue",
    "",
    "- **Pending by queue:** $($Improvement.pending_by_queue | ConvertTo-Json -Compress)",
    "- **Failed by queue:** $($Improvement.failed_by_queue | ConvertTo-Json -Compress)",
    "",
    "## Decision",
    "",
    "Keep relation and hygiene work as reviewable reports/proposals. Do not start graph UI or auto-apply hygiene without repeated operator evidence."
)
$Lines | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
```

- [x] **Step 2: Add governance template**

Create `docs/ops/memory-governance-report-template.md`:

```markdown
# Memory Governance Report

- **Period:**
- **Commit/package:**
- **Diagnostics snapshot:**

## Relation index health

| Relation kind | Count | Useful in recovery/search? | Follow-up |
| --- | ---: | --- | --- |
| shared_tag | | | |
| supported_by | | | |
| duplicate_candidate | | | |

## Hygiene candidates

| Category | Count | Review owner | Action |
| --- | ---: | --- | --- |
| low_evidence | | | |
| stale | | | |
| conflict | | | |

## Escalation decision

- [ ] Keep Markdown/JSON reports.
- [ ] Add REST/MCP read-only summary only.
- [ ] Consider graph/dashboard UI only after repeated triage is too slow in reports.
- [ ] Never auto-apply hygiene without human review.
```

- [x] **Step 3: Verify script against diagnostics sample**

Run with an existing snapshot `diagnostics.json`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\report-memory-governance.ps1 -DiagnosticsPath <path-to-diagnostics.json>
```

Expected:

```text
FullName ... diagnostics.memory-governance.md
```

- [x] **Step 4: Commit memory governance slice**

Run:

```powershell
git add scripts\report-memory-governance.ps1 docs\ops\memory-governance-report-template.md
git commit -m "chore: add memory governance reporting slice"
```

---

## Task 6: MCP client inventory and smoke hardening

**Files:**
- Modify: `docs/clients/codex-mcp.md`
- Modify: `docs/clients/openclaw-mcp.md`
- Modify: `docs/mcp-tool-inventory.md`
- Create: `scripts/check-mcp-tool-inventory.ps1`
- Create: `docs/ops/client-smoke-report-template.md`

- [x] **Step 1: Create inventory check script**

Create `scripts/check-mcp-tool-inventory.ps1`:

```powershell
param(
    [string]$InventoryPath = "docs\mcp-tool-inventory.md"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Path = Join-Path $RepoRoot $InventoryPath
$Text = Get-Content -LiteralPath $Path -Raw
$Required = @(
    "gcd_diagnostics",
    "gcd_scheduler_status",
    "gcd_add_memory",
    "gcd_search_memories",
    "gcd_search_assets",
    "gcd_propose_memory_feedback_actions"
)
$Missing = @()
foreach ($Name in $Required) {
    if ($Text -notmatch [regex]::Escape($Name)) {
        $Missing += $Name
    }
}
if ($Missing.Count -gt 0) {
    throw "MCP inventory missing required tools: $($Missing -join ', ')"
}
[pscustomobject]@{
    Ok = $true
    InventoryPath = $Path
    RequiredCount = $Required.Count
}
```

- [x] **Step 2: Update MCP inventory with risk grouping**

Ensure `docs/mcp-tool-inventory.md` contains:

```markdown
## Read-only diagnostics tools

- `gcd_diagnostics`
- `gcd_scheduler_status`

## Read/search tools

- `gcd_search_memories`
- `gcd_search_assets`

## High-risk write tools

- `gcd_add_memory`
- `gcd_propose_memory_feedback_actions`
```

Keep the existing documented tools; do not remove working inventory content.

- [x] **Step 3: Update client docs**

Add to both `docs/clients/codex-mcp.md` and `docs/clients/openclaw-mcp.md`:

```markdown
## Smoke order

1. Call `gcd_diagnostics`.
2. Call `gcd_scheduler_status`.
3. Run one read-only search.
4. Only then test a high-risk write tool against smoke-tagged data.
5. Do not paste API keys, local secrets, or private raw content into smoke reports.
```

- [x] **Step 4: Add client smoke report template**

Create `docs/ops/client-smoke-report-template.md`:

```markdown
# Client Smoke Report

- **Client:** Codex / OpenClaw / other
- **Date:**
- **Commit/package:**
- **Server URL:**
- **Operator:**

## Checks

| Step | Tool/API | Result | Notes |
| --- | --- | --- | --- |
| Diagnostics | `gcd_diagnostics` | | |
| Scheduler | `gcd_scheduler_status` | | |
| Search | read-only search | | |
| Smoke write | smoke-tagged write only | | |

## Secrets check

- [ ] Report contains no API key.
- [ ] Report contains no private raw file content.
- [ ] Smoke data is tagged and bounded.
```

- [x] **Step 5: Verify MCP inventory slice**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check-mcp-tool-inventory.ps1
```

Expected:

```text
Ok : True
```

- [x] **Step 6: Commit MCP client slice**

Run:

```powershell
git add docs\clients\codex-mcp.md docs\clients\openclaw-mcp.md docs\mcp-tool-inventory.md scripts\check-mcp-tool-inventory.ps1 docs\ops\client-smoke-report-template.md
git commit -m "docs: harden MCP client smoke guidance"
```

---

## Task 7: Wire new slices into package and release acceptance

**Files:**
- Modify: `scripts/package-nas-update.ps1`
- Modify: `scripts/verify-nas-package.ps1`
- Modify: `scripts/run-release-acceptance.ps1`

- [x] **Step 1: Add required package entries**

In both `scripts/package-nas-update.ps1` and `scripts/verify-nas-package.ps1`, add:

```powershell
"global_context_db/scripts/run-retrieval-eval-fixture-check.ps1",
"global_context_db/scripts/export-feedback-review.ps1",
"global_context_db/scripts/report-feedback-governance.ps1",
"global_context_db/scripts/report-session-recovery.ps1",
"global_context_db/scripts/report-memory-governance.ps1",
"global_context_db/scripts/check-mcp-tool-inventory.ps1",
"global_context_db/docs/asset-manifest-schema.md",
"global_context_db/docs/ops/retrieval-eval-report-template.md",
"global_context_db/docs/ops/feedback-governance-report-template.md",
"global_context_db/docs/ops/session-recovery-report-template.md",
"global_context_db/docs/ops/memory-governance-report-template.md",
"global_context_db/docs/ops/client-smoke-report-template.md",
```

- [x] **Step 2: Add release acceptance sanity checks**

In `scripts/run-release-acceptance.ps1`, extend the Python plan sanity block with:

```python
required_roadmap_completion_files = [
    'scripts/run-retrieval-eval-fixture-check.ps1',
    'scripts/export-feedback-review.ps1',
    'scripts/report-feedback-governance.ps1',
    'scripts/report-session-recovery.ps1',
    'scripts/report-memory-governance.ps1',
    'scripts/check-mcp-tool-inventory.ps1',
    'docs/asset-manifest-schema.md',
    'docs/ops/retrieval-eval-report-template.md',
    'docs/ops/feedback-governance-report-template.md',
    'docs/ops/session-recovery-report-template.md',
    'docs/ops/memory-governance-report-template.md',
    'docs/ops/client-smoke-report-template.md',
]
missing_roadmap_completion_files = [path for path in required_roadmap_completion_files if not Path(path).exists()]
if missing_roadmap_completion_files:
    raise SystemExit(f'Missing roadmap-completion executable-slice files: {missing_roadmap_completion_files}')
print(f'Roadmap completion executable slice: {len(required_roadmap_completion_files)} files present')
```

- [x] **Step 3: Add script-level acceptance calls**

In `scripts/run-release-acceptance.ps1`, before `git diff --check`, add:

```powershell
Write-Host "`n== retrieval eval fixture check =="
powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run-retrieval-eval-fixture-check.ps1") -OutputPath (Join-Path $OutputDir "retrieval-eval-fixture-summary.json")

Write-Host "`n== MCP inventory check =="
powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "check-mcp-tool-inventory.ps1")
```

- [x] **Step 4: Verify package scripts**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
```

Expected:

```text
Ok : True
```

- [x] **Step 5: Commit acceptance wiring**

Run:

```powershell
git add scripts\package-nas-update.ps1 scripts\verify-nas-package.ps1 scripts\run-release-acceptance.ps1
git commit -m "chore: gate roadmap completion artifacts"
```

---

## Task 8: Full release acceptance and release record

**Files:**
- Create: `docs/releases/2026-06-06-roadmap-completion.md`
- Modify: `docs/superpowers/plans/2026-06-06-long-roadmap.md`
- Modify: `docs/superpowers/plans/2026-06-06-roadmap-completion-implementation.md` by checking completed boxes if implemented manually.

- [x] **Step 1: Run full release acceptance**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
```

Expected:

```text
pytest passed
compileall passed
NAS package verify Ok=True
Roadmap completion executable slice: 12 files present
acceptance passed
```

- [x] **Step 2: Create release record**

Create `docs/releases/2026-06-06-roadmap-completion.md`:

```markdown
# 2026-06-06 Roadmap Completion Release

- **Package path:** `S:\项目开发\全局数据库\release\global_context_db.zip`
- **Commit:**
- **Acceptance command:** `powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release`

## Included slices

- Retrieval eval fixture coverage and report template.
- Feedback governance export and report scripts.
- Asset manifest schema/versioning.
- Session recovery reporting.
- Memory hygiene and relation governance reporting.
- MCP client inventory and smoke hardening.
- Package and release acceptance gates.

## Explicit non-goals

- Redis Streams not triggered.
- Dashboard/subgraph UI not triggered.
- LLM planner not triggered.
- ACL/user manager not triggered.

## Verification evidence

- pytest:
- compileall:
- NAS package verify:
- retrieval eval fixture check:
- MCP inventory check:
- git diff check:
```

- [x] **Step 3: Update roadmap completion status**

Append to `docs/superpowers/plans/2026-06-06-long-roadmap.md`:

```markdown
## Roadmap completion executable slice

This slice completes the current no-heavy-dependency roadmap pass by adding:

- retrieval eval fixture validation and reporting;
- feedback governance export/reporting;
- asset manifest schema versioning;
- session recovery reporting;
- memory hygiene/relation governance reporting;
- MCP client smoke hardening;
- release/package gates for the new artifacts.

Redis, dashboard/subgraph, LLM planner, and ACL remain untriggered until evidence records justify them.
```

- [x] **Step 4: Verify docs and final diff**

Run:

```powershell
git diff --check
git status --branch --short
```

Expected:

```text
no diff --check output
```

- [x] **Step 5: Commit release record**

Run:

```powershell
git add docs\releases\2026-06-06-roadmap-completion.md docs\superpowers\plans\2026-06-06-long-roadmap.md docs\superpowers\plans\2026-06-06-roadmap-completion-implementation.md
git commit -m "docs: add roadmap completion release plan"
```

---

## Task 9: Final publish and remote verification

**Files:**
- No file modifications.

- [x] **Step 1: Push all completed commits**

Run:

```powershell
git push
```

Expected:

```text
... main -> main
```

If the push fails due to GitHub network issues, capture the exact error and retry later. Do not modify AiMaMi/proxy settings.

- [x] **Step 2: Verify remote matches local**

Run:

```powershell
$local = git rev-parse HEAD
$remote = (git ls-remote origin refs/heads/main).Split()[0]
"local=$local"
"remote=$remote"
if ($local -ne $remote) { throw "remote does not match local" }
```

Expected:

```text
local=<same-sha>
remote=<same-sha>
```

- [x] **Step 3: Final clean status**

Run:

```powershell
git status --branch --short
```

Expected:

```text
## main...origin/main
```

---

## Completion boundary

This plan is complete only when all of the following are true:

- Existing local commit `6f336ea` is pushed or explicitly documented as network-blocked.
- Retrieval eval validation exists and passes.
- Feedback governance export/reporting exists and passes focused tests.
- Asset manifest payloads are versioned and tests pass.
- Session recovery report script and template exist and have sample verification.
- Memory governance report script and template exist and have diagnostics-sample verification.
- MCP inventory check exists and passes.
- Package and verify scripts include all new scripts/docs.
- `scripts/run-release-acceptance.ps1` passes without skipped pytest.
- `git diff --check` passes.
- Release record exists at `docs/releases/2026-06-06-roadmap-completion.md`.
- All intended commits are pushed to `origin/main`, unless GitHub network is explicitly blocking push.

## What still remains after this plan

Even after this plan is complete, these remain future evidence-gated projects, not part of this no-heavy-dependency pass:

- Redis queue migration design and implementation.
- Dashboard/subgraph UI.
- LLM feedback planner.
- ACL/user-manager.
- Real NAS operator deployment evidence if no NAS environment was available during local execution.
