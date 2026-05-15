# Global Context DB

一个部署在 NAS 上的公共记忆库，给 Codex、OpenClaw、Claude Code 这类工具共享长期记忆、文档和采集内容。

## 现在能做什么

- `/memories`：写入、查询、更新、删除长期记忆
- `/documents`：导入文本文件或公开 URL
- `/captures`：保存网页采集记录
- `/feeds`：手动管理 RSS 源
- `/audit-logs`：查看记忆操作审计
- `/memories/{id}/versions`：查看记忆版本历史
- `desktop/`：桌面管理壳，负责连接、采集、搜索、治理

## 运行方式

### 本地

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Docker

```bash
docker compose up --build
```

### 桌面端

```bash
cd desktop
npm install
npm run dev
```

## 设计原则

- 本地优先，默认不要求普通用户安装 Docker
- NAS 作为公共数据层
- 访问和管理交给 Codex、OpenClaw 等工具
- 数据要可追溯、可去重、可恢复

## 下一步

- 记忆去重策略继续细化
- 桌面端增加更完整的治理页面
- 预留会话归档和跨工具恢复能力
