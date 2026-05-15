# NAS 部署和 MCP 接入

第一版推荐在 NAS 上用 Docker 同时启动两个服务：

- REST 管理接口：`http://NAS_IP:8000`
- MCP 工具接口：`http://NAS_IP:8001/mcp`

## Compose 文件规则

NAS Docker 项目只使用：

```text
docker-compose.yaml
```

不要保留 `docker-compose.yml`。如果目录里同时存在 `.yml` 和 `.yaml`，NAS GUI 可能继续读取旧文件，导致更新没有生效。

## 启动

在 NAS 或支持 Docker 的机器上进入项目目录：

```bash
docker compose up -d --build
```

如果使用 NAS 图形界面，项目路径应指向 `global_context_db/docker-compose.yaml`。

## 检查 REST

```bash
curl http://NAS_IP:8000/health
```

```bash
curl http://NAS_IP:8000/diagnostics
```

正常情况下，`/health` 会返回服务名、版本、数据目录、SQLite 路径和 MCP 配置。治理版版本号应为 `0.1.2-governance` 或更高。`/diagnostics` 会返回记忆、文档、捕获、审计和失败摘要。

## MCP 地址

给支持远程 MCP 的 AI 工具填写：

```text
http://NAS_IP:8001/mcp
```

例如你的 NAS IP 是 `192.168.10.5`：

```text
http://192.168.10.5:8001/mcp
```

## 工具名约定

主工具名统一使用 `gcd_*`。旧客户端如果误调用 `memory_search`，现在也会兼容转到同一套搜索实现。

## 快照

导出快照：

```bash
curl -X POST http://NAS_IP:8000/snapshots
```

恢复快照：

```bash
curl -X POST http://NAS_IP:8000/snapshots/restore
```

快照内容包含：

- SQLite 数据库
- LanceDB 数据目录
- artifacts
- manifest

## 桌面端连接 NAS

1. 打开桌面端。
2. 进入 Settings。
3. 后端地址填写 `http://NAS_IP:8000`。
4. 模式选择 NAS / 远程服务。
5. 点击测试连接。

桌面端只连接 NAS 上已经运行的服务，不会尝试在 NAS 上启动后端。

## 本机 stdio MCP

如果某个工具只支持本机 stdio MCP，可以在项目环境里使用：

```bash
gcd-mcp
```

## 数据位置

Docker 数据卷里保存：

- `/data/gcd_v2.sqlite3`
- `/data/lancedb_v2`
- `/data/artifacts`
- `/data/snapshots`

外部工具不要直接访问这些文件，只通过 MCP 或 REST 访问。
