# NAS Acceptance Report: 2026-06-06

- **Status:** pending NAS deployment
- **Release package:** `S:\项目开发\全局数据库\release\global_context_db.zip`
- **Release commit:** `86eca67 docs: complete runtime acceptance hardening plan`
- **Checklist source:** `docs/nas-operator-acceptance.md`

## Deployment record

Fill after deployment:

- NAS host/IP:
- Deployment time:
- Operator:
- Package copied from:
- Package copied to:
- Previous package retained at:

## REST checks

```powershell
Invoke-RestMethod "http://NAS_IP:8000/health"
Invoke-RestMethod "http://NAS_IP:8000/diagnostics"
Invoke-RestMethod "http://NAS_IP:8000/scheduler/status"
```

Results:

- `/health`:
- `/diagnostics`:
- `/scheduler/status`:

## MCP checks

Endpoint:

```text
http://NAS_IP:8001/mcp
```

Tools:

- `gcd_health`:
- `gcd_diagnostics`:
- `gcd_scheduler_status`:
- `gcd_add_memory` smoke:
- `gcd_search_memories` smoke:

## Diagnostics snapshot

```powershell
powershell -ExecutionPolicy Bypass -File scripts\collect-diagnostics-snapshot.ps1 -BaseUrl http://NAS_IP:8000 -OutputDir .\diagnostics-snapshots
```

Results:

- Snapshot directory:
- Manifest:
- Files:

## Rollback

- Previous known-good package:
- Rollback tested:
- Data volume untouched:
- External NAS source files untouched:

## Notes

- 
