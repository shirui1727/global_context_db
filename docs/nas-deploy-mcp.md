# NAS 部署和 MCP 接入

第一版推荐在 NAS 上用 Docker 同时启动两个服务：

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

正常返回类似：

```json
{
  "ok": true,
  "service": "global-context-db",
  "data_dir": "/data",
  "sqlite_path": "/data/gcd_v2.sqlite3",
  "mcp": {
    "host": "0.0.0.0",
    "port": 8001,
    "path": "/mcp"
  }
}
```

## MCP 地址

给支持远程 MCP 的 AI 工具填写：

```text
http://NAS_IP:8001/mcp
```

例如你的 NAS IP 是 `192.168.10.5`：

```text
http://192.168.10.5:8001/mcp
```

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

外部工具不要直接访问这些文件，只通过 MCP 或 REST 访问。
