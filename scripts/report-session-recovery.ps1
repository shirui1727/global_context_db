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
$Sessions = @($Data.sessions)
$Recoverable = 0
$NeedsSummary = 0

foreach ($Session in $Sessions) {
    $Summary = [string]$Session.summary
    if ($Summary.Trim().Length -ge 40) {
        $Recoverable += 1
    } else {
        $NeedsSummary += 1
    }
}

$Lines = @(
    "# Session Recovery Report",
    "",
    "- **Generated at:** $((Get-Date).ToUniversalTime().ToString('o'))",
    "- **Session count:** $($Sessions.Count)",
    "- **Recoverable sessions:** $Recoverable",
    "- **Needs summary:** $NeedsSummary",
    "",
    "## Sessions needing summary",
    "",
    "| Session id | Title | Source agent | Last activity | Reason |",
    "| --- | --- | --- | --- | --- |"
)

foreach ($Session in $Sessions) {
    $Summary = [string]$Session.summary
    if ($Summary.Trim().Length -lt 40) {
        $Lines += "| $($Session.id) | $($Session.title) | $($Session.source_agent) | $($Session.last_activity_at) | summary shorter than 40 characters |"
    }
}

$Lines | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
