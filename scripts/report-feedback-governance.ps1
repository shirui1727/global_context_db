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
