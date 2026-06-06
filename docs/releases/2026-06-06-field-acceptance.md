# Release: Field acceptance build

- **Date:** 2026-06-06
- **Commit:** `6e7e004 docs: add field acceptance first use plan`
- **Branch:** `main`
- **NAS package path:** `S:\项目开发\全局数据库\release\global_context_db.zip`
- **Status:** ready for NAS field deployment; NAS acceptance is still recorded separately.

## Summary

This build adds field acceptance artifacts: REST service smoke, MCP smoke checklist, first-use workflow, diagnostics baseline template, and NAS acceptance report template.

## Verification command

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
```

## Expected verification evidence

- pytest passes.
- `python -m compileall app tools` passes.
- NAS package verification returns `Ok=True`.
- MemOS maturity plan has 45 tasks and 0 open checkboxes.
- Runtime acceptance plan has 5 tasks and 0 open checkboxes.
- Field acceptance plan has 7 tasks and 0 open checkboxes.
- `git diff --check` passes.

## Follow-up

After deploying to NAS, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-service-smoke.ps1 -BaseUrl http://NAS_IP:8000
powershell -ExecutionPolicy Bypass -File scripts\collect-diagnostics-snapshot.ps1 -BaseUrl http://NAS_IP:8000 -OutputDir .\diagnostics-snapshots
```

Then complete:

- `docs/ops/nas-acceptance-report-2026-06-06.md`
- `docs/ops/diagnostics-baseline-2026-06-06.md`
