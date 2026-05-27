# MemOS → Global Context DB 借鉴与重构路线

> 日期：2026-05-27
> 参考项目：MemTensor/MemOS（本地参考路径：`S:\项目开发\全局数据库\_reference_repos\MemOS`）
> 当前项目：`S:\项目开发\全局数据库\global_context_db`
> 详细执行计划：`docs/superpowers/plans/2026-05-27-memos-maturity-rebuild.md`

---

## 1. 总判断

MemOS 和 Global Context DB 目标高度相似：都是给 LLM/Agent 做长期记忆、检索、治理和自我演化。我们的项目现在已经有 NAS-first、REST/MCP、SQLite、LanceDB、asset manifest、session capture 等基础，但还不成熟，主要缺：稳定后台调度、反馈纠错闭环、组件边界、生命周期治理和多 cube 组合策略。

结论：**借鉴 MemOS 的成熟产品架构，而不是把它整包替换进来。** 现在要直接抄“结构、接口、状态机、handler 分层和治理闭环”；重依赖能力延后。

---

## 2. 现在直接抄进来

### 2.1 MemCube → Context Cube（已完成 v0.1，后续增强组合策略）

MemOS 的 Multi-Cube 思路很关键：不同用户、项目、Agent、知识库必须有隔离和可组合边界。

当前已完成：

- `context_cubes`
- `cube_bindings`
- memories/assets/sessions/improvement/promotions 支持 `cube_id`
- search/recall 支持 `cube_id` / `cube_ids`
- REST/MCP cube 工具

后续补：

- 默认 cube resolver：按 `user_id / agent_id / project_path / session_id` 自动归属。
- readable/writable cube 组合：私有 cube + shared cube + kb cube。
- cube snapshot/export/import。

### 2.2 MemReader → Reader fast/fine 分层（fast 已完成）

MemOS 把输入先读成统一 memory item，再进入存储/检索/治理。这个经验必须保留。

当前已完成 fast mode：

- `ReaderItem`
- `read_text_fast()`
- `read_session_event_fast()`
- `read_asset_manifest_fast()`
- `read_tool_trace_fast()`
- memory/document/session/asset/control 入口写 reader metadata

下一步：

- reader output 进入 `memory_candidates`。（已完成）
- 通过 REST/MCP 暴露 candidate 创建、列表、promotion 和 lifecycle 查询。（已完成）
- 增加 evidence/provenance/span 字段规范。（已完成：`ReaderEvidence`、`ReaderEvidenceSpan`、`memory_evidence.source_span`）
- fine mode 第一版骨架已完成：先用确定性 marker 抽取 `Decision/Preference/Todo/Fact/Insight/Warning`，输出 candidates + source quote + hallucination quality 标记；真实 LLM 抽取后置。

### 2.3 MemScheduler → SQLite Scheduler（下一阶段最高优先级）

MemOS 的 scheduler 成熟点不是“Redis 本身”，而是：队列、优先级、状态跟踪、handler、监控、失败恢复。我们先用 SQLite 抄状态机。

要新增到 `improvement_tasks`：

```text
retry_count
max_retries
next_run_at
claimed_at
claimed_until
worker_id
queue_name
last_error
```

新增：

```text
app/scheduler/service.py
tests/test_scheduler.py
```

核心函数：

```text
claim_next_task(queue_name, worker_id)
complete_task(task_id)
fail_task(task_id, error)
release_expired_claims()
retry_failed_tasks()
run_pending_tasks(limit)
```

状态机：

```text
pending -> running -> done
pending -> running -> failed
running + lease expired -> pending
failed + retry_count < max_retries -> pending
failed + retry_count >= max_retries -> failed
```

### 2.4 Memory Feedback → 纠错/补充/归档闭环

MemOS 的 feedback 不是简单评论，而是把自然语言反馈变成标准 memory 操作。我们先做手动 action apply。

新增表：

```text
memory_feedback
memory_feedback_actions
```

第一版 action：

```text
update
archive
add_evidence
create_memory
reject
```

后面再做 LLM 自动生成 action proposal。

当前已补第一版 proposal 骨架：不直接接 LLM，先用 deterministic planner 从反馈文本生成可审核 action proposal，状态为 `proposed`，不会自动修改正式 memory；审核后仍走同一套 `apply_memory_feedback()`。

新增调用面：

```text
POST /memory-feedback/{feedback_id}/propose-actions
gcd_propose_memory_feedback_actions
```

### 2.5 Components + Handlers → 组件初始化和 API/MCP 分层

MemOS 把 component init、handler、scheduler、reader、feedback 拆开。当前 `api.py` / `mcp_server.py` / `repo.py` 已偏大，继续堆会失控。

新增：

```text
app/runtime/components.py
app/handlers/memory_handler.py
app/handlers/asset_handler.py
app/handlers/session_handler.py
app/handlers/cube_handler.py
app/handlers/scheduler_handler.py
app/handlers/feedback_handler.py
```

原则：

```text
API/MCP -> handler -> service -> repo/vector store
```

### 2.6 Memory lifecycle / provenance / version

MemOS 的 textual metadata 里有 source、status、version、history、archived memory 等思想。我们已经有 `memory_versions`、`memory_evidence`，但还缺统一 lifecycle events。

新增：

```text
memory_lifecycle_events
memory_candidates
GET  /memories/{memory_id}/lifecycle
POST /memory-candidates
GET  /memory-candidates
POST /memory-candidates/{candidate_id}/promote
gcd_list_memory_lifecycle_events
gcd_create_memory_candidate
gcd_list_memory_candidates
gcd_promote_memory_candidate
```

状态建议：

```text
candidate
active
verified
stale
archived
deleted
conflicted
```

### 2.7 Hook/plugin runtime → 轻量事件队列（当前实现）

第三方 worker、OpenClaw、NAS 扩展需要稳定接入点，但当前阶段不做重插件系统，也不让主服务执行外部脚本。

本阶段落点：

- `hook_subscriptions`：声明关注的 `hook_name`、`target_kind/target_ref`、状态和 metadata。
- `hook_events`：事件只入队或记录 `no_subscriber`，由外部 worker 查询后处理。
- Domain services now emit lifecycle events for memory, session, asset, artifact, analysis, and scan operations into the hook queue.
- REST/MCP：创建订阅、发事件、列事件、标记 dispatched。
- 安全边界：GCD 只记录/排队事件，不执行任意插件代码。

---

## 3. 后面再引入

| 能力 | 为什么后置 | 什么时候做 |
|---|---|---|
| Reader fine mode LLM 抽取 | 确定性骨架已完成；真实 LLM 仍需要配置、成本、质量评估 | Scheduler + Feedback 稳定后 |
| Redis Streams / consumer group | 当前 NAS 单机先用 SQLite 验证语义 | 多 worker 或并发压力出现后 |
| Complex plugin governance / marketplace | Current phase only needs event queues; GCD must not execute arbitrary plugin code | After hook queue is used by real workers |
| Graph memory / subgraph | 现在先用 SQLite + LanceDB + evidence | lifecycle/feedback 数据积累后 |
| Dashboard | 先保证服务层稳定 | Scheduler/Feedback/lifecycle 可视化需要时 |
| Reranker / agentic search | 依赖更多模型和策略 | 基础 recall 质量瓶颈明确后 |
| User manager / ACL | 当前是个人 NAS 服务 | 真多用户共享时 |

---

## 4. 暂时不要抄

- Parametric Memory。
- Activation Memory / KV cache。
- LoRA / model adaptation。
- 企业多租户权限和云平台计费。
- 把 OCR/ASR/ffmpeg/PDF 重解析塞进 GCD 主服务。
- 直接替换为 MemOS 整套运行时。

原因：这些会把当前 NAS-first 服务变成另一个大平台，短期不能提高稳定性，反而增加维护难度。

---

## 5. 开发顺序

### 已完成

1. Context Cube v0.1。
2. Reader fast mode v0.1。
3. SQLite Scheduler。
4. Memory Feedback 基础表和手动 apply。
5. Runtime Components + Handlers。
6. Lifecycle events + reader candidates。
7. Lifecycle/candidate REST + MCP 调用面。
8. Reader evidence/provenance/span 规范。
9. Reader fine mode 非 LLM 骨架。

### 再下一轮

10. Feedback action proposal 非 LLM 骨架。
11. Hook/plugin runtime 非重依赖骨架。
12. Hook runtime domain event emission.
13. LLM feedback action proposal.
14. Redis scheduler.
15. dashboard / graph memory.

---

## 6. 每阶段验证

每个代码阶段完成前必须跑：

```powershell
python -m pytest -q
python -m compileall app tools
git status --short
```

阶段提交：

```powershell
git add <changed files>
git commit -m "feat: ..."
git push
```

---

## 7. 下一步明确任务

当前进入 **Task 11: Hook/plugin runtime 非重依赖骨架**：只做 hook 订阅、事件入队、列表查询和人工标记 dispatched；不执行任意外部代码，不做插件市场。
