# Diagnostics Baseline: 2026-06-06

- **Status:** local acceptance baseline captured; NAS deployment values pending.
- **Release commit:** `86eca67 docs: complete runtime acceptance hardening plan`
- **Baseline purpose:** provide a healthy-shape reference for `/health`, `/diagnostics`, and `/scheduler/status` before comparing future NAS incidents.

## Local evidence

Local service smoke and diagnostics snapshot are verified as part of the 2026-06-06 field acceptance plan.

Commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-service-smoke.ps1 -BaseUrl http://127.0.0.1:<local_port>
powershell -ExecutionPolicy Bypass -File scripts\collect-diagnostics-snapshot.ps1 -BaseUrl http://127.0.0.1:<local_port> -OutputDir <temp_snapshot_dir>
```

Expected snapshot files:

- `health.json`
- `diagnostics.json`
- `scheduler-status.json`
- `manifest.json`

## Healthy shape

`/health`:

- `ok = true`
- `service = global-context-db`
- has `version`
- has `mcp`

`/diagnostics`:

- has `governance.audit.high_risk_actions`
- `high_risk_actions` includes `mcp.high_risk_write`
- has `governance.improvement.queue_health`
- has `pending_by_queue`, `failed_by_queue`, `retryable_failed_by_queue`, `exhausted_failed_by_queue`, and `oldest_pending_by_queue`

`/scheduler/status`:

- has `queue_health`
- has `pending_by_queue`
- has `failed_by_queue`
- has `retryable_failed_by_queue`
- has `exhausted_failed_by_queue`
- has `oldest_pending_by_queue`

## NAS baseline

Status: pending NAS deployment.

Fill after NAS overlay:

- NAS host:
- Snapshot directory:
- `/health` summary:
- `/diagnostics` governance summary:
- `/scheduler/status` queue summary:
- Any failed/retryable/exhausted queue pressure:
- Decision: Redis/dashboard/LLM planner triggered? Expected default: no.
