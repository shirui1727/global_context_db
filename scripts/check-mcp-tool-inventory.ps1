param(
    [string]$InventoryPath = "docs\mcp-tool-inventory.md"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Path = Join-Path $RepoRoot $InventoryPath
$Text = Get-Content -LiteralPath $Path -Raw
$Required = @(
    "gcd_diagnostics",
    "gcd_scheduler_status",
    "gcd_add_memory",
    "gcd_search_memories",
    "gcd_search_assets",
    "gcd_propose_memory_feedback_actions"
)
$Missing = @()
foreach ($Name in $Required) {
    if ($Text -notmatch [regex]::Escape($Name)) {
        $Missing += $Name
    }
}
if ($Missing.Count -gt 0) {
    throw "MCP inventory missing required tools: $($Missing -join ', ')"
}
[pscustomobject]@{
    Ok = $true
    InventoryPath = $Path
    RequiredCount = $Required.Count
}
