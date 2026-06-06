param(
    [Parameter(Mandatory = $true)]
    [string]$Before,
    [Parameter(Mandatory = $true)]
    [string]$After
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

function To-Hashtable {
    param($Object)
    $Result = @{}
    if ($null -eq $Object) {
        return $Result
    }
    foreach ($Property in $Object.PSObject.Properties) {
        $Result[$Property.Name] = $Property.Value
    }
    return $Result
}

function Get-IntValue {
    param($Value)
    if ($null -eq $Value) {
        return 0
    }
    return [int]$Value
}

function Compare-Map {
    param($BeforeMap, $AfterMap)
    $BeforeHash = To-Hashtable $BeforeMap
    $AfterHash = To-Hashtable $AfterMap
    $Keys = @($BeforeHash.Keys + $AfterHash.Keys | Sort-Object -Unique)
    $Delta = [ordered]@{}
    foreach ($Key in $Keys) {
        $BeforeValue = Get-IntValue $BeforeHash[$Key]
        $AfterValue = Get-IntValue $AfterHash[$Key]
        $Delta[$Key] = [ordered]@{
            before = $BeforeValue
            after = $AfterValue
            delta = $AfterValue - $BeforeValue
        }
    }
    return $Delta
}

$BeforeDiagnostics = Read-SnapshotJson $Before "diagnostics.json"
$AfterDiagnostics = Read-SnapshotJson $After "diagnostics.json"
$BeforeScheduler = Read-SnapshotJson $Before "scheduler-status.json"
$AfterScheduler = Read-SnapshotJson $After "scheduler-status.json"

$Warnings = @()
foreach ($Required in @("governance", "counts")) {
    if (-not ($AfterDiagnostics.PSObject.Properties.Name -contains $Required)) {
        $Warnings += "after diagnostics missing $Required"
    }
}
if (-not ($AfterScheduler.PSObject.Properties.Name -contains "queue_health")) {
    $Warnings += "after scheduler missing queue_health"
}

$Result = [ordered]@{
    ok = $Warnings.Count -eq 0
    count_delta = Compare-Map $BeforeDiagnostics.counts $AfterDiagnostics.counts
    queue_delta = [ordered]@{
        pending_by_queue = Compare-Map $BeforeScheduler.pending_by_queue $AfterScheduler.pending_by_queue
        failed_by_queue = Compare-Map $BeforeScheduler.failed_by_queue $AfterScheduler.failed_by_queue
        retryable_failed_by_queue = Compare-Map $BeforeScheduler.retryable_failed_by_queue $AfterScheduler.retryable_failed_by_queue
        exhausted_failed_by_queue = Compare-Map $BeforeScheduler.exhausted_failed_by_queue $AfterScheduler.exhausted_failed_by_queue
    }
    audit_delta = [ordered]@{
        high_risk_write_action_count = [ordered]@{
            before = Get-IntValue $BeforeDiagnostics.governance.audit.high_risk_write_action_count
            after = Get-IntValue $AfterDiagnostics.governance.audit.high_risk_write_action_count
            delta = (Get-IntValue $AfterDiagnostics.governance.audit.high_risk_write_action_count) - (Get-IntValue $BeforeDiagnostics.governance.audit.high_risk_write_action_count)
        }
    }
    warnings = $Warnings
}

$Result | ConvertTo-Json -Depth 20
