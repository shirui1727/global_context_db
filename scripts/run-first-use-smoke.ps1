param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$AgentId = "codex",
    [string]$Tag = "first-use-smoke",
    [string]$ProjectPath = "S:\项目开发\全局数据库\global_context_db",
    [string]$ApiKey = ""
)

$ErrorActionPreference = "Stop"

function Invoke-Gcd {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        $Body = $null
    )

    $Headers = @{}
    if ($ApiKey) {
        $Headers["X-API-Key"] = $ApiKey
    }
    $Uri = "$BaseUrl$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers
    }
    return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 50)
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SmokeText = "First-use smoke ${Stamp}: Global Context DB can write, search, register assets, create sessions, and report diagnostics."

Write-Host "== first-use smoke =="
Write-Host "BaseUrl: $BaseUrl"
Write-Host "Tag: $Tag"

$MemoryResult = Invoke-Gcd "POST" "/memories" @{
    content = $SmokeText
    tags = @($Tag, "smoke-test")
    agent_id = $AgentId
    source_kind = "first_use_smoke"
    metadata = @{
        smoke_test = $true
        scenario = "first-use-smoke"
        stamp = $Stamp
    }
}
$MemoryId = $MemoryResult.memory_id
if (-not $MemoryId) { throw "memory smoke did not return memory_id" }

$MemorySearch = Invoke-Gcd "GET" ("/memories/search?q=" + [uri]::EscapeDataString($SmokeText) + "&top_k=5")
if (-not ($MemorySearch.results | Where-Object { $_.memory_id -eq $MemoryId -or $_.id -eq $MemoryId })) {
    throw "memory smoke search did not find created memory $MemoryId"
}

$AssetResult = Invoke-Gcd "POST" "/assets" @{
    uri = "smb://NAS/smoke/$Stamp/brief.md"
    title = "First-use smoke asset $Stamp"
    summary = "Referenced asset for first-use smoke. Original file remains outside GCD."
    tags = @($Tag, "smoke-test", "asset")
    asset_kind = "document"
    asset_key = "first-use-smoke-$Stamp"
    storage_mode = "referenced"
    created_by = $AgentId
    metadata = @{
        smoke_test = $true
        scenario = "first-use-smoke"
        stamp = $Stamp
    }
}
$AssetId = $AssetResult.id
if (-not $AssetId) { throw "asset smoke did not return id" }

$AssetSearch = Invoke-Gcd "POST" "/assets/search" @{
    query = "First-use smoke asset $Stamp"
    top_k = 5
}
if (-not ($AssetSearch.results | Where-Object { $_.asset_id -eq $AssetId -or $_.id -eq $AssetId })) {
    throw "asset smoke search did not find created asset $AssetId"
}

$Session = Invoke-Gcd "POST" "/sessions" @{
    source_agent = $AgentId
    project_path = $ProjectPath
    title = "First-use smoke session $Stamp"
    summary = "Smoke session for Global Context DB first-use workflow."
    created_by = $AgentId
    metadata = @{
        smoke_test = $true
        scenario = "first-use-smoke"
        stamp = $Stamp
    }
}
$SessionId = $Session.id
if (-not $SessionId) { throw "session smoke did not return id" }

$Event = Invoke-Gcd "POST" "/sessions/$SessionId/events" @{
    event_type = "assistant_note"
    role = "assistant"
    content = "First-use smoke event $Stamp without secrets."
    metadata = @{
        smoke_test = $true
        scenario = "first-use-smoke"
    }
}
if (-not $Event.id) { throw "session event smoke did not return id" }

$Feedback = Invoke-Gcd "POST" "/memory-feedback" @{
    feedback_text = "First-use smoke feedback ${Stamp}: add evidence that diagnostics-first operation is working."
    target_memory_id = $MemoryId
    created_by = $AgentId
    metadata = @{
        smoke_test = $true
        scenario = "first-use-smoke"
    }
}
$FeedbackId = $Feedback.id
if (-not $FeedbackId) { throw "feedback smoke did not return id" }

$Proposal = Invoke-Gcd "POST" "/memory-feedback/$FeedbackId/propose-actions?planner=deterministic"
if ($Proposal.planner.mode -ne "deterministic") {
    throw "feedback proposal did not use deterministic planner"
}

$Diagnostics = Invoke-Gcd "GET" "/diagnostics"
if (-not ($Diagnostics.governance.audit.high_risk_actions -contains "mcp.high_risk_write")) {
    throw "diagnostics missing mcp.high_risk_write"
}

$Scheduler = Invoke-Gcd "GET" "/scheduler/status"
if (-not ($Scheduler.PSObject.Properties.Name -contains "queue_health")) {
    throw "scheduler status missing queue_health"
}

Write-Host "== first-use smoke passed =="
[pscustomobject]@{
    Ok = $true
    BaseUrl = $BaseUrl
    Stamp = $Stamp
    MemoryId = $MemoryId
    AssetId = $AssetId
    SessionId = $SessionId
    FeedbackId = $FeedbackId
    ProposedCount = $Proposal.proposed_count
}
