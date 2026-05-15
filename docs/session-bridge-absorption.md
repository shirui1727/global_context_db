# opal-bridge 会话桥吸收方案

## 定位

`opal-bridge` 对 `global_context_db` 的价值，不是替代记忆库，而是启发下一层能力：跨 agent 会话归档与恢复。

`global_context_db` 当前负责：

- 长期记忆
- 文档导入
- 语义搜索
- MCP/REST 统一访问

`opal-bridge` 启发的是：

- canonical session format
- canonical event
- 跨工具 session 转换
- 会话 resume 上下文生成

## 为什么有用

现在 `global_context_db` 已经能让 Codex、OpenClaw 等工具共享长期记忆。但长期记忆只是被筛选后的信息，不等于完整会话历史。

后续如果要让新 AI 快速接手一个项目，除了搜索长期记忆，还需要知道：

- 这个项目之前讨论过什么
- 哪些方案被否掉了
- 哪些命令跑过
- 哪些工具调用成功或失败
- 上一个 agent 停在什么状态

这就是 session bridge 层要解决的问题。

## 建议内部概念

第一阶段只设计，不实现。

未来可以引入 `canonical_event` 作为统一事件模型。每条事件至少包含：

- `source_agent`
- `session_id`
- `project_path`
- `role`
- `content`
- `tool_name`
- `tool_args`
- `tool_result`
- `created_at`
- `metadata`

原始 session 文件可以作为 artifact 保存，统一事件用于检索、摘要和恢复上下文。

## 与 memories 的边界

`memories` 保存长期、稳定、可复用的信息。

`canonical_event` 保存完整或半完整的会话流水。

不要把二者混在一起，否则长期记忆会被聊天噪声污染。正确关系是：

- session event 是原始过程资料
- memory 是从过程资料中提炼出的长期事实、偏好、决策和结论

## 后续预留能力

未来可以新增 MCP 工具：

- `gcd_ingest_session`：导入一段 agent 会话
- `gcd_search_sessions`：按项目、agent、时间、关键词搜索历史会话
- `gcd_resume_context`：给新 AI 汇总某个项目或会话的可恢复上下文

第一阶段不新增这些工具，只保留设计方向。

## 实施顺序建议

1. 收集 Codex、OpenClaw、Claude Code 的 session 样例。
2. 定义最小 `canonical_event` schema。
3. 做只读导入，不做双向转换。
4. 对 session events 建语义索引。
5. 做 `gcd_resume_context` 摘要工具。
6. 最后再考虑跨工具 resume 渲染。

## 当前结论

`opal-bridge` 应被吸收进 `global_context_db` 的第二阶段路线：会话层/事件层。第一版 NAS + MCP 记忆库保持稳定，不因为 session bridge 设计而扩大当前数据表和工具接口。
