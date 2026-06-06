param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Assert-Property {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Context
    )

    if ($null -eq $Object -or -not ($Object.PSObject.Properties.Name -contains $Name)) {
        throw "$Context is missing required property '$Name'"
    }
}

$BaseUrl = $BaseUrl.TrimEnd("/")

Write-Host "== Global Context DB service smoke =="
Write-Host "BaseUrl: $BaseUrl"

Write-Host "`n== /health =="
$Health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($Health.ok -ne $true) {
    throw "/health did not return ok=true"
}
if ($Health.service -ne "global-context-db") {
    throw "/health returned unexpected service: $($Health.service)"
}
Assert-Property $Health "version" "/health"
Assert-Property $Health "mcp" "/health"

Write-Host "`n== /diagnostics =="
$Diagnostics = Invoke-RestMethod -Uri "$BaseUrl/diagnostics" -Method Get
Assert-Property $Diagnostics "governance" "/diagnostics"
Assert-Property $Diagnostics.governance "audit" "/diagnostics.governance"
Assert-Property $Diagnostics.governance "improvement" "/diagnostics.governance"
Assert-Property $Diagnostics.governance.audit "high_risk_actions" "/diagnostics.governance.audit"
Assert-Property $Diagnostics.governance.audit "write_action_counts" "/diagnostics.governance.audit"
if ($Diagnostics.governance.audit.high_risk_actions -notcontains "mcp.high_risk_write") {
    throw "/diagnostics high_risk_actions does not include mcp.high_risk_write"
}

$Improvement = $Diagnostics.governance.improvement
foreach ($Name in @(
    "queue_health",
    "pending_by_queue",
    "failed_by_queue",
    "retryable_failed_by_queue",
    "exhausted_failed_by_queue",
    "oldest_pending_by_queue"
)) {
    Assert-Property $Improvement $Name "/diagnostics.governance.improvement"
}

Write-Host "`n== /scheduler/status =="
$Scheduler = Invoke-RestMethod -Uri "$BaseUrl/scheduler/status" -Method Get
foreach ($Name in @(
    "queue_health",
    "pending_by_queue",
    "failed_by_queue",
    "retryable_failed_by_queue",
    "exhausted_failed_by_queue",
    "oldest_pending_by_queue"
)) {
    Assert-Property $Scheduler $Name "/scheduler/status"
}

Write-Host "`n== service smoke passed =="
[pscustomobject]@{
    Ok = $true
    BaseUrl = $BaseUrl
    Service = $Health.service
    Version = $Health.version
}
