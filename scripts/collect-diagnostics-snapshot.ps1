param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OutputDir = ".\diagnostics-snapshots"
)

$ErrorActionPreference = "Stop"

function Redact-Object {
    param([Parameter(ValueFromPipeline = $true)]$Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [System.Collections.IDictionary]) {
        $Result = [ordered]@{}
        foreach ($Key in $Value.Keys) {
            if ($Key -match '(?i)(api[_-]?key|token|password|authorization|secret)') {
                $Result[$Key] = "[REDACTED]"
            }
            else {
                $Result[$Key] = Redact-Object $Value[$Key]
            }
        }
        return $Result
    }

    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $Items = @()
        foreach ($Item in $Value) {
            $Items += Redact-Object $Item
        }
        return $Items
    }

    if ($Value -is [pscustomobject]) {
        $Result = [ordered]@{}
        foreach ($Property in $Value.PSObject.Properties) {
            if ($Property.Name -match '(?i)(api[_-]?key|token|password|authorization|secret)') {
                $Result[$Property.Name] = "[REDACTED]"
            }
            else {
                $Result[$Property.Name] = Redact-Object $Property.Value
            }
        }
        return $Result
    }

    return $Value
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SnapshotDir = Join-Path $OutputDir $Timestamp
New-Item -ItemType Directory -Path $SnapshotDir -Force | Out-Null

$Endpoints = @(
    @{ Name = "health"; Path = "/health" },
    @{ Name = "diagnostics"; Path = "/diagnostics" },
    @{ Name = "scheduler-status"; Path = "/scheduler/status" }
)

$Files = @()
foreach ($Endpoint in $Endpoints) {
    $Uri = "$BaseUrl$($Endpoint.Path)"
    Write-Host "Fetching $Uri"
    $Response = Invoke-RestMethod -Uri $Uri -Method Get
    $Redacted = Redact-Object $Response
    $File = Join-Path $SnapshotDir "$($Endpoint.Name).json"
    $Redacted | ConvertTo-Json -Depth 100 | Set-Content -Path $File -Encoding UTF8
    $Files += $File
}

$Manifest = [ordered]@{
    ok = $true
    base_url = $BaseUrl
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    snapshot_dir = $SnapshotDir
    files = $Files
    notes = "Contains health, diagnostics, and scheduler status only. Common secret fields are redacted."
}
$ManifestPath = Join-Path $SnapshotDir "manifest.json"
$Manifest | ConvertTo-Json -Depth 10 | Set-Content -Path $ManifestPath -Encoding UTF8

[pscustomobject]@{
    Ok = $true
    SnapshotDir = $SnapshotDir
    Manifest = $ManifestPath
    Files = $Files.Count
}
