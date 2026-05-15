# git 参考项目吸收笔记

这些项目不用照搬，主要吸收架构思想。

## mcp-memory-service

最接近本项目目标：一个独立记忆服务，被多个工具连接。

吸收：

- REST API + MCP 双入口
- 记忆服务独立运行
- agent/user/conversation 维度
- 远程连接和权限控制

## mem0

它证明“记忆层”可以作为 AI 应用的独立组件。

吸收：

- `user_id / agent_id / run_id` 这类上下文字段
- add/search/list/update/delete 的标准记忆接口
- 后续可补历史记录和记忆评分

## redis-agent-memory-server

重点是短期记忆和长期记忆分层。

吸收：

- working memory 适合会话临时状态
- long-term memory 适合长期知识和偏好
- 后续可加后台整理任务

## neo4j-agent-memory

图数据库适合关系复杂以后再上。

暂不吸收：

- 第一版不引入 Neo4j
- 不先做复杂知识图谱

## openclaw-mem0

很适合做第一批兼容接口。

吸收：

- `GET /health`
- `POST /memories`
- `GET /memories`
- `GET /memories/search`
- `DELETE /memories/{id}`

## swarmvault

适合未来做“资料库/知识库层”，不是第一版核心。

吸收：

- 原始资料归档
- 人工审核和知识条目
- 冲突检查

## 本项目第一阶段结论

先做成一个干净、稳定、工具可连的 NAS 记忆服务。桌面、浏览器插件、MCP、OpenClaw 都是客户端。
