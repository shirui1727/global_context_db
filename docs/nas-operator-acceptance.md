# NAS Operator Acceptance Checklist

这份清单用于 NAS 覆盖更新后确认 `global_context_db` 已经运行在新版本，并且核心治理诊断可用。

## 0. 本地发布包验收

在把 zip 覆盖到 NAS 前，先在 Windows 仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-release-acceptance.ps1 -OutputDir ..\release
```

通过标准：

- pytest 通过。
- `python -m compileall app tools` 通过。
- `scripts\package-nas-update.ps1` 生成 `global_context_db.zip`。
- `scripts\verify-nas-package.ps1` 返回 `Ok=True`。
- `git diff --check` 无错误。

## 1. 覆盖更新注意事项

1. 解压 `release\global_context_db.zip` 到 NAS Docker 项目目录，覆盖同名 `global_context_db` 项目目录。
2. 在 NAS Container Manager / Docker 项目里重新构建并启动。
3. **不要删除数据卷，不要删除 `data/`，不要删除外部 NAS 原始资料目录。**
4. 如果 `/health` 更新了但 `/diagnostics` 仍是 404，通常说明旧镜像还在；删除旧镜像后重新部署，但仍不要删除数据卷。

## 2. REST post-deploy checks

把 `NAS_IP` 替换成实际地址：

```powershell
$BaseUrl = "http://NAS_IP:8000"
Invoke-RestMethod "$BaseUrl/health"
Invoke-RestMethod "$BaseUrl/diagnostics"
Invoke-RestMethod "$BaseUrl/scheduler/status"
```

通过标准：

- `/health`
  - `ok = true`
  - `service = global-context-db`
  - 返回 `version`、`data_dir` 和 `mcp` 配置。
- `/diagnostics`
  - 返回 `storage`、`governance` 等顶层结构。
  - `governance.audit.high_risk_actions` 包含 `mcp.high_risk_write`。
  - `governance.audit.write_action_counts` 可用于查看最近写入动作统计。
  - `governance.improvement.queue_health` 存在。
  - `governance.improvement.pending_by_queue`、`failed_by_queue`、`retryable_failed_by_queue`、`exhausted_failed_by_queue`、`oldest_pending_by_queue` 存在。
- `/scheduler/status`
  - 返回 `queue_health`。
  - 返回 `pending_by_queue`、`failed_by_queue`、`retryable_failed_by_queue`、`exhausted_failed_by_queue`、`oldest_pending_by_queue`。

## 3. MCP reachability checks

MCP endpoint:

```text
http://NAS_IP:8001/mcp
```

最小连通性检查：

```powershell
Invoke-WebRequest "http://NAS_IP:8001/mcp" -Headers @{ Accept = "application/json, text/event-stream" }
```

说明：

- 浏览器或普通 HTTP 直开 `/mcp` 出现 `Missing session ID` 不代表服务坏了；streamable HTTP MCP 客户端会先 initialize 建立会话。
- 真正的工具面验收应使用 MCP 客户端调用：
  - `gcd_health`
  - `gcd_diagnostics`
  - `gcd_scheduler_status`

## 4. Diagnostics support snapshot

遇到部署或运行问题时，先采集有界诊断快照：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\collect-diagnostics-snapshot.ps1 -BaseUrl http://NAS_IP:8000 -OutputDir .\diagnostics-snapshots
```

该脚本只采集 `/health`、`/diagnostics`、`/scheduler/status`，并会递归脱敏常见 secret 字段。

## 5. Rollback notes

安全回滚：

1. 停止当前 Docker 项目。
2. 用上一份已验证的 `global_context_db.zip` 覆盖项目代码目录。
3. 重新构建镜像并启动。
4. 再次运行 `/health`、`/diagnostics`、`/scheduler/status`。

禁止操作：

- 不要删除 Docker volume。
- 不要删除 `global_context_db/data`。
- 不要删除外部 NAS 原始资料库。
- 不要用破坏性 git 或文件清理命令处理 NAS 数据目录。
