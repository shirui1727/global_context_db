param(
    [Parameter(Mandatory = $true)]
    [string]$Snapshot,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

function Read-SnapshotJson {
    param(
        [Parameter(Mandatory = $true)][string]$SnapshotPath,
        [Parameter(Mandatory = $true)][string]$FileName
    )

    $Path = if (Test-Path $SnapshotPath -PathType Container) {
        Join-Path $SnapshotPath $FileName
    }
    else {
        $SnapshotPath
    }
    if (-not (Test-Path $Path)) {
        throw "Missing snapshot file: $Path"
    }
    return Get-Content -Path $Path -Raw | ConvertFrom-Json
}

function Json-Compact {
    param($Value)
    if ($null -eq $Value) {
        return "{}"
    }
    return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

$Health = Read-SnapshotJson $Snapshot "health.json"
$Diagnostics = Read-SnapshotJson $Snapshot "diagnostics.json"
$Scheduler = Read-SnapshotJson $Snapshot "scheduler-status.json"

$ScoreRaw = powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "score-diagnostics-snapshot.ps1") -Snapshot $Snapshot
$Score = $ScoreRaw | ConvertFrom-Json
$QueueRaw = powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "report-queue-pressure.ps1") -Snapshot $Snapshot
$Queue = $QueueRaw | ConvertFrom-Json

$CreatedAt = (Get-Date).ToUniversalTime().ToString("o")
$McpJson = Json-Compact $Health.mcp
$ScoreMetricsJson = Json-Compact $Score.metrics
$QueueTotalsJson = Json-Compact $Queue.totals
$PendingJson = Json-Compact $Queue.pending_by_queue
$FailedJson = Json-Compact $Queue.failed_by_queue
$RetryableJson = Json-Compact $Queue.retryable_failed_by_queue
$ExhaustedJson = Json-Compact $Queue.exhausted_failed_by_queue
$OldestJson = Json-Compact $Queue.oldest_pending_by_queue
$HighRiskActions = $Diagnostics.governance.audit.high_risk_actions -join ", "
$WriteActionCountsJson = Json-Compact $Diagnostics.governance.audit.write_action_counts
$ScoreReasons = $Score.reasons -join "; "

$Lines = @(
    "# Global Context DB Ops Report",
    "",
    "- Generated at: $CreatedAt",
    "- Snapshot: $Snapshot",
    "- Service: $($Health.service)",
    "- Version: $($Health.version)",
    "- Status: $($Score.status)",
    "",
    "## Health",
    "",
    "- ok: $($Health.ok)",
    "- data_dir: $($Health.data_dir)",
    "- mcp: $McpJson",
    "",
    "## Diagnostics score",
    "",
    "- status: $($Score.status)",
    "- reasons: $ScoreReasons",
    "- metrics: $ScoreMetricsJson",
    "",
    "## Queue pressure",
    "",
    "- recommendation: $($Queue.recommendation)",
    "- totals: $QueueTotalsJson",
    "- pending_by_queue: $PendingJson",
    "- failed_by_queue: $FailedJson",
    "- retryable_failed_by_queue: $RetryableJson",
    "- exhausted_failed_by_queue: $ExhaustedJson",
    "- oldest_pending_by_queue: $OldestJson",
    "",
    "## Governance audit",
    "",
    "- high_risk_actions: $HighRiskActions",
    "- high_risk_write_action_count: $($Diagnostics.governance.audit.high_risk_write_action_count)",
    "- write_action_counts: $WriteActionCountsJson",
    "",
    "## Trigger decisions",
    "",
    "- Redis Streams: not triggered unless queue pressure evidence persists.",
    "- Dashboard/subgraph: not triggered unless repeated triage cannot be served by reports.",
    "- LLM planner: not triggered without real feedback corpus evidence.",
    "- ACL/user manager: not triggered without real multi-user isolation needs.",
    ""
)

$Report = $Lines -join "`n"

if (-not $OutputPath) {
    $OutputPath = Join-Path $Snapshot "ops-report.md"
}

$Parent = Split-Path $OutputPath -Parent
if ($Parent -and -not (Test-Path $Parent)) {
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
}
$Report | Set-Content -Path $OutputPath -Encoding UTF8

[pscustomobject]@{
    Ok = $true
    OutputPath = (Resolve-Path $OutputPath).Path
    Status = $Score.status
    QueueRecommendation = $Queue.recommendation
}
