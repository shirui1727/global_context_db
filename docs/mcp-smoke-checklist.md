# MCP Smoke Checklist

Use this checklist after REST service smoke passes. It proves that an MCP client can reach the NAS service and execute the minimum read/write memory workflow.

## Endpoint

```text
http://NAS_IP:8001/mcp
```

For local testing, replace `NAS_IP` with `127.0.0.1` if the MCP service is running locally.

## Read-only checks

Run from a real MCP client such as Codex/OpenClaw:

1. `gcd_health`
   - Expected: `ok=true`, `service=global-context-db`.
2. `gcd_diagnostics`
   - Expected: contains `governance.audit.high_risk_actions`.
   - Expected: `high_risk_actions` includes `mcp.high_risk_write`.
3. `gcd_scheduler_status`
   - Expected: contains `queue_health`, `pending_by_queue`, `failed_by_queue`, `oldest_pending_by_queue`.

## Minimal write/read check

Create one smoke memory:

```text
gcd_add_memory(
  content="MCP smoke memory 2026-06-06: global_context_db can write and search over MCP.",
  tags=["smoke-test", "mcp"],
  agent_id="codex",
  metadata={"smoke_test": true, "date": "2026-06-06"}
)
```

Then search:

```text
gcd_search_memories(query="MCP smoke memory 2026-06-06", top_k=5)
```

Expected:

- The created memory appears in search results.
- The memory keeps the `smoke-test` tag.

## Cleanup policy

Do not delete the smoke memory by default. It is useful as a trace that MCP was accepted.

If cleanup is necessary:

```text
gcd_delete_memory(memory_id="<created memory id>")
```

`gcd_delete_memory` is a high-risk MCP write and should create an audit entry with:

```text
action = mcp.high_risk_write
target_type = mcp_tool
target_id = gcd_delete_memory
```

Confirm through:

```text
gcd_diagnostics
gcd_list_audit_logs
```
