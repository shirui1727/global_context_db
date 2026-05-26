# Global Context DB 第三版架构说明

这版不再把系统简单叫做“NAS 公共记忆服务”。更准确的定位是：

> Global Context DB 是一个面向多 agent 的共享上下文数据库。它同时保存长期协作记忆、NAS 资产索引和资产使用经验，但三类数据必须分域治理，不能混成一锅自由 metadata。

第三版仍在摸索期，允许继续调整表结构和接口。当前优先级不是做完全部媒体理解能力，而是先把边界、身份、状态、审计和检索入口立住，避免越用越乱。

## 核心目标

1. 多个 AI 工具通过同一个 REST / MCP 后端读写上下文。
2. 通用聊天记忆保留，用来让 agent 理解用户、项目、偏好和历史决策。
3. NAS 文件不搬进数据库，只保存稳定引用、资产身份、元数据、摘要、标签和派生产物索引。
4. 资产事实和聊天记忆分开治理。聊天记忆可以帮助理解搜索意图，但不能直接替代资产事实。
5. 所有重要写入都要可追踪，至少知道谁写的、写了什么、目标是什么。

## 三个数据域

### 1. memory：长期协作记忆

保存“人、偏好、长期事实、项目背景、agent 经验”。

典型内容：

- 用户偏好的输出格式、语言风格、工作流。
- 某个项目的长期约束、背景、决策。
- agent 曾经踩过的坑和修复经验。
- 重要配置位置、工具接入方式、协作约定。

当前表：`memories`

关键字段：

- `content`
- `tags`
- `user_id`
- `agent_id`
- `session_id`
- `conversation_id`
- `memory_type`
- `context_domain = memory`
- `status`
- `source_kind`
- `trust_level`
- `metadata`

当前去重规则：

```text
sha256(user_id, agent_id, session_id, conversation_id, memory_type, content)
```

这个规则只解决字面重复，不解决语义重复。第三版先承认这个边界。

### 2. asset：NAS 资产索引

保存“文件在哪里、它是什么、它是否可用、它和哪些派生产物有关”。

典型内容：

- NAS 原始文件 URI。
- 文件名、媒体类型、大小、checksum。
- 资产类型：图片、视频、PDF、工程文件、音频、通用资产。
- 资产身份：`asset_key`。
- 版本组：`version_group_id`。
- 摘要、标签、状态、可信等级。
- 缩略图、OCR、ASR、关键帧、时间轴摘要等派生产物索引。

当前表：`file_references`

关键字段：

- `uri`：当前物理引用，仍保持唯一。
- `id`：当前仍由 `sha256(uri)` 生成，用于兼容已有引用。
- `asset_key`：资产级身份。优先使用调用方提供的资产 ID；没有时使用 `checksum`；再没有时退回 `sha256(uri)`。
- `checksum`：内容 hash。现在只是字段，但已经纳入重复候选诊断。
- `asset_kind`
- `media_type`
- `status`
- `analysis_status`
- `trust_level`
- `version_group_id`
- `derived_artifacts`
- `metadata`

当前资产身份规则：

```text
asset_key = payload.asset_key or checksum or sha256(uri)
```

这不是最终方案，但比只靠路径更稳。后续 NAS 扫描器应补充更强的身份信息，例如 inode/file id、mtime、快速 hash、完整 checksum、感知 hash。

### 3. usage：资产使用经验

第三版暂时不单独建表，但必须作为明确的数据域保留下来。短期可以写在 asset 的结构化 `metadata` 里，字段命名要稳定。

典型内容：

- 这个素材上次用于哪个项目。
- 哪个版本被选中。
- 哪个素材虽然叫 final 但已废弃。
- 人工确认过的推荐/禁用记录。
- 某个素材适合哪些风格、平台、客户。

建议 metadata 字段：

```json
{
  "usage_notes": [],
  "project_refs": [],
  "selected_in": [],
  "rejected_in": [],
  "verified_by": null,
  "verified_at": null
}
```

后续如果使用经验变多，应拆成 `asset_usage_notes` 或 `asset_events` 表，而不是继续塞进自由 metadata。

## 状态模型

### memory.status

建议值：

- `active`
- `stale`
- `deprecated`
- `archived`
- `deleted`

### memory.trust_level

建议值：

- `agent_inferred`
- `user_provided`
- `verified`
- `disputed`

### asset.status

建议值：

- `active`
- `missing`
- `moved`
- `stale`
- `deprecated`
- `archived`
- `deleted`

### asset.analysis_status

建议值：

- `pending`
- `indexed`
- `partial`
- `failed`
- `stale`
- `verified`

### asset.trust_level

建议值：

- `unverified`
- `auto_extracted`
- `agent_inferred`
- `human_verified`
- `disputed`

第三版代码不强制枚举，目的是保留试错空间；但写入方应尽量使用这些固定值。

## 检索原则

统一搜索入口可以查全部上下文，但必须支持分域：

```text
context_domain = memory
context_domain = asset
kind = memory
kind = file_reference
```

原则：

1. 聊天记忆可以帮助理解“上次那个”“我常用的”“这个项目里”的语境。
2. 资产事实必须落到 `file_references` 或派生产物索引上。
3. 搜索结果必须能看出它来自 memory 还是 asset。
4. 搜索结果必须带 `status`、`trust_level`、`source_kind`。
5. 暂时仍是轻量向量检索，不要把它宣传成可靠的视觉/视频检索。

## NAS 文件原则

`global_context_db` 不是网盘，也不是媒体库本体。

NAS 原始资料库继续保存：

```text
documents/
photos/
videos/
projects/
design-assets/
```

`global_context_db` 保存：

```text
uri
asset_key
checksum
media_type
asset_kind
size_bytes
summary
tags
status
analysis_status
derived_artifacts
vector index
audit logs
```

快照只备份 Global Context DB 自己的数据：SQLite、LanceDB、`/data/artifacts`。外部 NAS 原文件不会被复制进快照。

## 三种资料模式

### 引用模式

默认模式。原文件不复制，只登记路径和可检索描述。

适合：

- 视频素材
- 图片库
- PDF
- 工程资料
- 设计源文件

### 托管模式

只适合小文件或采集副本。

适合：

- 小 Markdown
- 网页 HTML
- 截图
- 小型导出文本

### 提取模式

原文件仍在 NAS，数据库保存派生产物索引。

适合：

- 图片 OCR / EXIF / 缩略图 / 视觉描述。
- 视频封面 / 关键帧 / ASR / OCR / 时间轴摘要。
- PDF 文本抽取 / 页级摘要。

第三版只建立字段和治理边界，不假装已经完成图片/视频深度理解。

## 审计与治理

当前已做：

- memory 创建、去重、更新、删除写入审计。
- asset 创建、更新写入审计。
- asset 可通过 REST / MCP 更新状态、摘要、标签、可信等级、分析状态和派生产物索引。
- `/diagnostics` 返回 memory 重复候选、asset 状态统计、asset 重复候选、近期失败任务和近期审计日志。
- 快照导出/恢复 SQLite、LanceDB、artifacts。
- 向量表升级时会检测缺失治理列，并用现有行重建表结构。

仍需补：

- file reference 的完整版本历史。
- asset 删除/移动的专门语义接口。
- 多 worker 扫描锁和幂等任务表。
- 人工确认和冲突裁决流程。

## 当前接口边界

### REST

- `POST /memories`
- `GET /memories`
- `GET /memories/search`
- `PATCH /memories/{memory_id}`
- `DELETE /memories/{memory_id}`
- `POST /file-references`
- `GET /file-references`
- `PATCH /file-references/{file_reference_id}`
- `POST /search`
- `GET /diagnostics`

`POST /search` 支持：

```json
{
  "query": "黄昏建筑航拍",
  "top_k": 5,
  "context_domain": "asset",
  "kind": "file_reference"
}
```

### MCP

新增/保留的关键工具：

- `gcd_add_memory`
- `gcd_search_memories`
- `gcd_update_memory`
- `gcd_add_file_reference`
- `gcd_list_file_references`
- `gcd_update_file_reference`
- `gcd_search_context`
- `gcd_diagnostics`

## 当前明确不承诺

第三版不承诺以下能力已经完成：

- 自动全盘 NAS 扫描。
- 视频关键帧抽取。
- 视频 ASR / OCR / 镜头切分。
- 图片视觉 embedding。
- 感知 hash 近重复聚类。
- 按项目/客户/目录的访问控制。
- 10TB 素材库的长期命中率。

这些是后续阶段要做的工程，不应该用当前轻量索引冒充。

## 下一阶段整改路线

### 必改

1. 建立 NAS 扫描任务表，记录 pending/running/failed/stale/deleted。
2. 增加资产更新接口，支持标记 missing/moved/stale/deprecated。
3. 给 file reference 增加版本历史或 asset event 表。
4. 建立 metadata 写入规范，限制 agent 自由散写。
5. 增加真实业务查询回归集。

### 应改

1. 图片：缩略图、OCR、EXIF、基础视觉描述。
2. 视频：封面、时长、分辨率、关键帧、ASR、时间轴摘要。
3. 搜索：关键词 + 向量 + 结构化过滤 + rerank。
4. 重复治理：checksum、快速 hash、感知 hash、版本组。
5. 使用经验：拆出 `asset_usage_notes` 或 `asset_events`。

### 可优化

1. 首选结果机制：最终版、人工确认版、常用版优先。
2. 质量仪表盘：无 checksum、无摘要、未验证、过期、失败、重复候选。
3. 批量修正：错误标签/摘要一次修正，全局生效。
4. 冷数据归档策略。

## 验收口径

当前成功标准不是“能写能读”，而是：

1. memory 和 asset 能分开写、分开搜、统一搜。
2. asset 搜索结果能看出 URI、资产身份、状态、可信等级。
3. 重复资产能在 `/diagnostics` 里暴露候选。
4. 错误写入能通过审计日志追到来源。
5. 文档明确说明当前没完成的图片/视频深度理解能力。

等这些成立以后，才进入“真能找准素材”的验收：固定业务查询集、top-k 命中率、重复率、过期率、三个月后回归。
