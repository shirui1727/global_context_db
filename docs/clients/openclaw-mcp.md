# OpenClaw MCP Client Profile

Use this profile when connecting OpenClaw to Global Context DB through streamable HTTP MCP.

## Endpoint

```text
http://NAS_IP:8001/mcp
```

Transport:

```text
HTTP streamable transport
```

Headers, if the client exposes them:

```text
Accept: application/json, text/event-stream
```

## Important note

Opening `/mcp` directly in a browser may show `Missing session ID`. That does not prove the MCP service is broken. A real MCP client initializes a session before tool calls.

## Acceptance sequence

1. Verify REST:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-service-smoke.ps1 -BaseUrl http://NAS_IP:8000
```

2. Add OpenClaw MCP server:

```text
global_context_db -> http://NAS_IP:8001/mcp
```

3. Run MCP tools:

- `gcd_health`
- `gcd_diagnostics`
- `gcd_scheduler_status`
- `gcd_add_memory`
- `gcd_search_memories`

## Troubleshooting `fetch failed`

Check in order:

1. REST `/health`.
2. REST `/diagnostics`.
3. MCP URL and transport type.
4. Whether the client expects streamable HTTP.
5. Whether API key settings changed.

Do not modify AiMaMi or other local relay/proxy configuration unless explicitly requested.
