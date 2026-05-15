# global-context-db

NAS 上的公共记忆服务。

它不是单机笔记软件，而是给 Codex、OpenClaw、浏览器插件、桌面管理器等工具共用的记忆数据库。

## 现在的方向

- 数据放 NAS
- 后端通过 Docker 跑
- 外部工具只连 API，不直接碰数据库文件
- AI 工具优先通过 MCP 连接
- 桌面端作为管理界面
- 先做记忆、采集、搜索，再做更复杂的知识层

## 新库

当前默认使用新库文件：

- `data/gcd_v2.sqlite3`
- `data/lancedb_v2`

## 运行

```bash
uvicorn app.main:app --reload
```

## MCP 入口

AI 工具应该优先连接 MCP：

```bash
gcd-mcp
```

当前 MCP 工具：

- `gcd_health`
- `gcd_add_memory`
- `gcd_search_memories`
- `gcd_list_memories`
- `gcd_update_memory`
- `gcd_delete_memory`
- `gcd_ingest_text`
- `gcd_search_context`

## 记忆接口

REST 接口保留给桌面、浏览器插件、后台管理和调试：

- `POST /memories`
- `GET /memories`
- `GET /memories/search`
- `PATCH /memories/{id}`
- `DELETE /memories/{id}`

## 说明

第一版不做账号体系，不做平台绕过，不做云盘实时数据库。云盘只适合备份。
