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
