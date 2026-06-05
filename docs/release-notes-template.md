# Global Context DB Release Notes Template

复制本模板到具体版本记录中使用。

## Release

- Version / label:
- Date:
- Commit:
- NAS package path:

## Summary

- 

## Changes

### Added

- 

### Changed

- 

### Fixed

- 

### Docs / Ops

- 

## Verification evidence

本地发布验收：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
```

结果：

- pytest:
- compileall:
- NAS package:
- NAS package verify:
- plan checklist sanity:
- `git diff --check`:

NAS post-deploy checks:

Checklist: `docs/nas-operator-acceptance.md`

```powershell
Invoke-RestMethod "http://NAS_IP:8000/health"
Invoke-RestMethod "http://NAS_IP:8000/diagnostics"
Invoke-RestMethod "http://NAS_IP:8000/scheduler/status"
```

MCP checks:

- `gcd_health`:
- `gcd_diagnostics`:
- `gcd_scheduler_status`:

## Known warnings / limitations

- FastAPI `on_event` deprecation warning is currently known if present in pytest output.

## Rollback

- Previous known-good package:
- Rollback steps:
  1. Stop Docker project.
  2. Overlay previous package code.
  3. Rebuild/restart containers.
  4. Re-run NAS operator acceptance checks.
- Data safety:
  - Do not delete Docker volume.
  - Do not delete `global_context_db/data`.
  - Do not delete external NAS source files.

## Follow-up

- 
