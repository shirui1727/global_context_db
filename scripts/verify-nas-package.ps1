param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath
)

$ErrorActionPreference = "Stop"

$ZipPath = (Resolve-Path $ZipPath).Path
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $Entries = $Zip.Entries
    $Names = $Entries | ForEach-Object { $_.FullName -replace "\\", "/" }

    $Required = @(
        "global_context_db/app/api.py",
        "global_context_db/app/assets/service.py",
        "global_context_db/app/core/config.py",
        "global_context_db/app/governance/service.py",
        "global_context_db/app/improvements/service.py",
        "global_context_db/app/memory/graph_service.py",
        "global_context_db/app/memory/service.py",
        "global_context_db/app/scheduler/service.py",
        "global_context_db/app/storage/repo.py",
        "global_context_db/docker-compose.yaml",
        "global_context_db/scripts/compare-diagnostics-snapshots.ps1",
        "global_context_db/scripts/collect-diagnostics-snapshot.ps1",
        "global_context_db/scripts/generate-ops-report.ps1",
        "global_context_db/scripts/report-queue-pressure.ps1",
        "global_context_db/scripts/run-retrieval-eval-fixture-check.ps1",
        "global_context_db/scripts/export-feedback-review.ps1",
        "global_context_db/scripts/report-feedback-governance.ps1",
        "global_context_db/scripts/report-session-recovery.ps1",
        "global_context_db/scripts/report-memory-governance.ps1",
        "global_context_db/scripts/check-mcp-tool-inventory.ps1",
        "global_context_db/scripts/run-release-acceptance.ps1",
        "global_context_db/scripts/run-first-use-smoke.ps1",
        "global_context_db/scripts/run-service-smoke.ps1",
        "global_context_db/scripts/score-diagnostics-snapshot.ps1",
        "global_context_db/docs/asset-manifest-schema.md",
        "global_context_db/docs/ops/retrieval-eval-report-template.md",
        "global_context_db/docs/ops/feedback-governance-report-template.md",
        "global_context_db/docs/ops/session-recovery-report-template.md",
        "global_context_db/docs/ops/memory-governance-report-template.md",
        "global_context_db/docs/ops/client-smoke-report-template.md",
        "global_context_db/tools/media_manifest_worker.py",
        "global_context_db/tools/retrieval_eval_fixture.py"
    )
    foreach ($Item in $Required) {
        if ($Names -notcontains $Item) {
            throw "Missing required entry: $Item"
        }
    }

    $Blocked = $Names | Where-Object {
        $_ -like "global_context_db/data/*" -or
        $_ -like "global_context_db/.git/*" -or
        $_ -like "*node_modules*" -or
        $_ -like "*docker-compose.yml"
    }
    if ($Blocked) {
        throw "Blocked entries found: $(($Blocked | Select-Object -First 10) -join ', ')"
    }

    [pscustomobject]@{
        Ok = $true
        ZipPath = $ZipPath
        Entries = $Entries.Count
        Compose = "global_context_db/docker-compose.yaml"
        ProjectRoot = "global_context_db/"
    }
}
finally {
    $Zip.Dispose()
}
