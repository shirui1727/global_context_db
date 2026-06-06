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

function To-Map {
    param($Object)
    $Result = [ordered]@{}
    if ($null -eq $Object) { return $Result }
    foreach ($Property in $Object.PSObject.Properties) {
        $Result[$Property.Name] = $Property.Value
    }
    return $Result
}

$Scheduler = Read-SnapshotJson $Snapshot "scheduler-status.json"

$Pending = To-Map $Scheduler.pending_by_queue
$Failed = To-Map $Scheduler.failed_by_queue
$Retryable = To-Map $Scheduler.retryable_failed_by_queue
$Exhausted = To-Map $Scheduler.exhausted_failed_by_queue
$Oldest = To-Map $Scheduler.oldest_pending_by_queue

$Warnings = @()
$Recommendation = "continue_sqlite"

$PendingTotal = Map-Total $Scheduler.pending_by_queue
$FailedTotal = Map-Total $Scheduler.failed_by_queue
$ExhaustedTotal = Map-Total $Scheduler.exhausted_failed_by_queue

if ($ExhaustedTotal -gt 0) {
    $Warnings += "exhausted failed queue work exists"
}
if ($FailedTotal -gt 0) {
    $Warnings += "failed queue work exists"
}
if ($PendingTotal -gt 0) {
    $Warnings += "pending queue work exists"
}
if ($PendingTotal -gt 50 -or $ExhaustedTotal -gt 0) {
    $Recommendation = "investigate_queue_pressure"
}

[ordered]@{
    ok = $true
    recommendation = $Recommendation
    totals = [ordered]@{
        pending = $PendingTotal
        failed = $FailedTotal
        retryable_failed = Map-Total $Scheduler.retryable_failed_by_queue
        exhausted_failed = $ExhaustedTotal
    }
    pending_by_queue = $Pending
    failed_by_queue = $Failed
    retryable_failed_by_queue = $Retryable
    exhausted_failed_by_queue = $Exhausted
    oldest_pending_by_queue = $Oldest
    warnings = $Warnings
} | ConvertTo-Json -Depth 20
