# NAS 部署和 MCP 接入

这份文档给 NAS 图形界面用户使用。目标是把 `global_context_db` 部署成一个长期运行的公共记忆服务。

## 架构

Docker 项目会启动两个容器：

- `global_context_db-app-1`：REST 后端，端口 `8000`
- `global_context_db-mcp-1`：MCP 服务，端口 `8001`

数据放在 Docker 卷里：

- `/data/gcd_v2.sqlite3`
- `/data/lancedb_v2`
- `/data/artifacts`
- `/data/snapshots`

不要直接操作这些文件，外部工具只通过 REST 或 MCP 访问。

## 第一次安装

1. 把项目放到 NAS 目录，例如：

```text
共享文件夹/docker/SR_AI/global_context_db
```

2. 确认目录里存在：

```text
docker-compose.yaml
Dockerfile
app/
docs/
pyproject.toml
README.md
```

3. 在 Docker / Container Manager 中进入“项目”。
4. 点击“创建”。
5. 选择：

```text
global_context_db/docker-compose.yaml
```

6. 创建并启动项目。

## Compose 文件规则

本 NAS 项目使用：

```text
docker-compose.yaml
```

不要同时保留：

```text
docker-compose.yml
```

如果两个文件同时存在，NAS 图形界面可能继续读取旧配置，导致更新看起来成功但代码没有变。

## 端口

```text
REST: http://NAS_IP:8000
MCP:  http://NAS_IP:8001/mcp
```

例如：

```text
REST: http://192.168.10.5:8000
MCP:  http://192.168.10.5:8001/mcp
```

## 验证

打开：

```text
http://NAS_IP:8000/health
```

治理版应看到：

```text
version: 0.1.2-governance
```

继续打开：

```text
http://NAS_IP:8000/diagnostics
http://NAS_IP:8000/snapshots
```

如果 `/diagnostics` 是 404，说明容器里的代码还是旧的，需要删除旧镜像后重新部署。

## OpenClaw / MCP 客户端配置

服务名称：

```text
global_context_db
```

传输类型：

```text
HTTP 流式传输
```

URL：

```text
http://NAS_IP:8001/mcp
```

如果有 HTTP 请求头设置，可以加：

```text
Accept: application/json, text/event-stream
```

注意：`/mcp` 不是普通网页。直接用浏览器打开出现 `Missing session ID` 是正常的，MCP 客户端会先发 initialize 建立会话。

## 更新流程

1. 在 Windows 本机生成更新包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1
```

2. 把生成的 zip 覆盖到 NAS：

```text
S:\项目开发\全局数据库\release\global_context_db.zip
```

3. 在 NAS 的 `docker/SR_AI` 这一层解压，覆盖同名 `global_context_db` 目录。
4. 在 Docker 项目里确认 Compose 配置内容是新的。
5. 停止项目。
6. 删除旧镜像：

```text
global_context_db-app
global_context_db-mcp
```

7. 不要删除卷，不要删除 `/data`。
8. 回项目，点击重新部署。

只删除容器不够；旧镜像还在时，重新部署可能继续运行旧代码。

## 常见问题

### Docker Hub 打开镜像是 404

正常。`global_context_db-app` 和 `global_context_db-mcp` 是 NAS 本地构建的镜像，不是 Docker Hub 上的公开镜像。

### `/health` 新了，但 `/diagnostics` 是 404

说明 Compose 配置更新了，但镜像代码没重建。删除旧镜像后重新部署。

### OpenClaw 报 fetch failed

先确认 NAS 端：

```text
http://NAS_IP:8000/health
http://NAS_IP:8000/diagnostics
```

如果 REST 正常，再重新添加 OpenClaw 的 MCP 服务配置：

```text
http://NAS_IP:8001/mcp
```

## 本机命令部署

如果不是 NAS 图形界面，也可以在项目目录运行：

```bash
docker compose -f docker-compose.yaml up -d --build
```
