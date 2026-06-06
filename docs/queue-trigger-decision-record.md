# Queue Trigger Decision Record

本记录用于判断什么时候才进入 Redis、dashboard/subgraph 或 LLM planner 阶段。默认原则：先看 diagnostics 和真实使用证据，不凭感觉加重依赖。

## 1. SQLite scheduler 何时不够

继续使用 SQLite scheduler 的条件：

- `/scheduler/status.queue_health` 能解释当前 backlog。
- `failed_by_queue` 主要是业务任务失败，而不是 claim/lease 竞争。
- `oldest_pending_by_queue` 没有持续增长到影响人工工作流。
- 单 NAS 或单 worker 运行足够。

考虑 Redis Streams / consumer group 的触发信号：

- 多 worker 或远程 worker 已经真实上线，并且出现重复 claim、lease 竞争或明显吞吐瓶颈。
- `pending_by_queue` 和 `oldest_pending_by_queue` 在多次采样中持续增长，单 worker 无法及时消化。
- `retryable_failed_by_queue` 很低但 backlog 仍持续堆积，说明主要瓶颈不是业务失败而是调度吞吐。
- NAS SQLite 写锁或 WAL checkpoint 成为可复现瓶颈，并有日志或诊断快照佐证。

不应触发 Redis 的情况：

- 只是想“更专业”。
- 当前只有本地/NAS 单 worker。
- backlog 是少量人工 review proposal，且 oldest pending 可接受。

## 2. Dashboard/subgraph 何时值得做

继续使用 `/diagnostics`、`/scheduler/status` 和 `memory_relations` REST/MCP 的条件：

- 运营问题能通过 JSON 诊断快照解释。
- relation index 主要用于局部排查 duplicate/support/shared-tag。
- 没有长期人工巡检和可视化需求。

考虑 dashboard/subgraph 的触发信号：

- 同一类治理问题需要频繁人工查看，并且 JSON 快照已经影响判断效率。
- `memory_relations` 数据量和使用频率证明图式导航有实际价值。
- 需要跨 memory、asset、session、feedback、scheduler queue 做人工 triage。
- 已有明确用户流程：例如每周 review stale/conflict/duplicate candidate，而不是单纯展示漂亮图。

不应触发 dashboard/subgraph 的情况：

- 只是 diagnostics 字段多。
- 还没有稳定使用 `memory_relations`。
- 没有明确操作者和决策动作。

## 3. LLM planner 何时值得做

继续使用 deterministic feedback proposals 的条件：

- 手动 feedback apply 使用量低。
- deterministic proposals 足以生成可 review 的 update/archive/add_evidence/create_memory action。
- 失败主要来自数据不足，而不是规则表达能力不足。

考虑 LLM planner 的触发信号：

- 已积累足够真实 feedback 样本，且 deterministic planner 经常生成不完整或过粗 action。
- 人工 review 反复需要从长文本反馈中拆分多条 action。
- 有稳定 LLM 配置、成本边界和质量验收集。
- LLM planner 只生成 proposal，不绕过 manual apply 和 audit。

不应触发 LLM planner 的情况：

- 没有真实 feedback 样本。
- 只是想自动化所有纠错。
- 无法验证输出质量或无法控制成本。

## 4. Evidence required before escalation

进入重依赖阶段前，至少保留：

- 一份 `collect-diagnostics-snapshot.ps1` 采样输出。
- 相关 pytest 或评测结果。
- 具体业务场景描述：谁在什么流程里被什么瓶颈卡住。
- 决策结论：为什么现有 SQLite/diagnostics/deterministic proposal 不够。

## 5. Status on 2026-06-06

Current evidence:

- Release acceptance passes locally.
- Runtime acceptance plan is complete.
- Field acceptance plan provides REST smoke, MCP smoke checklist, first-use workflow, diagnostics baseline, and NAS acceptance report template.
- No real NAS multi-worker queue pressure has been observed in this plan.
- No repeated dashboard triage workflow has been observed in this plan.
- No real feedback corpus showing deterministic proposal failure has been collected in this plan.

Decision:

- Redis Streams: **not triggered**.
- Dashboard/subgraph: **not triggered**.
- LLM planner: **not triggered**.
- User manager / ACL: **not triggered**.

Next review should use a real diagnostics snapshot and first-use workflow evidence, not preference or architecture aesthetics.
