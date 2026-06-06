param(
    [Parameter(Mandatory = $true)]
    [string]$DiagnosticsPath,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $OutputPath) {
    $OutputPath = [System.IO.Path]::ChangeExtension($DiagnosticsPath, ".memory-governance.md")
}

$Diagnostics = Get-Content -LiteralPath $DiagnosticsPath -Raw | ConvertFrom-Json
$Memory = $Diagnostics.governance.memory
$Improvement = $Diagnostics.governance.improvement

$Lines = @(
    "# Memory Governance Report",
    "",
    "- **Generated at:** $((Get-Date).ToUniversalTime().ToString('o'))",
    "",
    "## Relation index",
    "",
    "- **Sample count:** $($Memory.relation_index.sample_count)",
    "- **Kind counts:** $($Memory.relation_index.kind_counts | ConvertTo-Json -Compress)",
    "",
    "## Hygiene queue",
    "",
    "- **Pending by queue:** $($Improvement.pending_by_queue | ConvertTo-Json -Compress)",
    "- **Failed by queue:** $($Improvement.failed_by_queue | ConvertTo-Json -Compress)",
    "",
    "## Decision",
    "",
    "Keep relation and hygiene work as reviewable reports/proposals. Do not start graph UI or auto-apply hygiene without repeated operator evidence."
)

$Lines | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
