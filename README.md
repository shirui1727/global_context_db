# Global Context DB

Global Context DB 是部署在 NAS 上的公共记忆库，用来给 Codex、OpenClaw、Claude Code、桌面端和浏览器插件共享长期记忆与上下文。

它不是普通笔记软件。核心目标是：多个 AI 工具通过同一个后端访问长期记忆、文档和采集内容，而不是各自保存一份孤立上下文。

## 当前能力

- 长期记忆：写入、查询、更新、删除、去重。
- 文档入库：文本、文件、公开 URL。
- 资料采集：网页剪藏、RSS、批量 URL。
- 治理能力：审计日志、版本历史、诊断统计、误删保护。
- NAS 接入：Docker 部署，远程 MCP 地址。
- 桌面管理：连接设置、测试连接、搜索、记忆管理、治理查看。

## 关键地址

- REST: `http://NAS_IP:8000`
- Health: `http://NAS_IP:8000/health`
- MCP: `http://NAS_IP:8001/mcp`

`/health` 返回服务名、版本、数据目录、SQLite 路径和 MCP 配置。`/diagnostics` 返回统计、审计、失败摘要和重复候选。

## MCP 工具名

主工具名使用 `gcd_*` 前缀：

- `gcd_add_memory`
- `gcd_search_memories`
- `gcd_list_memories`
- `gcd_update_memory`
- `gcd_delete_memory`
- `gcd_ingest_text`
- `gcd_search_context`
- `gcd_diagnostics`
- `gcd_export_snapshot`
- `gcd_list_snapshots`
- `gcd_restore_snapshot`

兼容旧客户端时，也提供：

- `memory_search`
- `memory_export_snapshot`
- `memory_restore_snapshot`

## 本地运行

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## NAS / Docker 运行

```bash
docker compose up -d --build
```

NAS 项目只保留一个部署文件：

```text
docker-compose.yml
```

不要再创建或保留 `docker-compose.yaml`，避免 NAS Docker GUI 读取错文件。

## 手动快照

导出快照：

```bash
curl -X POST http://NAS_IP:8000/snapshots
```

恢复快照：

```bash
curl -X POST http://NAS_IP:8000/snapshots/restore
```

恢复前务必确认快照来自本系统导出。

## NAS 手动更新包

在 Windows 本机生成 NAS 覆盖包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1
```

生成结果：

```text
S:\项目开发\全局数据库\release\global_context_db.zip
```

这个 zip 的外层目录固定是 `global_context_db`。在 NAS 的 `docker/SR_AI` 这一层解压，覆盖同名项目目录即可。

更新包不会包含：

- `data`
- `.git`
- `node_modules`
- `docker-compose.yaml`

## 桌面端

```bash
cd desktop
npm install
npm run dev
```

打开桌面端后，在 Settings 里切换到 NAS 地址，例如：

```text
http://192.168.10.5:8000
```

然后点击测试连接，确认服务名、版本、数据目录和 MCP 地址显示正确。

## 设计原则

- NAS 是公共数据层。
- MCP 是 AI 工具优先入口。
- REST 是管理、调试和桌面端入口。
- 外部工具不要直接操作数据库文件。
- 长期记忆和完整会话流水分层处理。
