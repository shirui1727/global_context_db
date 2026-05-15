# Global Context DB

Global Context DB 是一个部署在 NAS 上的公共记忆库，用来给 Codex、OpenClaw、Claude Code、桌面端和浏览器插件共享长期记忆与上下文。

它不是普通笔记软件。它的核心目标是：让多个 AI 工具通过同一个 MCP / REST 后端访问长期记忆、文档和采集内容，而不是各自保存一份孤立上下文。

## 当前能力

- 长期记忆：写入、查询、更新、删除、去重。
- 文档入库：文本、文件、公开 URL。
- 资料采集：网页剪藏、RSS、批量 URL。
- 治理能力：审计日志、版本历史、诊断统计、误删保护。
- 快照能力：手动导出和恢复 SQLite、LanceDB、artifacts。
- NAS 接入：Docker 部署，远程 MCP 地址。

## 快速地址

把 `NAS_IP` 替换成你的 NAS IP，例如 `192.168.10.5`。

```text
REST:        http://NAS_IP:8000
Health:      http://NAS_IP:8000/health
Diagnostics: http://NAS_IP:8000/diagnostics
MCP:         http://NAS_IP:8001/mcp
```

部署成功后，`/health` 里应看到：

```json
{
  "ok": true,
  "service": "global-context-db",
  "version": "0.1.2-governance"
}
```

## NAS Docker 安装

### 1. 准备目录

在 NAS 共享文件夹里放到类似目录：

```text
docker/SR_AI/global_context_db
```

项目目录里应包含：

```text
app/
docs/
desktop/
Dockerfile
docker-compose.yaml
pyproject.toml
README.md
```

不要把 `data`、`.git`、`node_modules` 放进更新包。

### 2. 创建 Docker 项目

在 NAS Docker / Container Manager 里：

1. 进入“项目”。
2. 点击“创建”。
3. 选择 `global_context_db/docker-compose.yaml`。
4. 创建并启动项目。

本项目使用的 Compose 文件名是：

```text
docker-compose.yaml
```

不要同时保留 `docker-compose.yml`，避免 NAS 图形界面读错旧配置。

### 3. Docker Compose 配置

当前 `docker-compose.yaml` 会启动两个服务：

- `app`：REST 后端，端口 `8000`
- `mcp`：远程 MCP 服务，端口 `8001`

关键环境变量：

```yaml
GCD_DATA_DIR: /data
GCD_SQLITE_PATH: /data/gcd_v2.sqlite3
GCD_LANCEDB_DIR: /data/lancedb_v2
GCD_SERVICE_VERSION: 0.1.2-governance
```

MCP 服务额外使用：

```yaml
GCD_MCP_HOST: 0.0.0.0
GCD_MCP_PORT: 8001
GCD_MCP_PATH: /mcp
```

### 4. 验证

打开：

```text
http://NAS_IP:8000/health
```

继续确认：

```text
http://NAS_IP:8000/diagnostics
http://NAS_IP:8000/snapshots
```

`/diagnostics` 能返回统计信息，说明治理版已经真正跑起来。

## AI 工具配置

### OpenClaw / 支持远程 MCP 的客户端

新增 MCP 服务：

```text
服务名称：global_context_db
传输类型：HTTP 流式传输
URL：http://NAS_IP:8001/mcp
```

如果客户端允许填写 HTTP 请求头，可加：

```text
Accept: application/json, text/event-stream
```

通常 MCP 客户端会自动带这个头，不填也可以先测试。

### MCP 工具名

主工具名使用 `gcd_*`：

- `gcd_health`
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

兼容旧客户端：

- `memory_search`
- `memory_export_snapshot`
- `memory_restore_snapshot`

## 手动更新 NAS

在 Windows 本机生成更新包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1
```

生成结果：

```text
S:\项目开发\全局数据库\release\global_context_db.zip
```

更新步骤：

1. 解压 `global_context_db.zip`。
2. 覆盖 NAS 的 `docker/SR_AI/global_context_db` 目录。
3. 确认项目配置里是新的 `docker-compose.yaml` 内容。
4. 停止项目。
5. 删除旧镜像 `global_context_db-app` 和 `global_context_db-mcp`。
6. 不要删除数据卷，不要删除 `/data`。
7. 回到项目，重新部署。

只删除容器不够；如果镜像没删，NAS 可能继续用旧代码创建新容器。

## 快照备份

导出快照：

```bash
curl -X POST http://NAS_IP:8000/snapshots
```

列出快照：

```bash
curl http://NAS_IP:8000/snapshots
```

恢复快照：

```bash
curl -X POST http://NAS_IP:8000/snapshots/restore \
  -H "Content-Type: application/json" \
  -d "{\"snapshot_path\":\"/data/snapshots/your_snapshot.zip\"}"
```

恢复前请确认快照来自本项目导出。

## 本地开发

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

桌面端：

```bash
cd desktop
npm install
npm run dev
```

## 设计原则

- NAS 是公共数据层。
- MCP 是 AI 工具优先入口。
- REST 是管理、调试和桌面端入口。
- 外部工具不要直接操作 SQLite 或 LanceDB 文件。
- 长期记忆和完整会话流水分层处理。
