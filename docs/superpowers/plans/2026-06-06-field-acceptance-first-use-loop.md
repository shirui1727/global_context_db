# Field Acceptance & First-use Loop

**Goal:** 把当前已经通过本地发布验收的 `global_context_db` 接到真实运行链路：服务 smoke、MCP smoke、first-use workflow、诊断快照基线和 NAS 验收报告模板。继续保持 NAS-first、diagnostics-first；不默认进入 Redis、dashboard/subgraph、LLM planner 或 ACL 阶段。

**Baseline:**

- `86eca67 docs: complete runtime acceptance hardening plan` 已推送到 `main`。
- `scripts/run-release-acceptance.ps1` 已覆盖 pytest、compileall、NAS 打包/验包、计划账本和 `git diff --check`。
- 当前重依赖触发条件仍是证据驱动：没有真实 queue pressure / dashboard triage / feedback 样本前，不升级架构。

---

## Task 1: Release record for current runtime acceptance build

Goal: make the current release candidate traceable before any NAS overlay deployment.

- [x] Add `docs/releases/2026-06-06-runtime-acceptance.md`.
- [x] Record commit, package path, verification command, observed verification evidence, and known warnings.
- [x] Keep the release record factual; do not claim NAS deployment has happened unless it has.

Verification:

```powershell
python -c "from pathlib import Path; Path('docs/releases/2026-06-06-runtime-acceptance.md').read_text(encoding='utf-8')"
git diff --check
```

---

## Task 2: REST service smoke script

Goal: provide a read-only script that verifies a running REST service after local uvicorn or NAS deployment.

- [x] Add `scripts/run-service-smoke.ps1`.
- [x] Check `/health`, `/diagnostics`, and `/scheduler/status`.
- [x] Assert expected governance audit and queue-health fields, including `mcp.high_risk_write`.

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-service-smoke.ps1 -BaseUrl http://127.0.0.1:8000
```

---

## Task 3: MCP smoke checklist

Goal: make MCP client acceptance explicit without requiring this repo to own every client runtime.

- [x] Add `docs/mcp-smoke-checklist.md`.
- [x] Cover `gcd_health`, `gcd_diagnostics`, `gcd_scheduler_status`, `gcd_add_memory`, and `gcd_search_memories`.
- [x] Document that cleanup via `gcd_delete_memory` is high-risk and audited.

---

## Task 4: First-use workflow

Goal: give the operator a concrete first workflow that exercises memory, asset, session, retrieval, feedback, scheduler diagnostics, and governance.

- [x] Add `docs/first-use-workflow.md`.
- [x] Keep the workflow NAS-safe: register asset references, do not copy or parse original NAS files in the core service.
- [x] Include expected evidence after each phase.

---

## Task 5: Diagnostics baseline record

Goal: create a shareable baseline template/record for what a healthy local or NAS deployment looks like.

- [x] Add `docs/ops/diagnostics-baseline-2026-06-06.md`.
- [x] Record local smoke/snapshot verification and mark NAS-specific values as pending until real NAS deployment.
- [x] Reference `scripts/collect-diagnostics-snapshot.ps1`.

---

## Task 6: NAS acceptance report

Goal: prepare an operator-fillable report for the real NAS deployment.

- [x] Add `docs/ops/nas-acceptance-report-2026-06-06.md`.
- [x] Base it on `docs/nas-operator-acceptance.md`.
- [x] Mark status as `pending NAS deployment` until the actual NAS overlay is performed.

---

## Task 7: Trigger decision status update

Goal: explicitly record whether Redis, dashboard/subgraph, or LLM planner are triggered by current evidence.

- [x] Update `docs/queue-trigger-decision-record.md` with a 2026-06-06 status section.
- [x] State that no escalation is currently triggered by local acceptance evidence.
- [x] Preserve the evidence required before future escalation.

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
git diff --check
```
