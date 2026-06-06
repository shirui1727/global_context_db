param(
    [string]$OutputDir = "",
    [switch]$SkipPytest
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
try {
    if (-not $OutputDir) {
        $OutputDir = Join-Path (Split-Path $RepoRoot -Parent) "release"
    }

    $OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
    $ZipPath = Join-Path $OutputDir "global_context_db.zip"

    Write-Host "== Global Context DB release acceptance =="
    Write-Host "Repo: $RepoRoot"
    Write-Host "OutputDir: $OutputDir"

    if (-not $SkipPytest) {
        Write-Host "`n== pytest =="
        python -m pytest -q
    }

    Write-Host "`n== compileall =="
    python -m compileall app tools

    Write-Host "`n== NAS package =="
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "package-nas-update.ps1") -OutputDir $OutputDir

    Write-Host "`n== NAS package verify =="
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "verify-nas-package.ps1") $ZipPath

    Write-Host "`n== plan checklist sanity =="
    python -c @"
from pathlib import Path
import re

plan = Path('docs/superpowers/plans/2026-05-27-memos-maturity-rebuild.md')
text = plan.read_text(encoding='utf-8')
tasks = [int(n) for n in re.findall(r'^## Task (\d+): ', text, flags=re.M)]
open_boxes = re.findall(r'^- \[ \] ', text, flags=re.M)

if tasks != list(range(1, 46)):
    raise SystemExit(f'Unexpected MemOS maturity task sequence: {tasks[:5]} ... {tasks[-5:]}')
if open_boxes:
    raise SystemExit(f'MemOS maturity plan still has {len(open_boxes)} open checkbox(es)')

print('MemOS maturity plan: 45 tasks, 0 open checkboxes')

runtime_plan = Path('docs/superpowers/plans/2026-06-05-runtime-acceptance-hardening.md')
runtime_text = runtime_plan.read_text(encoding='utf-8')
runtime_tasks = [int(n) for n in re.findall(r'^## Task (\d+): ', runtime_text, flags=re.M)]
runtime_open_boxes = re.findall(r'^- \[ \] ', runtime_text, flags=re.M)

if runtime_tasks != list(range(1, 6)):
    raise SystemExit(f'Unexpected runtime acceptance task sequence: {runtime_tasks}')
if runtime_open_boxes:
    raise SystemExit(f'Runtime acceptance plan still has {len(runtime_open_boxes)} open checkbox(es)')

print('Runtime acceptance plan: 5 tasks, 0 open checkboxes')

field_plan = Path('docs/superpowers/plans/2026-06-06-field-acceptance-first-use-loop.md')
field_text = field_plan.read_text(encoding='utf-8')
field_tasks = [int(n) for n in re.findall(r'^## Task (\d+): ', field_text, flags=re.M)]
field_open_boxes = re.findall(r'^- \[ \] ', field_text, flags=re.M)

if field_tasks != list(range(1, 8)):
    raise SystemExit(f'Unexpected field acceptance task sequence: {field_tasks}')
if field_open_boxes:
    raise SystemExit(f'Field acceptance plan still has {len(field_open_boxes)} open checkbox(es)')

print('Field acceptance plan: 7 tasks, 0 open checkboxes')

required_roadmap_files = [
    'docs/superpowers/plans/2026-06-06-long-roadmap.md',
    'docs/releases/2026-06-06-field-acceptance.md',
    'docs/ops/weekly-operations-report-template.md',
    'docs/ops/smoke-data-policy.md',
    'docs/clients/codex-mcp.md',
    'docs/clients/openclaw-mcp.md',
    'docs/mcp-tool-inventory.md',
    'scripts/compare-diagnostics-snapshots.ps1',
    'scripts/score-diagnostics-snapshot.ps1',
    'scripts/run-first-use-smoke.ps1',
]

missing_roadmap_files = [path for path in required_roadmap_files if not Path(path).exists()]
if missing_roadmap_files:
    raise SystemExit(f'Missing long-roadmap executable-slice files: {missing_roadmap_files}')

print(f'Long roadmap executable slice: {len(required_roadmap_files)} files present')

required_ops_report_files = [
    'scripts/generate-ops-report.ps1',
    'scripts/report-queue-pressure.ps1',
    'docs/ops/dashboard-trigger-review.md',
    'docs/ops/feedback-sample-log.md',
    'docs/asset-artifact-policy.md',
    'docs/external-worker-contract.md',
    'docs/session-compression-policy.md',
]

missing_ops_report_files = [path for path in required_ops_report_files if not Path(path).exists()]
if missing_ops_report_files:
    raise SystemExit(f'Missing ops-report executable-slice files: {missing_ops_report_files}')

print(f'Ops report executable slice: {len(required_ops_report_files)} files present')
"@

    Write-Host "`n== git diff check =="
    git diff --check

    Write-Host "`n== acceptance passed =="
    [pscustomobject]@{
        Ok = $true
        Repo = "$RepoRoot"
        ZipPath = "$ZipPath"
    }
}
finally {
    Pop-Location
}
