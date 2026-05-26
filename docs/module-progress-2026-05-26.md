# 模块级开发进度报告（2026-05-26）

## 总体判断

当前仓库 `S:\项目开发\全局数据库\global_context_db` 已从早期 NAS 共享记忆库推进到 v0.3 架构阶段。开发重点已经从基础部署与快照能力，扩展到 memory / asset / session / improvement / retrieval 五大域协同。

当前状态判断：

- 已进入 **v0.3 功能实现中后期**
- 核心代码已大规模落地
- 测试已开始补齐
- 仍存在提交前收尾问题（至少包括测试导入路径问题）

## Git 状态摘要

- 分支：`main`
- 最近已提交版本停留在 **2026-05-15** 一组 NAS 部署/MCP/打包相关提交
- 当前工作区存在大量未提交改动：
  - 已跟踪修改：16 个文件
  - 新增目录：`app/assets`、`app/control`、`app/files`、`app/improvements`、`app/sessions`、`tests`、`tools`
  - `git diff --stat` 约 **4830 行新增 / 297 行删除**

说明本轮不是小修，而是一次版本级扩展。

## 模块级进度

### 1. API 层（`app/api.py`）

**状态：高完成度，接口面已显著扩展。**

已覆盖的能力：

- 基础入口：`/health`、`/diagnostics`
- 高层 agent 入口：`/remember`、`/recall`、`/forget`、`/improve`
- 快照：创建、列出、恢复
- 文档：ingest / upload / ingest-url / search
- 文件引用兼容接口：`/file-references`
- 资产域：创建、列表、搜索、版本、位置、artifact、analysis manifest、scan run、向量维护
- 会话域：session CRUD、events、traces、summaries、model usage、resume context
- improvement 任务队列接口
- 抓取与 feed/crawl 入口
- memory 正式域：memory、promotion、evidence、quality、audit logs
- 检索评估：`/retrieval/eval`

**判断：** API 已经不是简单 CRUD，而是完整平台门面，接口设计基本成型。

### 2. MCP 层（`app/mcp_server.py`）

**状态：高完成度。**

已暴露的 MCP 能力包括：

- memory 全套工具
- memory evidence / promotion / quality
- audit / diagnostics / snapshots
- asset 全套工具
- session 全套工具
- improvement 工具
- remember/recall/forget 高层入口
- file reference 兼容工具
- context search / retrieval eval

**判断：** MCP 已从“给 AI 调记忆”升级为“给 AI 调整个平台能力”。这是项目成熟度提升的明确信号。

### 3. 存储层（`app/storage/repo.py`）

**状态：本轮开发核心重心，完成度高。**

当前 repo 已承载多域持久化：

- documents / chunks
- file references
- assets / locations / versions / artifacts / scan runs
- sessions / events / traces / summaries / model usage
- improvements
- memories / versions / evidence / promotion proposals
- audit logs
- captures / feeds / feed items / crawl jobs

**判断：** 数据模型已经从单库单表思路扩展到一个真正的“全局上下文数据库”基础设施层。`repo.py` 是本轮改动最大的事实核心。

### 4. Memory 域（`app/memory/service.py`）

**状态：高完成度。**

已实现方向：

- memory 创建、查询、更新、删除
- evidence 关联
- promotion proposal 创建/更新/审核
- quality report：低证据、过期、冲突检测
- quality 候选转 improvement task
- version / audit 记录

**亮点：**

- 不再把长期记忆当成随意写入的 KV，而是开始引入 **证据链、审核、冲突发现、质量治理**。

**判断：** 这是 v0.3 最有产品价值的升级之一。

### 5. Retrieval 域（`app/retrieval/service.py`）

**状态：中高完成度。**

已实现方向：

- 分域 context search
- context budget 裁剪
- retrieval eval
- expected domain/id 命中率评估

**判断：** 已超出“能搜到”的阶段，开始关注“能不能稳定命中正确对象”。这对 agent 系统非常关键。

### 6. Asset 域（`app/assets/service.py`）

**状态：高完成度，属于本轮新增重点。**

已实现方向：

- 资产创建/更新/搜索
- asset identity / URI 规范化
- allow/deny prefix 权限策略
- asset version 管理
- asset artifact 注册
- analysis manifest 回写
- scan run
- vector rebuild
- preflight / fresh install preflight
- file reference 兼容层

**亮点：**

- 资产已不是简单文件引用，而是具备 **身份、版本、位置、派生产物、扫描批次、权限策略** 的治理模型。

**判断：** 资产域架构已经站住，是项目区别于普通 memory store 的关键能力。

### 7. Session 域（`app/sessions/service.py`）

**状态：高完成度。**

已实现方向：

- session 创建、列出、更新
- session event / trace / summary / model usage
- resume context 生成
- handoff 结构化输出
- 敏感字段过滤
- context budget 裁剪

**亮点：**

- 已开始解决“窗口丢失后如何恢复开发现场”的真实问题。

**判断：** 这是面向 Codex / Claude Code / LobsterAI 等 agent 实际使用场景的重要模块。

### 8. Improvement 域（`app/improvements/service.py`）

**状态：中高完成度。**

已实现方向：

- improvement task 创建、列出、更新
- `/improve` 统一入口
- 部分确定性任务执行

**判断：** 改进队列已经有骨架和部分执行能力，但仍偏 orchestration 层，后续还可以继续扩充执行器。

### 9. Control 层（`app/control/service.py`）

**状态：轻量但明确。**

功能是统一封装：

- remember
- recall
- forget
- improve

**判断：** 这是对 agent 友好的薄门面，复杂性基本下沉到 domain service，结构合理。

### 10. Schema 层（`app/core/schemas.py`）

**状态：高完成度。**

当前 schema 已覆盖：

- session / event / trace / summary / usage
- improvement
- remember / recall / forget
- memory / evidence / promotion
- file reference
- asset / artifact / scan run / analysis manifest
- retrieval eval
- capture / feed / crawl
- snapshot

**判断：** schema 扩展说明接口层和服务层不是临时拼接，已经在统一数据契约。

## 测试覆盖进度

### `tests/test_v03_sessions_improvements.py`

覆盖：

- session event/trace/resume context
- secret redaction + budget
- asset version 变更触发 improvement task
- remember / recall / improve
- memory promotion -> evidence
- memory quality report
- quality candidate enqueue
- retrieval eval
- search/recall budget
- v0.3 表计数

**判断：** 这组测试更像 v0.3 主线验收测试。

### `tests/test_assets.py`

覆盖：

- asset key 变更/版本变更
- missing/recover
- deny prefix
- file reference 兼容
- analysis manifest 注册与索引
- fresh install preflight

**判断：** 资产域测试相对扎实。

### `tests/test_media_manifest_worker.py`

覆盖：

- 资产类型判断
- scan item
- analysis manifest
- scan run
- post_json
- CLI 提交 manifest

**判断：** worker 已从脚本雏形推进到“带测试的工具模块”。

## 当前明确问题

### 1. pytest 当前不全绿

已观测到的直接错误：

- `tests/test_media_manifest_worker.py`
- `ModuleNotFoundError: No module named 'tools'`

这说明：

- `tools/media_manifest_worker.py` 已存在
- `tools/__init__.py` 也存在
- 但当前测试执行环境下导入路径仍未整理好

这属于 **提交前应优先收口的问题**。

### 2. 仍处于大量未提交状态

当前工作树尚未整理成一组清晰提交，意味着：

- 架构扩展已做完大半
- 但版本边界还没正式封口

## 阶段判断

如果按里程碑来分：

### 已完成

- NAS 部署与打包链路
- REST + MCP 双入口
- v0.3 数据域建模
- asset / session / improvement / memory governance 主体实现
- retrieval eval 与 context budget
- media manifest worker 初版
- 一轮主线测试补充

### 正在开发 / 待收尾

- 测试执行环境与导入路径整理
- 全量 pytest 验证
- 未提交改动整理入库
- 发布前最终联调

## 当前进度评估

主观评估：

- **架构完成度：85%+**
- **核心功能实现度：75%~85%**
- **可发布度：60%~70%**（主要卡在验证/收尾，不是卡在无代码）

## 建议的下一步优先级

1. 修复 `tools` 模块测试导入问题
2. 跑全量 `pytest`
3. 确认打包脚本与验证脚本通过
4. 将本轮 v0.3 改动整理提交
5. 再做一次 NAS 发布包验证
