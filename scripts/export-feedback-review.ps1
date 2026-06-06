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
