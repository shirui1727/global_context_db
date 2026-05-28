# Current architecture v0.3

这是当前权威架构说明。旧 `nas-memory-architecture.md` 保留为历史设计草稿，不再作为实现导航。

## 定位

Global Context DB 是部署在 NAS 上的多 agent 共享上下文数据库。它不是网盘，也不是完整媒体库，而是给 Codex、OpenClaw、LobsterAI、桌面端和浏览器插件共同使用的 REST/MCP 后端。

核心原则：

- 原始 NAS 大文件不复制进数据库。
- 长期记忆、文档、资产、会话过程分域治理。
- 所有重要写入可追踪。
- 检索默认分组，不把不同数据域混成一锅。
- 先做可恢复、可诊断、可验收，再做复杂 OCR/ASR/图谱。

## 数据域

### memory

长期稳定事实、偏好、项目决策、agent 经验。

主表：

```text
memories
memory_versions
memory_evidence
memory_promotion_proposals
```

入口：

```text
POST /memories
GET /memories
GET /memories/search
PATCH /memories/{memory_id}
DELETE /memories/{memory_id}
POST /memories/{memory_id}/evidence
GET /memories/{memory_id}/evidence
POST /memory-promotions
GET /memory-promotions
PATCH /memory-promotions/{proposal_id}
POST /memory-promotions/{proposal_id}/review
GET /memories/quality
POST /memories/quality/enqueue-improvements
POST /memories/hygiene/enqueue
POST /memories/relations/rebuild
GET /memories/relations
```

MCP：

```text
gcd_add_memory
gcd_search_memories
gcd_list_memories
gcd_update_memory
gcd_delete_memory
gcd_add_memory_evidence
gcd_list_memory_evidence
gcd_create_memory_promotion
gcd_list_memory_promotions
gcd_review_memory_promotion
gcd_memory_quality_report
gcd_enqueue_memory_quality_improvements
gcd_enqueue_memory_hygiene
gcd_build_memory_relation_index
gcd_list_memory_relations
```

长期 memory 不应该直接来自 session 流水。推荐流程：

```text
session_events -> memory_promotion_proposals -> review/promote -> memories + memory_evidence
```

`memory_evidence` 让长期记忆能指回来源，例如：

```text
session_event
document_chunk
asset
audit_log
manual
```

`/memories/quality` 是诊断入口，不自动修改数据。当前报告包含：

```text
low_evidence: active 但没有 evidence 的长期记忆候选
stale: status 已 stale/deprecated、metadata.valid_until 过期或带 stale_reason 的候选
conflicts: 同 scope/tag 下带明显相反标记的保守冲突候选
summary: status/trust/source 分布
```

冲突检测只做保守规则，不做语义裁判；它的作用是把“值得人工确认/进入 improvement queue”的项目挑出来。

`/memories/quality/enqueue-improvements` 会把诊断候选变成可追踪任务：

```text
low_evidence -> verify_memory_evidence
stale -> refresh_stale_memory
conflicts -> resolve_memory_conflict
```

这些任务默认只排队，不自动修改记忆。`/memories/hygiene/enqueue` 会把同类候选放入 `memory_hygiene` 队列；scheduler 执行后只返回 review proposal，不直接改写正式 memory。`memory_relations` 是轻量 SQLite 关系索引，不是完整图数据库。当前边类型：shared_tag / supported_by / duplicate_candidate。

### document

文档和 chunk。适合文本、Markdown、网页正文、上传文件解析后的文本。

主表：

```text
documents
chunks
```

入口：

```text
POST /documents/ingest
POST /documents/upload
POST /documents/ingest-url
POST /documents/search
```

### asset

NAS 资产治理层。保存逻辑资产、位置、内容版本、派生产物登记、manifest 扫描批次。

主表：

```text
assets
asset_locations
asset_versions
asset_artifacts
asset_scan_runs
```

入口：

```text
POST /assets
GET /assets
GET /assets/{asset_id}
PATCH /assets/{asset_id}
POST /assets/search
POST /assets/scan-runs
GET /assets/{asset_id}/versions
GET /assets/{asset_id}/locations
POST /assets/{asset_id}/artifacts
POST /assets/{asset_id}/analysis-manifest
GET /assets/{asset_id}/artifacts
PATCH /asset-artifacts/{artifact_id}
```

兼容入口：

```text
POST /file-references
GET /file-references
PATCH /file-references/{file_reference_id}
```

MCP：

```text
gcd_add_asset
gcd_search_assets
gcd_list_assets
gcd_update_asset
gcd_list_asset_versions
gcd_list_asset_artifacts
gcd_register_asset_artifact
gcd_register_asset_analysis_manifest
gcd_run_asset_scan
gcd_rebuild_asset_vectors
```

视频、图片、文稿刮削采用外部 worker + manifest 回写：

```text
1. scanner 只提交原文件 manifest: uri / asset_key / checksum / size / modified_at / media_type。
2. GCD 创建或更新 asset、location、version，不复制原文件。
3. media worker 读取允许范围内的原文件，生成派生产物：
   - 图片: probe_metadata / thumbnail / ocr_text / scene_summary / embedding_visual
   - 视频: probe_metadata / thumbnail / keyframe / asr_text / ocr_text / scene_summary
   - 文稿: probe_metadata / ocr_text 或 embedding_text；可解析文本时也可走 document ingest
4. worker 调用 analysis-manifest，把 artifact URI、文本内容摘要、状态、时间戳等写回。
5. GCD 登记 asset_artifacts，并把 asr_text / ocr_text / scene_summary / embedding_text 这类文本进入 asset 域向量索引。
```

推荐 artifact URI 放在 `/data/artifacts/...`，会随 GCD snapshot 备份。大体积派生产物也可以放 `smb://...`，但仍走 allow/deny 前缀校验。

仓库自带一个轻量 worker 样板：

```text
python tools/media_manifest_worker.py S:/NAS/docs/brief.md --mode scan-item --uri-prefix smb://NAS/docs --root S:/NAS/docs
python tools/media_manifest_worker.py S:/NAS/library --mode scan-run --uri-prefix smb://NAS/library --scope-prefix smb://NAS/library
python tools/media_manifest_worker.py S:/NAS/docs/brief.md --mode analysis-manifest --asset-id <asset_id> --artifact-root data/artifacts
python tools/media_manifest_worker.py S:/NAS/library --mode scan-run --uri-prefix smb://NAS/library --scope-prefix smb://NAS/library --post-url http://127.0.0.1:8000/assets/scan-runs --api-key <key>
```

它只做无外部依赖的 manifest 生成和文本类文稿抽取。真实生产刮削应在这个样板基础上接：

```text
ffprobe/ffmpeg -> probe_metadata, thumbnail, keyframe
OCR 引擎 -> ocr_text
ASR 引擎 -> asr_text
视觉/多模态模型 -> scene_summary, embedding_visual
文档解析器 -> embedding_text 或 document ingest
```

### session

agent 工作过程层。保存会话、事件、工具 trace、summary、模型使用量。它解决“窗口记录丢了，开发到哪里了”的恢复问题。

主表：

```text
agent_sessions
session_events
session_traces
session_summaries
session_model_usage
```

入口：

```text
POST /sessions
GET /sessions
GET /sessions/{session_id}
PATCH /sessions/{session_id}
POST /sessions/{session_id}/events
GET /sessions/{session_id}/events
POST /sessions/{session_id}/traces
GET /sessions/{session_id}/resume-context
POST /context/resume
```

MCP：

```text
gcd_start_session
gcd_record_session_event
gcd_record_tool_trace
gcd_get_resume_context
gcd_end_session
```

`resume_context` 返回：

```text
handoff
recent_events
open_tasks
relevant_memories
relevant_assets
relevant_documents
warnings
budget
```

其中 `handoff` 是确定性接手包，包含：

```text
current_focus
recent_progress
next_steps
risks
tools_used
open_task_count
```

可控参数：

```text
include_raw_events: 是否返回原始 session events，默认 true
context_budget_chars: 返回上下文预算，默认 12000
format: handoff/brief/raw 预留字段，当前主要使用 handoff
```

session event 和 trace 写入前会过滤敏感字段：

```text
api_key
authorization
bearer
cookie
password
secret
token
x-api-key
```

### improvement

确定性改进任务队列。用于记录重建向量、重建 artifact、补索引、处理 missing、提升 session memory 等任务。

主表：

```text
improvement_tasks
```

入口：

```text
POST /improvements
GET /improvements
PATCH /improvements/{task_id}
POST /improve
```

MCP：

```text
gcd_create_improvement_task
gcd_list_improvement_tasks
gcd_update_improvement_task
gcd_improve
```

当前可确定性执行：

```text
rebuild_vectors
cleanup_stale_vectors
```

当前只排队不自动执行：

```text
summarize_session
promote_session_memory
refresh_asset_artifacts
reindex_asset
resolve_missing_asset
verify_untrusted_memory
verify_memory_evidence
refresh_stale_memory
resolve_memory_conflict
```

## 高层控制面

给 agent 使用的薄入口：

```text
POST /remember
POST /recall
POST /forget
POST /improve
```

MCP：

```text
gcd_remember
gcd_recall
gcd_forget
gcd_improve
```

这些不是替代精确 domain API，而是给 agent 快速写入/召回/软删除/创建改进任务。

## 检索边界

`POST /search` 默认返回分组结构：

```json
{
  "query": "...",
  "mode": "context_search",
  "groups": {
    "memory": [],
    "document": [],
    "asset": [],
    "session": []
  }
}
```

可用模式：

```text
memory_search
document_search
asset_search
context_search
```

`POST /retrieval/eval` 是最小检索验收入口。它接收固定 query 列表和期望 domain/id，返回 `domain_hit_rate`、`id_hit_rate` 和每条 case 的命中情况，用来证明“能稳定找准”而不只是“能搜到”。

`POST /search`、`POST /documents/search`、`POST /recall` 和 MCP `gcd_search_context`/`gcd_recall` 支持 `context_budget_chars`。返回结构包含：

```text
budget.requested_chars
budget.used_chars
budget.original_used_chars
budget.truncated
```

当结果超过预算时，服务会按排序保留前面的结果，必要时截断第一条长文本，避免一次召回把 agent 上下文撑爆。

## 权限与安全

资产 URI 使用 allow/deny 前缀：

```text
GCD_ASSET_ALLOW_PREFIXES
GCD_ASSET_DENY_PREFIXES
```

deny 优先于 allow。命中 deny 的资产写入会被拒绝，并写入 audit log。

MCP 写入工具可由 `GCD_REQUIRE_MCP_API_KEY` 和 `GCD_API_KEY` 保护。

## 当前非目标

v0.3 不承诺：

- 直接扫描 NAS 文件系统。
- 自动 OCR/ASR/关键帧生成。
- 自动 LLM 总结并覆盖长期记忆。
- 完整知识图谱或独立 graph database。当前只提供 SQLite `memory_relations` 关系索引。
- 复杂多租户权限系统。

## 验收

当前基础验收：

```text
python -m compileall app
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/package-nas-update.ps1
powershell -ExecutionPolicy Bypass -File scripts/verify-nas-package.ps1 <zip>
```

服务验收：

- `/health` 正常。
- `/diagnostics` 显示 memory/document/asset/session/improvement 计数。
- `/diagnostics` 显示 memory promotion 计数和 memory quality 摘要。
- `/assets/search` 不返回 memory。
- `/search` 默认分组返回。
- `/memories/quality` 能返回低证据、过期和冲突候选。
- `/memories/quality/enqueue-improvements` 能把质量候选转换成 improvement tasks。
- `/retrieval/eval` 能返回固定 query 的 domain/id 命中率。
- `gcd_get_resume_context` 能返回结构化 handoff。
- resume context 支持 `include_raw_events` 和 `context_budget_chars`。
- session trace 不保存明文 token/api_key/password/authorization。
- asset version 变化能产生 improvement task。
