# Runtime Acceptance & NAS Runbook Hardening

**Goal:** 把已经完成的 MemOS maturity 主线从“功能完成”推进到“可发布、可巡检、可判断下一阶段触发条件”。本轮继续保持 NAS-first、SQLite-first、diagnostics-first；不默认引入 Redis、dashboard、LLM planner 或 ACL。

**Current baseline:**

- MemOS maturity plan Task 1-45 已完成并推送。
- 全量测试、编译、NAS 打包与验包已多次通过。
- `/diagnostics` 和 `/scheduler/status` 已能暴露 queue health、失败/重试状态、oldest pending、高风险写入审计等治理信号。

**Principle:** 新一轮优先做验收、运行手册、诊断采样和小硬化；只有 diagnostics 或真实使用证据证明需要时，才进入重依赖阶段。

---

## Task 1: Release acceptance one-shot script

Goal: provide a single local command that verifies the current release candidate before NAS overlay deployment.

- [x] Add `scripts/run-release-acceptance.ps1`.
- [x] Chain existing verification: pytest, compileall, NAS package build, NAS package verify, plan checklist sanity, and `git diff --check`.
- [x] Keep the script local and deterministic; it does not deploy to NAS or mutate service data.

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
git diff --check
```

---

## Task 2: NAS operator acceptance checklist

Goal: make post-deploy verification explicit for a NAS GUI/operator workflow.

- [x] Document the exact post-overlay checks: `/health`, `/diagnostics`, `/scheduler/status`, MCP endpoint reachability, and package version evidence.
- [x] Include expected diagnostics fields for queue health and governance audit.
- [x] Include rollback notes that avoid destructive data operations.

---

## Task 3: Diagnostics snapshot command

Goal: make it easy to collect a bounded support snapshot from a running service without adding a dashboard.

- [x] Add a script or documented command that fetches `/health`, `/diagnostics`, and `/scheduler/status` into timestamped JSON files.
- [x] Redact API keys and avoid collecting raw memory contents.
- [x] Verify the output shape can be shared for troubleshooting.

---

## Task 4: Queue trigger decision record

Goal: make Redis/dashboard/LLM escalation decisions evidence-led.

- [x] Define concrete signs that SQLite scheduler is insufficient.
- [x] Define signs that diagnostics are insufficient and a dashboard/subgraph is warranted.
- [x] Define signs that deterministic feedback proposals are insufficient and LLM planner work is justified.

---

## Task 5: Release notes template

Goal: make each future release easier to ship and audit.

- [x] Add a short release-notes template covering changes, verification evidence, NAS package path, known warnings, and rollback notes.
- [x] Link the acceptance script and NAS operator checklist.
