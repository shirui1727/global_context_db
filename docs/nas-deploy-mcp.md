# NAS 部署和 MCP 接入

第一版推荐同时启动两个服务：

- REST 管理接口：`http://NAS_IP:8000`
- MCP 工具接口：`http://NAS_IP:8001/mcp`

## 启动

在 NAS 或支持 Docker 的机器上进入项目目录：

```bash
docker compose up -d --build
```

## 检查 REST

```bash
curl http://NAS_IP:8000/health
```

正常返回：

```json
{"ok": true}
```

## MCP 地址

给支持远程 MCP 的 AI 工具填写：

```text
http://NAS_IP:8001/mcp
```

## 本机 stdio MCP

如果某个工具只支持本机 stdio MCP，可以在项目环境里使用：

```bash
gcd-mcp
```

## 数据位置

Docker 数据卷里保存：

- `/data/gcd_v2.sqlite3`
- `/data/lancedb_v2`

外部工具不要直接访问这些文件，只通过 MCP 或 REST 访问。
