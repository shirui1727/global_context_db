# Cognee absorption notes for v0.3

这份文档记录从本地 `git参考/cognee-main` 可以吸收进 Global Context DB 的经验，以及 v0.3 现在就能做的落地清单。

结论先放前面：v0.3 不应该把 Cognee 整个平台搬进来，也不应该现在就引入完整知识图谱栈。我们应该吸收它的“记忆控制面”设计，把当前已经打硬的 `memory / document / asset / context` 边界上面再加一层轻量 session、trace、improve 闭环。

## Cognee 真正值得看的点

Cognee 的核心定位不是单纯 RAG，也不是一个文件索引器，而是 memory control plane。它把 agent 记忆拆成几类生命周期：

- `remember`: 写入短期或长期记忆。
- `recall`: 按查询、session、dataset 找回上下文。
- `forget`: 删除或遗忘指定范围的数据。
- `improve`: 把 session、trace、feedback 等运行过程沉淀成更稳定的长期知识。

本地源码里几个可借鉴点：

- `cognee/__init__.py` 暴露的是很薄的 V2 memory API：`remember / recall / improve / forget`。
- `persist_sessions_in_knowledge_graph.py` 把指定 session 抽取出来，再通过 memify pipeline 沉淀到长期图谱。
- `persist_agent_trace_feedbacks_in_knowledge_graph.py` 把 agent trace、每步反馈、工具返回内容转成可沉淀材料。
- `global_context_index.py` 把全局上下文索引作为可重建的 improve 任务，而不是写入时一次性定死。
- session lifecycle migration 里有 `session_records` 和 `session_model_usage`，说明它把会话状态、模型使用量、错误数、last activity 作为一等数据。
- `cognee-mcp` 的测试强调 MCP 暴露面要克制：LLM 直连工具只保留少量稳定动词，内部 UI 工具有另一组边界。

这些思路和我们当前方向是契合的：底层数据先按 domain 治理，上层再提供 agent 友好的动词。

## 不要现在吸收的东西

v0.3 先别做这些：

- 不引入 Cognee 作为运行时依赖。
- 不上完整 graph database。
- 不做实体/关系抽取平台。
- 不做真实 OCR、ASR、缩略图、视频关键帧生成。
- 不做复杂多租户权限系统。
- 不做自动改写长期记忆的 LLM improve 流水线。

原因很简单：我们现在最需要的是 NAS 可部署、边界稳定、可验收。图谱和智能抽取以后能加，但现在加会把部署、调试、数据一致性都拖重。

## 应该吸收成什么

### 1. 轻量 memory control plane

在现有 REST/MCP 上新增四个高层动词，但内部仍调用已有 domain service：

```text
gcd_remember  -> 写 memory，或按 content_type 分流到 document/asset/session
gcd_recall    -> 聚合搜索，默认分组返回 memory/document/asset/session
gcd_forget    -> 软删除、archive、mark stale，不做物理删除
gcd_improve   -> 创建或执行改进任务，例如重建索引、补摘要、补 artifact、沉淀 session
```

REST 对应：

```text
POST /remember
POST /recall
POST /forget
POST /improve
```

这四个入口不是替代 `/assets`、`/memories`、`/documents`，而是给 agent 用的薄外壳。工程调试、精确写入、扫描恢复仍用 canonical domain API。

### 2. Session layer

新增 session 域，保存 agent 工作过程，而不是把过程噪声直接写进长期 memory。

建议表：

```text
agent_sessions
session_events
session_traces
session_summaries
session_model_usage
```

最小字段：

```text
agent_sessions:
  id
  source_agent
  project_path
  status
  started_at
  last_activity_at
  ended_at
  title
  summary
  metadata

session_events:
  id
  session_id
  event_type
  role
  content
  tool_name
  tool_args
  tool_result
  created_at
  metadata

session_traces:
  id
  session_id
  trace_id
  origin_function
  status
  memory_query
  memory_context
  method_params
  method_return_value
  error_message
  feedback_text
  created_at
  metadata

session_summaries:
  id
  session_id
  summary_kind
  content
  status
  created_by
  created_at
  metadata

session_model_usage:
  id
  session_id
  model
  tokens_in
  tokens_out
  cost_usd
  updated_at
```

第一版不需要完整复刻所有 agent 的原始日志，只要能记录 `session_start / user_prompt / tool_call / tool_result / assistant_note / pre_compact / session_end`。

### 3. Improve queue

Cognee 的 `improve` 值得吸收，但我们先做成确定性任务队列，不让 LLM 自动改长期事实。

建议表：

```text
improvement_tasks
```

字段：

```text
id
task_kind
target_domain
target_id
status
priority
reason
created_by
claimed_by
created_at
updated_at
finished_at
error_message
metadata
```

v0.3 支持的 `task_kind`：

```text
rebuild_vectors
summarize_session
promote_session_memory
refresh_asset_artifacts
reindex_asset
resolve_missing_asset
verify_untrusted_memory
cleanup_stale_vectors
```

执行规则：

- `pending -> running -> done/failed/skipped`
- 同一个 `target_domain + target_id + task_kind` 默认去重。
- `gcd_improve` 默认只创建任务或执行确定性任务。
- 需要 LLM 的任务先输出 proposal，不直接覆盖正式数据。

### 4. Agent hook ingestion

从 Cognee 的 Claude Code hook 思路吸收一组通用 hook，但命名做成我们自己的：

```text
POST /agent-hooks/session-start
POST /agent-hooks/user-prompt
POST /agent-hooks/tool-use
POST /agent-hooks/pre-compact
POST /agent-hooks/session-end
```

MCP 工具：

```text
gcd_start_session
gcd_record_session_event
gcd_record_tool_trace
gcd_get_resume_context
gcd_end_session
```

这些接口的目标不是“监控一切”，而是解决断窗、换 agent、上下文压缩之后能继续的问题。

### 5. Resume context

新增一个恢复上下文接口：

```text
POST /sessions/{session_id}/resume-context
POST /context/resume
```

返回结构：

```json
{
  "project_path": "...",
  "session": {},
  "recent_events": [],
  "open_tasks": [],
  "relevant_memories": [],
  "relevant_assets": [],
  "warnings": []
}
```

v0.3 先做确定性拼装：最近事件、session summary、未完成 improvement tasks、按 project_path 搜到的 memory/asset。不要现在做复杂生成式总结。

## v0.3 现在就能做的清单

### P0: NAS 覆盖前必须打磨

- 新增 `docs/cognee-absorption-v0.3.md`，作为 v0.3 设计入口。
- 新增 `/diagnostics` 字段：显示 session 表、improvement task 表计数。
- Fresh install 模式下明确推荐 `/assets`，把 `/file-references` 标为兼容别名。
- 保证 package zip 包含 v0.2 asset docs 和 v0.3 absorption docs。
- 跑通 `pytest`、`compileall`、NAS package verify。

### P1: Session 最小闭环

- 在 `app/storage/repo.py` 增加 session 五张表。
- 新建 `app/sessions/service.py`。
- 新增 REST：
  - `POST /sessions`
  - `GET /sessions`
  - `GET /sessions/{session_id}`
  - `PATCH /sessions/{session_id}`
  - `POST /sessions/{session_id}/events`
  - `GET /sessions/{session_id}/events`
  - `POST /sessions/{session_id}/traces`
  - `GET /sessions/{session_id}/resume-context`
- 新增 MCP：
  - `gcd_start_session`
  - `gcd_record_session_event`
  - `gcd_record_tool_trace`
  - `gcd_get_resume_context`
  - `gcd_end_session`
- 检索新增 `session_search`，但 `/search` 默认仍按 domain 分组，不混成一锅。

### P2: Improve 最小闭环

- 新增 `improvement_tasks` 表。
- 新建 `app/improvements/service.py`。
- 新增 REST：
  - `POST /improvements`
  - `GET /improvements`
  - `PATCH /improvements/{task_id}`
  - `POST /improve`
- 新增 MCP：
  - `gcd_create_improvement_task`
  - `gcd_list_improvement_tasks`
  - `gcd_update_improvement_task`
  - `gcd_improve`
- 把现有 asset vector rebuild 包装成一个 `rebuild_vectors` improvement task。
- asset version 变化、artifact stale、location missing 时自动创建对应 improvement task。

### P3: High-level memory verbs

- 新增薄外壳 REST：
  - `POST /remember`
  - `POST /recall`
  - `POST /forget`
- 新增薄外壳 MCP：
  - `gcd_remember`
  - `gcd_recall`
  - `gcd_forget`
- `remember` 支持 `content_type`：
  - `memory`
  - `document`
  - `asset`
  - `session_event`
- `recall` 默认返回分组结果，并支持 `session_id`、`project_path`。
- `forget` 只做软删除、archive、stale，不物理删除。

### P4: Tests

- session 创建、事件写入、trace 写入、结束 session。
- resume context 包含最近事件和相关 memory/asset。
- improvement task 去重、状态流转、失败记录。
- `gcd_improve` 能创建 rebuild vector task。
- `/recall` 不把结果混成旧扁平列表。
- `/remember` 按 `content_type` 分流正确。
- MCP 工具列表包含 v0.3 工具，旧 file reference 工具仍可用。

## 建议实施顺序

1. 先做 session tables + service + REST，不碰现有 memory/asset 逻辑。
2. 再做 MCP session tools，让 Codex/OpenClaw 能先把过程写进来。
3. 做 resume context，解决“窗口记录丢了，开发到哪里了”的真实痛点。
4. 做 improvement_tasks，把 v0.2 的 stale/missing/rebuild 变成可排队、可追踪。
5. 最后补 `remember / recall / forget / improve` 四个高层动词。

这条路线的好处是：每一步都能单独验收，NAS 部署失败面小，而且不会把已经打硬的 asset 层重新搅乱。

## v0.3 验收标准

- `/health` 正常。
- `/diagnostics` 能显示 memory、document、asset、session、improvement task 计数。
- 一个 agent 能创建 session、写事件、写工具 trace、结束 session。
- 窗口记录丢失时，`gcd_get_resume_context` 能返回最近进度、未完成任务和相关资产。
- asset 版本变化后能自动生成 `reindex_asset` 或 `refresh_asset_artifacts` 任务。
- `/search` 或 `/recall` 仍然按 domain 分组，不把 session 噪声污染长期 memory。
- NAS package verify 通过。

## v0.3 第一版实现状态

已实现：

- SQLite 新增 `agent_sessions`、`session_events`、`session_traces`、`session_summaries`、`session_model_usage`。
- SQLite 新增 `improvement_tasks`，支持去重、状态流转、状态计数。
- REST 新增 `/sessions*`、`/context/resume`、`/agent-hooks/*`、`/improvements*`。
- REST 新增 `/remember`、`/recall`、`/forget`、`/improve` 薄控制面。
- MCP 新增 `gcd_start_session`、`gcd_record_session_event`、`gcd_record_tool_trace`、`gcd_get_resume_context`、`gcd_end_session`。
- MCP 新增 `gcd_create_improvement_task`、`gcd_list_improvement_tasks`、`gcd_update_improvement_task`、`gcd_improve`。
- MCP 新增 `gcd_remember`、`gcd_recall`、`gcd_forget`。
- `/search` 默认分组增加 `session` domain。
- session event 写入向量库，`context_domain=session`，不会混进 memory。
- asset 版本变化自动创建 `reindex_asset`、`refresh_asset_artifacts` task。
- manifest scan 标记 missing 时自动创建 `resolve_missing_asset` task。
- `/diagnostics` 显示 session 和 improvement 状态分布。

第一版仍然保守处理的部分：

- `gcd_improve(execute=true)` 目前只确定性执行 `rebuild_vectors` / `cleanup_stale_vectors`。
- `summarize_session`、`promote_session_memory`、`refresh_asset_artifacts`、`reindex_asset`、`resolve_missing_asset`、`verify_untrusted_memory` 先进入任务队列，暂不自动改写正式数据。
- session summary 先支持人工写入，不做 LLM 自动总结。
- agent hook 先是通用 REST/MCP 接口，不绑定某一个具体客户端的本地 hook 文件格式。
