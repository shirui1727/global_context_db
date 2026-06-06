# Codex MCP Client Profile

Use this profile when connecting Codex to Global Context DB through MCP.

## Endpoint

```text
http://NAS_IP:8001/mcp
```

Local testing:

```text
http://127.0.0.1:8001/mcp
```

## Smoke sequence

Run these tools first:

1. `gcd_health`
2. `gcd_diagnostics`
3. `gcd_scheduler_status`

Then run a minimal write/read:

1. `gcd_add_memory`
2. `gcd_search_memories`

Use tags:

```text
codex
smoke-test
mcp-smoke
```

## High-risk tools

The following should be used deliberately and reviewed through audit logs:

- `gcd_delete_memory`
- `gcd_update_memory`
- `gcd_apply_memory_feedback`
- snapshot restore/import style operations

## Troubleshooting

If MCP fails, verify REST first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-service-smoke.ps1 -BaseUrl http://NAS_IP:8000
```

If REST passes but MCP fails, check client transport configuration and use `docs/mcp-smoke-checklist.md`.
