# Frontier memory absorption notes

这份文档记录 v0.3 之后继续吸收的外部经验。目标不是追热点，而是把 Global Context DB 打磨成 NAS 上可长期运行、可恢复、可诊断的 agent memory/control plane。

## 参考来源

- LangGraph memory 文档：明确区分 short-term memory 和 long-term memory，短期记忆随线程/会话 checkpoint 走，长期记忆进入跨会话 store。
- Mem0 论文：强调面向生产 agent 的长期记忆需要增量抽取、更新、异步总结、工具调用和向量检索，而不是把全量对话塞进上下文。
- Generative Agents：经典架构是 memory stream + reflection + planning + retrieval，原始事件不等于长期记忆，反思/总结是独立过程。
- MCP Authorization / Security Best Practices：远程工具必须重视授权、用户 consent、token audience validation，禁止 token passthrough，避免 confused deputy。

## 对 Global Context DB 的吸收判断

### 1. 当前方向是对的

v0.3 已经把记忆拆成：

- `memory`: 长期稳定事实、偏好、决策、经验。
- `document`: 文档/chunk。
- `asset`: NAS 资产、位置、版本、派生产物。
- `session`: agent 过程记录、事件、trace。
- `improvement`: 可追踪的重建、补索引、恢复、提升任务。

这和前沿实践里的“短期状态 + 长期记忆 + 过程可观测 + 改进队列”是同一条线。

### 2. 不要做全量记忆

长期记忆不能等于完整聊天记录。完整聊天记录应该进入 `session_events`；只有经过确认、总结或提升的内容才进入 `memories`。

v0.3.1 的重点应该是：

- `session_events` 保存过程。
- `handoff` 提供接手摘要。
- `improvement_tasks` 决定哪些内容需要被总结、提升、重建。
- 人或确定性规则确认后，再写入 `memories`。

### 3. 检索优化优先级高于复杂 ingestion

前沿经验反复指向一个点：agent 记忆系统最容易坏在“召回一堆差不多相关但不真正有用的内容”。

因此下一步优先做：

- 查询分域路由。
- 结构化 handoff。
- context budget。
- 结果去重。
- freshness / trust / status / domain 权重。
- evidence 标注。

先不要急着做复杂实体图谱。

### 4. MCP 安全必须前置

Global Context DB 是 NAS 上的共享记忆和资产控制面，MCP 写入工具必须更保守。

下一步应该加：

- 工具级写入开关。
- 高风险工具 action audit。
- `api_key` 不允许落入 session trace。
- asset URI allow/deny 继续作为硬边界。
- `gcd_forget`、`gcd_restore_snapshot`、`gcd_improve(execute=true)` 这类工具需要更强确认。

## v0.3.1 已吸收

- `get_resume_context` 返回结构化 `handoff`：
  - `current_focus`
  - `recent_progress`
  - `next_steps`
  - `risks`
  - `tools_used`
  - `open_task_count`
- session events 继续作为原始过程记录，handoff 只是确定性摘要视图。

## v0.3.2 已吸收

- `ResumeContextRequest` 增加 `include_raw_events`，agent 可以只拿 handoff，不拿完整事件流水。
- `ResumeContextRequest` 和 `RecallRequest` 增加 `context_budget_chars`，避免恢复上下文过量膨胀。
- session event / trace 写入统一过滤敏感字段：
  - `api_key`
  - `authorization`
  - `bearer`
  - `cookie`
  - `password`
  - `secret`
  - `token`
  - `x-api-key`
- `gcd_get_resume_context` 和 `gcd_recall` 暴露预算与 raw event 控制参数。

## v0.3.3 已吸收

- 新增 `memory_evidence`，长期 memory 能指回 session event、document chunk、asset、audit log 或人工来源。
- 新增 `memory_promotion_proposals`，session 内容进入长期 memory 前先生成提案。
- 新增 REST:
  - `POST /memory-promotions`
  - `GET /memory-promotions`
  - `PATCH /memory-promotions/{proposal_id}`
  - `POST /memory-promotions/{proposal_id}/review`
  - `POST /memories/{memory_id}/evidence`
  - `GET /memories/{memory_id}/evidence`
- 新增 MCP:
  - `gcd_create_memory_promotion`
  - `gcd_list_memory_promotions`
  - `gcd_review_memory_promotion`
  - `gcd_add_memory_evidence`
  - `gcd_list_memory_evidence`
- `/diagnostics` 增加 memory promotion 状态计数。

## v0.3.4 已吸收

- 新增 memory quality report，先做诊断，不自动改写长期记忆。
- 新增 REST:
  - `GET /memories/quality`
- 新增 MCP:
  - `gcd_memory_quality_report`
- `/diagnostics` 增加 memory quality 摘要。
- 报告当前输出：
  - `low_evidence`: active 但没有 evidence 的记忆候选。
  - `stale`: status 已 stale/deprecated、`metadata.valid_until` 过期或带 `stale_reason` 的候选。
  - `conflicts`: 同 scope/tag 下带明显相反标记的保守冲突候选。
  - `summary`: status/trust/source 分布。
- 冲突检测保持保守规则，只负责提出候选，不做语义裁判。

## v0.3.5 建议清单

已先吸收两项最小闭环：

- `POST /memories/quality/enqueue-improvements` 和 `gcd_enqueue_memory_quality_improvements` 可以把 quality report 候选转成 `improvement_tasks`。
- 新增任务类型：
  - `verify_memory_evidence`
  - `refresh_stale_memory`
  - `resolve_memory_conflict`
- `POST /retrieval/eval` 和 `gcd_run_retrieval_eval` 可以跑固定 query 夹具，返回 domain/id 命中率。
- 当前 eval 不引入新表，作为测试和人工验收入口；稳定后再扩成持久化评测集。

## v0.3.6 已吸收

- `SearchRequest.context_budget_chars` 开始真正约束普通搜索返回结果。
- `POST /search`、`POST /documents/search`、`POST /recall`、`gcd_search_context`、`gcd_recall` 都会返回 `budget` 元数据。
- 搜索预算当前按结果顺序保留，超预算时停止追加；如果第一条结果本身超过预算，会截断第一条文本并标记 `truncated=true`。
- 这一步先解决上下文膨胀，不改变排序算法。

## v0.3.7 已吸收

- 新增资产分析 manifest 入口：
  - `POST /assets/{asset_id}/analysis-manifest`
  - `gcd_register_asset_analysis_manifest`
- 入口用于承接外部 worker 对视频、图片、文稿的刮削结果，不在 GCD 内部直接跑 OCR/ASR/关键帧。
- manifest 可以批量登记 `thumbnail`、`keyframe`、`ocr_text`、`asr_text`、`scene_summary`、`embedding_text`、`embedding_visual`、`probe_metadata` 等 artifact。
- 带 `text` 的 artifact 会写入 asset 域向量索引，让视频 ASR、图片 OCR、场景摘要能被 `/assets/search` 和聚合搜索召回。
- asset 的 `analysis_status` 和 `last_analysis_manifest` metadata 会随 manifest 更新。

## v0.3.8 已吸收

- 新增 `tools/media_manifest_worker.py`，作为外部媒体刮削 worker 的无依赖样板。
- 支持生成 scan item：
  - 稳定 `asset_key`
  - SHA-256 checksum
  - size/modified_at/media_type/asset_kind
- 支持目录级 scan-run manifest，递归收集图片、视频、文稿，跳过 `.git`、`data`、`node_modules`、`__pycache__` 等噪声目录。
- 支持为文本类文稿生成 analysis manifest，并把文本写入 `/data/artifacts/<asset_id>/...`。
- 图片和视频当前生成 `probe_metadata` 占位 artifact，后续可以接 ffprobe/ffmpeg/OCR/ASR/视觉模型替换。
- `media_manifest_worker.py` 现在也支持 `--post-url` / `--api-key`，可以直接把 scan-run 或 analysis-manifest 推送到 GCD REST。
- NAS 打包和验包脚本已要求包含该 worker。

## v0.3.9 absorbed

- `format=raw|handoff|brief` is tightened: `brief` suppresses heavy arrays and returns compact counts; unknown formats are rejected.
- High-risk MCP write tools now emit `mcp.high_risk_write` audit actions, covering memory update/delete, feedback apply, promotion review, asset update, and similar paths.
- `tools/retrieval_eval_fixture.py` provides 20 fixed project cases across memory/document/asset/session and is wired into `/retrieval/eval`, `gcd_run_retrieval_eval`, and NAS package verification.
- `tools/media_manifest_worker.py` now supports `--ffprobe`, `--ocr-text-file`, and `--asr-text-file` adapters. Heavy media processing remains outside GCD; GCD registers manifests and artifacts only.
- `/diagnostics` now exposes governance signals such as pending promotions and audit write/high-risk counts.
- `memory_evidence.source_span.metadata` can carry provenance fields such as `document_chunk_id`, `asset_artifact_id`, `session_event_id`, selector, and quote_hash.
- `POST /memories/hygiene/enqueue` and `gcd_enqueue_memory_hygiene` enqueue candidates into `memory_hygiene`; scheduler output is review proposals only and does not mutate formal memory automatically.
- Lightweight SQLite `memory_relations` index is available via REST/MCP. Current edge types are `shared_tag`, `supported_by`, and `duplicate_candidate`. This is not a graph database and does not replace the SQLite + LanceDB backbone.
- Scheduler hardening after v0.3.9 adds queue-health observability without Redis: `queue_health`, pending/failed/retry-state counts by queue, oldest pending timestamps, and REST/MCP surface verification.
- NAS package verification now requires scheduler, diagnostics, hygiene, relation-index, and storage repo files so recent hardening cannot be silently omitted from overlay bundles.

## Future trigger conditions

- Redis Streams: introduce only after real multi-worker or remote concurrency pressure appears.
- LLM planner: introduce only after manual feedback apply and deterministic proposals have usage samples.
- Dashboard/subgraph: build only after `memory_relations` data proves useful.
- User manager / ACL: add only after real multi-user sharing needs appear.

## Current conclusion

The next direction is not stuffing in more data, but keeping this loop tight:

```text
complete process capture -> deterministic handoff -> evidence-based promotion -> domain-aware retrieval -> measurable recall
```

That path fits the current NAS experiment better than importing a large memory platform wholesale.
