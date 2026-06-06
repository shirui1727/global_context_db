# Release: Runtime acceptance build

- **Date:** 2026-06-06
- **Commit:** `86eca67 docs: complete runtime acceptance hardening plan`
- **Branch:** `main`
- **NAS package path:** `S:\项目开发\全局数据库\release\global_context_db.zip`
- **Status:** ready for NAS overlay deployment; actual NAS deployment is tracked separately in `docs/ops/nas-acceptance-report-2026-06-06.md`.

## Summary

This build completes the runtime acceptance hardening plan: one-shot release acceptance, NAS operator checklist, diagnostics snapshot collection, escalation trigger records, and release notes template.

## Verification command

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
```

## Verification evidence

Observed on the previous accepted run:

- pytest: `107 passed`
- known warnings: 2 FastAPI `on_event` deprecation warnings.
- compileall: passed for `app` and `tools`.
- NAS package verify: `Ok=True`.
- package entries: `96`.
- MemOS maturity plan: 45 tasks, 0 open checkboxes.
- Runtime acceptance plan: 5 tasks, 0 open checkboxes.
- `git diff --check`: passed.

## Operator follow-up

Before deploying to NAS, run the release acceptance command again from the current working tree. After deployment, follow:

- `docs/nas-operator-acceptance.md`
- `docs/mcp-smoke-checklist.md`
- `docs/first-use-workflow.md`

## Rollback note

Rollback should overlay the previous known-good package and rebuild/restart containers. Do not delete Docker volumes, `global_context_db/data`, or external NAS source files.
