param(
    [Parameter(Mandatory = $true)]
    [string]$Snapshot
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

function Map-Total {
    param($Object)
    if ($null -eq $Object) { return 0 }
    $Total = 0
    foreach ($Property in $Object.PSObject.Properties) {
        $Total += [int]$Property.Value
    }
    return $Total
}

function Get-IntValue {
    param($Value)
    if ($null -eq $Value) {
        return 0
    }
    return [int]$Value
}

$Health = Read-SnapshotJson $Snapshot "health.json"
$Diagnostics = Read-SnapshotJson $Snapshot "diagnostics.json"
$Scheduler = Read-SnapshotJson $Snapshot "scheduler-status.json"

$Reasons = @()
$Warnings = @()
$Status = "green"

if ($Health.ok -ne $true) {
    $Status = "red"
    $Reasons += "/health ok is not true"
}

foreach ($Name in @("governance", "counts")) {
    if (-not ($Diagnostics.PSObject.Properties.Name -contains $Name)) {
        $Status = "red"
        $Reasons += "/diagnostics missing $Name"
    }
}

foreach ($Name in @("queue_health", "pending_by_queue", "failed_by_queue", "retryable_failed_by_queue", "exhausted_failed_by_queue", "oldest_pending_by_queue")) {
    if (-not ($Scheduler.PSObject.Properties.Name -contains $Name)) {
        $Status = "red"
        $Reasons += "/scheduler/status missing $Name"
    }
}

$Exhausted = Map-Total $Scheduler.exhausted_failed_by_queue
$Failed = Map-Total $Scheduler.failed_by_queue
$Pending = Map-Total $Scheduler.pending_by_queue
$HighRiskWrites = Get-IntValue $Diagnostics.governance.audit.high_risk_write_action_count

if ($Exhausted -gt 0) {
    $Status = "red"
    $Reasons += "exhausted failed queue count is $Exhausted"
}
elseif ($Failed -gt 0 -and $Status -ne "red") {
    $Status = "yellow"
    $Reasons += "failed queue count is $Failed"
}

if ($Pending -gt 0 -and $Status -eq "green") {
    $Status = "yellow"
    $Reasons += "pending queue count is $Pending"
}

if ($HighRiskWrites -gt 0 -and $Status -eq "green") {
    $Status = "yellow"
    $Reasons += "high-risk write count is $HighRiskWrites"
}

if (-not ($Diagnostics.governance.audit.high_risk_actions -contains "mcp.high_risk_write")) {
    $Status = "red"
    $Reasons += "mcp.high_risk_write is missing from high_risk_actions"
}

if ($Reasons.Count -eq 0) {
    $Reasons += "service and governance fields look healthy"
}

[ordered]@{
    ok = $Status -ne "red"
    status = $Status
    reasons = $Reasons
    warnings = $Warnings
    metrics = [ordered]@{
        pending_queue_count = $Pending
        failed_queue_count = $Failed
        exhausted_failed_queue_count = $Exhausted
        high_risk_write_action_count = $HighRiskWrites
    }
} | ConvertTo-Json -Depth 20
