# MemOS 成熟化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Global Context DB 从“能用的 NAS 记忆服务”重构成借鉴 MemOS 的成熟记忆系统：有 Cube 隔离/组合、Reader 入口、可恢复 Scheduler、Feedback 纠错、Runtime Components/Handlers，以及清晰生命周期。

**Architecture:** 不把 MemOS 整包搬进来；按 Apache-2.0 允许范围学习并复刻成熟设计模式，优先实现与当前 NAS + SQLite + LanceDB + REST/MCP 架构兼容的最小成熟内核。先做本地可靠性（SQLite 状态机、手动 apply、组件拆分），再引入 Redis、LLM fine reader、graph/dashboard 等重依赖能力。

**Tech Stack:** Python 3.12、FastAPI、MCP FastMCP、SQLite/WAL、LanceDB、pytest、PowerShell、GitHub。

---

## 0. 参考结论：哪些现在抄、哪些后面引入、哪些暂不做

### 0.1 现在直接抄进当前重构主线

| MemOS 成熟经验 | 当前项目落点 | 现在做的原因 | 抄法 |
|---|---|---|---|
| MemCube / Multi-Cube 隔离与组合 | `context_cubes`、`cube_bindings`、`cube_id/cube_ids` | 多 Agent/项目/用户共享记忆必须先有边界 | 已完成 v0.1；后续补 Cube 组合策略和默认 cube resolver |
| MemReader fast/fine 分层 | `app/reader/service.py`、ReaderItem、ingest/session/asset 入口 | 所有输入先标准化，后面才能治理 | fast 已完成；下一步引入 reader candidates/lifecycle |
| MemScheduler 的队列、优先级、状态跟踪、handler 模式 | `improvement_tasks` + `app/scheduler/service.py` | 当前 improvement queue 还不能可靠后台执行 | 先用 SQLite claim/retry/lease 复刻，不引 Redis |
| Feedback & Correction 标准操作 | `memory_feedback`、`memory_feedback_actions`、manual apply | 成熟记忆系统必须能纠错、补证据、归档 | 先手动 actions，不上 LLM 自动规划 |
| API handler 与 component init 拆分 | `app/runtime/*`、`app/handlers/*` | 当前 `api.py/mcp_server.py/repo.py` 已变大，继续堆会失控 | 先抽 RuntimeComponents 和 handler，保持 REST/MCP 兼容 |
| Memory metadata: source、version、history、status | `memory_versions`、`memory_evidence`、lifecycle events | 解决“记忆从哪来、改过什么、能不能信” | 增量扩展，不破坏现有 memories 表 |

### 0.2 后面再引入

| MemOS 能力 | 延后原因 | 触发条件 |
|---|---|---|
| Reader fine mode / hallucination filter / evidence quote LLM 抽取 | 需要稳定 LLM 配置和成本控制 | Scheduler + Feedback 稳定后 |
| Redis Streams / consumer group / distributed scheduler | 当前 NAS 单机优先，SQLite 足够验证语义 | 多 worker 并发或远程负载上来后 |
| Hook/plugin runtime | hook_subscriptions / hook_events / REST-MCP hook tools | external workers need stable event entrypoints |
| Graph memory / subgraph dashboard | 当前 SQLite + LanceDB 已能服务检索 | memory lifecycle 和 feedback 数据足够后 |
| Reranker / agentic search / deep search | 会增加复杂依赖 | 基础 recall 质量瓶颈明确后 |
| User manager / enterprise ACL | 当前是个人/NAS 工具链 | 多真实用户共享并需要权限隔离时 |

### 0.3 暂时不要抄

- Parametric Memory、LoRA、model adaptation。
- Activation Memory / KV cache。
- 云 dashboard、多租户计费、企业权限大平台。
- 把 OCR/ASR/ffmpeg/PDF 深解析塞进主服务；继续用 external worker 产 manifest，GCD 只注册和检索。
- 直接替换成 MemOS 原项目运行时；当前项目要保持 NAS-first、REST/MCP-first。

---

## 1. 当前状态

已完成并推送：

- `b6d7276 feat: add context cubes for scoped memory`
  - `app/cubes/service.py`
  - `context_cubes` / `cube_bindings`
  - memories/assets/sessions/improvement/promotions 支持 `cube_id`
  - search/recall 支持 `cube_id` / `cube_ids`
  - REST/MCP cube 工具
- `5826d8e feat: add reader fast mode pipeline`
  - `ReaderItem`
  - `read_text_fast()` / `read_session_event_fast()` / `read_asset_manifest_fast()` / `read_tool_trace_fast()`
  - memory/document/session/asset/control 入口写 reader metadata

下一步从 Phase 3 开始，按 TDD 做 SQLite Scheduler。

---

## Task 1: SQLite Scheduler schema + repo

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\core\schemas.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\storage\repo.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_scheduler.py`

- [ ] **Step 1: 写失败测试：pending task 可 claim，且字段不丢失**

```python
def test_scheduler_claims_pending_task_with_cube_and_queue(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.storage.bootstrap import bootstrap
    from app.core.schemas import ImprovementTaskCreate
    from app.improvements.service import create_improvement_task
    from app.scheduler.service import claim_next_task

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "sqlite_path", tmp_path / "context.db")
    bootstrap(settings)

    task = create_improvement_task(ImprovementTaskCreate(
        task_kind="reindex_asset",
        target_domain="asset",
        target_id="asset-1",
        cube_id="cube-a",
        priority=10,
        metadata={"queue_name": "asset"},
    ))

    claimed = claim_next_task(queue_name="asset", worker_id="worker-1", lease_seconds=60)

    assert claimed is not None
    assert claimed["id"] == task["id"]
    assert claimed["cube_id"] == "cube-a"
    assert claimed["queue_name"] == "asset"
    assert claimed["worker_id"] == "worker-1"
    assert claimed["status"] == "running"
    assert claimed["claimed_until"]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
python -m pytest tests\test_scheduler.py::test_scheduler_claims_pending_task_with_cube_and_queue -q
```

Expected: FAIL，提示 `app.scheduler` 不存在或字段不存在。

- [ ] **Step 3: 扩展 schema**

在 `ImprovementTaskCreate` 增加：

```python
queue_name: str = "default"
max_retries: int = Field(default=3, ge=0, le=20)
next_run_at: str | None = None
```

在 `ImprovementTaskUpdate` 增加：

```python
retry_count: int | None = Field(default=None, ge=0, le=100)
max_retries: int | None = Field(default=None, ge=0, le=100)
next_run_at: str | None = None
claimed_at: str | None = None
claimed_until: str | None = None
worker_id: str | None = None
queue_name: str | None = None
last_error: str | None = None
```

- [ ] **Step 4: 扩展 `improvement_tasks` 表和自愈列**

在 create table 增加：

```sql
retry_count integer default 0,
max_retries integer default 3,
next_run_at text,
claimed_at text,
claimed_until text,
worker_id text,
queue_name text default 'default',
last_error text
```

在 `_ensure_columns(conn, "improvement_tasks", ...)` 加同名列。

- [ ] **Step 5: 更新 `ImprovementTasksRepo`**

更新 `upsert/get/update/list_recent/_decode` 的字段顺序，确保返回 dict 包含：

```python
"retry_count", "max_retries", "next_run_at", "claimed_at",
"claimed_until", "worker_id", "queue_name", "last_error"
```

保留旧字段 `claimed_by` / `error_message` 作为兼容别名，不删除。

- [ ] **Step 6: 运行当前测试**

```powershell
python -m pytest tests\test_scheduler.py::test_scheduler_claims_pending_task_with_cube_and_queue -q
```

Expected: FAIL 只剩 `claim_next_task` 未实现。

---

## Task 2: Scheduler service 状态机

**Files:**
- Create: `S:\项目开发\全局数据库\global_context_db\app\scheduler\__init__.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\scheduler\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\storage\repo.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_scheduler.py`

- [ ] **Step 1: 写状态机测试**

追加测试：

```python
def test_scheduler_prevents_double_claim(tmp_path, monkeypatch):
    # create one pending task, claim by worker-1, worker-2 gets None
    ...

def test_scheduler_releases_expired_claim(tmp_path, monkeypatch):
    # claim with lease_seconds=-1, release_expired_claims returns 1, then worker-2 can claim
    ...

def test_scheduler_retries_failed_until_max_retries(tmp_path, monkeypatch):
    # fail task twice with max_retries=2; first retry returns pending, second remains failed
    ...
```

不要跳过；用真实 repo + SQLite 临时目录。

- [ ] **Step 2: 在 repo 增加原子 claim 方法**

新增 `ImprovementTasksRepo.claim_next(queue_name, worker_id, now, claimed_until)`：

```sql
select id from improvement_tasks
where status = 'pending'
  and coalesce(queue_name, 'default') = ?
  and (next_run_at is null or next_run_at <= ?)
order by priority asc, created_at asc, rowid asc
limit 1
```

随后同一连接内 update：

```sql
update improvement_tasks
set status='running', worker_id=?, claimed_by=?, claimed_at=?, claimed_until=?, updated_at=?
where id=? and status='pending'
```

- [ ] **Step 3: 实现 `app/scheduler/service.py`**

必须提供：

```python
claim_next_task(queue_name: str = "default", worker_id: str = "local", lease_seconds: int = 300) -> dict | None
complete_task(task_id: str, result: dict | None = None) -> dict
fail_task(task_id: str, error: str, retry_delay_seconds: int = 60) -> dict
release_expired_claims(now: str | None = None) -> int
retry_failed_tasks(now: str | None = None) -> int
run_pending_tasks(limit: int = 10, queue_name: str = "default", worker_id: str = "local") -> dict
```

状态规则：

```text
pending -> running -> done
pending -> running -> failed
running + claimed_until < now -> pending
failed + retry_count < max_retries + next_run_at <= now -> pending
failed + retry_count >= max_retries -> failed
```

- [ ] **Step 4: 运行 scheduler 测试**

```powershell
python -m pytest tests\test_scheduler.py -q
```

Expected: PASS。

---

## Task 3: Scheduler executor + REST/MCP 接入

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\improvements\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\api.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\mcp_server.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_scheduler.py`

- [ ] **Step 1: 让 `run_pending_tasks()` 调用现有 deterministic executor**

把 `_execute_task(task, payload)` 抽成可复用函数：

```python
def execute_improvement_task(task: dict, *, actor: str = "scheduler", clean_legacy: bool = True) -> dict:
    payload = ImproveRequest(
        task_kind=task["task_kind"],
        target_domain=task["target_domain"],
        target_id=task["target_id"],
        cube_id=task.get("cube_id"),
        execute=True,
        clean_legacy=clean_legacy,
        created_by=actor,
        metadata=task.get("metadata", {}),
    )
    return _execute_task(task, payload)
```

- [ ] **Step 2: 写执行测试**

```python
def test_scheduler_run_pending_tasks_executes_known_task(tmp_path, monkeypatch):
    # monkeypatch app.improvements.service.execute_improvement_task to return {"ok": True}
    # assert run_pending_tasks(limit=1)["done"] == 1
```

- [ ] **Step 3: REST endpoints**

新增：

```text
POST /scheduler/claim
POST /scheduler/run-pending
POST /scheduler/release-expired
GET  /scheduler/status
```

返回不要暴露内部异常堆栈，400 用 `HTTPException`。

- [ ] **Step 4: MCP tools**

新增：

```text
gcd_scheduler_claim_next
gcd_scheduler_run_pending
gcd_scheduler_release_expired
gcd_scheduler_status
```

- [ ] **Step 5: 验证**

```powershell
python -m pytest tests\test_scheduler.py -q
python -m pytest -q
python -m compileall app tools
```

Expected: 全部 PASS。

- [ ] **Step 6: 提交推送**

```powershell
git add app\core\schemas.py app\storage\repo.py app\scheduler app\improvements\service.py app\api.py app\mcp_server.py tests\test_scheduler.py
git commit -m "feat: add sqlite scheduler state machine"
git push
```

---

## Task 4: Memory Feedback 基础表 + 手动 apply

**Files:**
- Create: `S:\项目开发\全局数据库\global_context_db\app\memory\feedback_service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\core\schemas.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\storage\repo.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\api.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\mcp_server.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_memory_feedback.py`

- [ ] **Step 1: 写 apply 测试**

覆盖：

```python
def test_feedback_update_memory_action_applies_and_versions(tmp_path, monkeypatch): ...
def test_feedback_archive_memory_action_applies(tmp_path, monkeypatch): ...
def test_feedback_add_evidence_action_applies(tmp_path, monkeypatch): ...
def test_feedback_create_memory_action_applies(tmp_path, monkeypatch): ...
```

- [ ] **Step 2: schema**

新增：

```python
class MemoryFeedbackCreate(BaseModel):
    cube_id: str | None = None
    feedback_text: str
    target_memory_id: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class MemoryFeedbackActionCreate(BaseModel):
    action_type: str
    target_memory_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 3: repo tables**

新增：

```sql
memory_feedback(id, cube_id, feedback_text, target_memory_id, status, created_by, created_at, updated_at, metadata)
memory_feedback_actions(id, feedback_id, action_type, target_memory_id, payload, status, applied_at, metadata)
```

- [ ] **Step 4: service apply**

支持 action：

```text
update         -> update_memory()
archive        -> update_memory(status='archived')
add_evidence   -> add_memory_evidence()
create_memory  -> add_memory()
reject         -> feedback/action 标记 rejected
```

每次 apply 写 audit log，action 幂等：已 `applied` 再 apply 不重复执行。

- [ ] **Step 5: REST/MCP**

```text
POST /memory-feedback
GET  /memory-feedback
POST /memory-feedback/{feedback_id}/actions
POST /memory-feedback/{feedback_id}/apply

gcd_memory_feedback
gcd_list_memory_feedback
gcd_apply_memory_feedback
```

- [ ] **Step 6: 验证提交**

```powershell
python -m pytest tests\test_memory_feedback.py -q
python -m pytest -q
python -m compileall app tools
git add app tests
git commit -m "feat: add manual memory feedback actions"
git push
```

---

## Task 5: RuntimeComponents + Handlers 拆分

**Files:**
- Create: `S:\项目开发\全局数据库\global_context_db\app\runtime\__init__.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\runtime\components.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\handlers\memory_handler.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\handlers\asset_handler.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\handlers\session_handler.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\handlers\cube_handler.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\handlers\scheduler_handler.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_runtime_components.py`

- [ ] **Step 1: 写 component 初始化测试**

```python
def test_runtime_components_bootstrap_is_idempotent(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.runtime.components import get_runtime_components

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "sqlite_path", tmp_path / "context.db")

    first = get_runtime_components(settings)
    second = get_runtime_components(settings)

    assert first.settings is settings
    assert second.settings is settings
    assert first.sqlite_path == settings.sqlite_path
```

- [ ] **Step 2: 实现 RuntimeComponents**

```python
@dataclass(frozen=True)
class RuntimeComponents:
    settings: Settings
    sqlite_path: Path
    data_dir: Path


def get_runtime_components(settings: Settings = settings) -> RuntimeComponents:
    bootstrap(settings)
    return RuntimeComponents(settings=settings, sqlite_path=settings.sqlite_path, data_dir=settings.data_dir)
```

先别把所有 service 塞进 dataclass；保持轻量，避免大爆改。

- [ ] **Step 3: 抽 handler 薄封装**

每个 handler 只做：

```text
validate request -> call service -> normalize error/response
```

不要在 handler 里写 repo SQL 或业务算法。

- [ ] **Step 4: 逐步改 API/MCP 调 handler**

先迁移新增的 scheduler/feedback/cube，再迁移 memory/session/asset。每迁一组跑相关测试。

- [ ] **Step 5: 验证提交**

```powershell
python -m pytest -q
python -m compileall app tools
git add app tests
git commit -m "refactor: introduce runtime components and handlers"
git push
```

---

## Task 6: Lifecycle events + reader candidates

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\reader\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\memory\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\storage\repo.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_memory_lifecycle.py`

- [ ] **Step 1: 新增 lifecycle 表**

```sql
memory_lifecycle_events(
  id text primary key,
  memory_id text,
  from_status text,
  to_status text,
  event_kind text,
  actor text,
  created_at text,
  metadata text default '{}'
)
```

- [ ] **Step 2: ReaderItem -> candidate**

新增 `memory_candidates`：保存 reader 输出但尚未确认的记忆候选。

状态：

```text
candidate -> active -> verified -> stale -> archived/deleted/conflicted
```

- [ ] **Step 3: 迁移 promotion/quality report 使用 lifecycle**

promotion 成功后写 `promoted` 事件；update 写 `corrected`；archive 写 `archived`。

- [ ] **Step 4: 验证提交**

```powershell
python -m pytest tests\test_memory_lifecycle.py -q
python -m pytest -q
python -m compileall app tools
git add app tests
git commit -m "feat: add memory lifecycle events"
git push
```

---

## Task 7: Lifecycle/candidate REST + MCP 调用面

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\handlers\memory_handler.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\api.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\mcp_server.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_memory_surfaces.py`

- [x] **Step 1: TDD 覆盖 REST 调用面**

新增测试：创建 memory 后 `GET /memories/{memory_id}/lifecycle` 能返回 `created`；`POST /memory-candidates` 能从 `ReaderItem` 保存候选；`GET /memory-candidates` 能列出；`POST /memory-candidates/{candidate_id}/promote` 能 promote 成正式 memory。

- [x] **Step 2: TDD 覆盖 MCP 调用面**

新增测试直接调用：

```text
gcd_list_memory_lifecycle_events
gcd_create_memory_candidate
gcd_list_memory_candidates
gcd_promote_memory_candidate
```

- [x] **Step 3: MemoryHandler 薄封装**

`MemoryHandler` 只代理 service：

```text
list_lifecycle_events
create_candidate
list_candidates
promote_candidate
```

- [x] **Step 4: REST/MCP 接入**

新增 REST：

```text
GET  /memories/{memory_id}/lifecycle
POST /memory-candidates
GET  /memory-candidates
POST /memory-candidates/{candidate_id}/promote
```

新增 MCP：

```text
gcd_list_memory_lifecycle_events
gcd_create_memory_candidate
gcd_list_memory_candidates
gcd_promote_memory_candidate
```

- [x] **Step 5: 验证提交**

```powershell
python -m pytest tests\test_memory_surfaces.py -q
python -m pytest -q
python -m compileall app tools
git add app tests docs
git commit -m "feat: expose memory lifecycle surfaces"
git push
```

---

## Task 8: Reader evidence/provenance/span 规范

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\core\schemas.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\reader\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\memory\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\storage\repo.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_reader.py`

- [x] **Step 1: TDD 覆盖 Reader evidence span**

新增测试确认 `read_text_fast()` 和 `read_session_event_fast()` 输出：

```text
ReaderItem.evidence[]
ReaderEvidence.source_domain/source_id/quote/confidence
ReaderEvidenceSpan.start/end/quote_hash
metadata.reader.evidence_count
```

- [x] **Step 2: TDD 覆盖 candidate promotion 保留 evidence**

新增测试确认 `ReaderItem -> memory_candidate -> promote_memory_candidate()` 后，`memory_evidence` 能保留原始 quote 和 `source_span`。

- [x] **Step 3: Schema 规范**

新增：

```text
ReaderEvidenceSpan
ReaderEvidence
ReaderItem.evidence
MemoryEvidenceCreate.source_span
```

- [x] **Step 4: SQLite 兼容扩展**

新增/自愈字段：

```text
memory_evidence.source_span
memory_candidates.evidence
```

- [x] **Step 5: 验证提交**

```powershell
python -m pytest tests\test_reader.py -q
python -m pytest -q
python -m compileall app tools
git add app tests docs
git commit -m "feat: standardize reader evidence spans"
git push
```

---

## Task 9: Reader fine mode 非 LLM 骨架

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\core\schemas.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\reader\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\memory\service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\handlers\memory_handler.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\api.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\mcp_server.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_reader.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_memory_surfaces.py`

- [x] **Step 1: TDD 覆盖 deterministic fine reader**

新增测试确认 `read_text_fine()` 不依赖 LLM，能从源文本中提取：

```text
Decision:
Preference:
Todo:
Fact:
Insight:
Warning:
```

并输出：

```text
content_kind=fine_candidates
metadata.reader.mode=fine
metadata.reader.llm_required=false
metadata.reader.candidate_count
metadata.quality.hallucination_filter=deterministic_source_quote
metadata.fine_candidates[]
ReaderItem.evidence[]
```

- [x] **Step 2: TDD 覆盖 fine reader -> memory_candidates**

新增测试确认 `create_memory_candidates_from_fine_reader()` 会把 fine candidates 写入 `memory_candidates`，保留 evidence quote/span 和 fine metadata。

- [x] **Step 3: REST/MCP 调用面**

新增 REST：

```text
POST /memory-candidates/from-fine-reader
```

新增 MCP：

```text
gcd_create_memory_candidates_from_fine_reader
```

- [x] **Step 4: 实现非 LLM 骨架**

第一版 deliberately 不接 LLM，只接确定性 marker extractor，避免在本地/NAS 服务里直接引入不稳定重依赖。

- [x] **Step 5: 验证提交**

```powershell
python -m pytest tests\test_reader.py tests\test_memory_surfaces.py -q
python -m pytest -q
python -m compileall app tools
git add app tests docs
git commit -m "feat: add deterministic reader fine mode"
git push
```

---

## Task 10: Feedback action proposal 非 LLM 骨架

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\memory\feedback_service.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\handlers\feedback_handler.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\api.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\mcp_server.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_memory_feedback.py`

- [x] **Step 1: TDD 覆盖 proposal 不直接 apply**

新增测试确认 `propose_memory_feedback_actions()` 生成 `status=proposed` action，不修改正式 memory；之后仍可通过 `apply_memory_feedback()` 审核应用。

- [x] **Step 2: TDD 覆盖确定性 planner**

第一版支持：

```text
Update content to: ... -> update
Archive / obsolete / outdated -> archive
Evidence: ... -> add_evidence
无 target_memory_id -> create_memory fallback
```

- [x] **Step 3: REST/MCP 调用面**

新增 REST：

```text
POST /memory-feedback/{feedback_id}/propose-actions
```

新增 MCP：

```text
gcd_propose_memory_feedback_actions
```

- [x] **Step 4: 保持可替换 LLM planner 边界**

当前 `planner=deterministic`，返回 `planner.llm_used=false`；真实 LLM action proposal 后续替换 planner，不改变 apply 路径。

- [x] **Step 5: 验证提交**

```powershell
python -m pytest tests\test_memory_feedback.py -q
python -m pytest -q
python -m compileall app tools
git add app tests docs
git commit -m "feat: add feedback action proposals"
git push
```

---

## 11. 每阶段验收门槛

每个阶段完成前必须跑：

```powershell
python -m pytest -q
python -m compileall app tools
git status --short
```

如果只是文档改动，可至少跑：

```powershell
python -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('docs').rglob('*.md')]"
git diff --check
```

---

## 12. 后续阶段触发条件

- Scheduler SQLite 连续通过本地和 NAS 运行验证后，再做 Redis Streams。
- Feedback 手动 apply 被实际使用后，再加 LLM action proposal。
- Hook/plugin runtime 当前先落地轻量事件队列；后续如确有需要，再做更复杂插件治理。
- 记忆纠错/版本数据积累后，再做 graph/dashboard。

---

## Task 11: Hook/plugin runtime 非重依赖骨架

**Files:**
- Modify: `S:\项目开发\全局数据库\global_context_db\app\core\schemas.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\storage\repo.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\hooks\service.py`
- Create: `S:\项目开发\全局数据库\global_context_db\app\handlers\hook_handler.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\api.py`
- Modify: `S:\项目开发\全局数据库\global_context_db\app\mcp_server.py`
- Test: `S:\项目开发\全局数据库\global_context_db\tests\test_hooks.py`

目标：给第三方 worker / OpenClaw / NAS 扩展提供稳定事件接入点，但不做插件市场，不执行任意外部代码。

- [x] 写失败测试：订阅 `memory.created` 后 emit event，事件进入 `queued` 并带 `subscription_id`。
- [x] 写失败测试：无订阅时 emit event，事件仍记录为 `no_subscriber`。
- [x] 写失败测试：REST/MCP 暴露订阅、发事件、查事件、标记 dispatched。
- [x] 新增 schema：`HookSubscriptionCreate`、`HookEventEmit`、`HookEventDispatch`。
- [x] 新增 SQLite 表：`hook_subscriptions`、`hook_events`。
- [x] 新增 service/handler：只负责记录、排队、查询、标记 dispatched。
- [x] 新增 REST：`POST/GET /hooks/subscriptions`、`POST/GET /hooks/events`、`POST /hooks/events/{event_id}/dispatch`。
- [x] 新增 MCP：`gcd_create_hook_subscription`、`gcd_list_hook_subscriptions`、`gcd_emit_hook_event`、`gcd_list_hook_events`、`gcd_mark_hook_event_dispatched`。

验证：

```powershell
python -m pytest tests\test_hooks.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

提交：

```powershell
git add app tests docs
git commit -m "feat: add hook runtime event queue"
git push
```


---

## Task 12: Hook runtime domain event emission

Goal: make the hook runtime more than a manual queue by wiring it into real domain service lifecycle events. Safety boundary remains unchanged: GCD records queued events only and does not execute external plugin code.

- [x] RED test: `add_memory()`, `update_session(status="ended")`, and `create_asset()` emit queued hook events when subscriptions exist.
- [x] Add `emit_domain_event()` as the service-layer emission boundary.
- [x] Memory service emits: `memory.created`, `memory.updated`, `memory.deleted`, `memory_evidence.created`, `memory_promotion.*`, `memory_candidate.promoted`.
- [x] Session service emits: `session.created`, `session.updated`, `session.ended`, `session_event.<event_type>`, `session_trace.recorded`.
- [x] Asset service emits: `asset.created/updated/status_changed`, `asset_artifact.*`, `asset_analysis.registered`, `asset_scan.completed`.
- [x] Preserve safety: events are only persisted to `hook_events`; external workers poll and handle them outside GCD.

Verification:

```powershell
python -m pytest tests\test_hooks.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: emit hooks from domain services"
git push
```

---

## Task 13: Default cube resolver

Goal: make Context Cubes usable by default instead of requiring callers to pass `cube_id` everywhere.

- [x] RED test: session creation without `cube_id` gets a project cube, session-scoped memory inherits it, project asset inherits it, and agent-only memory gets an agent cube.
- [x] Add `resolve_default_cube()` with precedence: explicit cube -> session cube/project -> project path -> agent -> user.
- [x] Auto-create deterministic project/agent/user cubes with `metadata.auto_resolved=true`.
- [x] Wire resolver into `create_session()`, `add_memory()`, and `create_asset()`.

Verification:

```powershell
python -m pytest tests\test_cubes.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: add default cube resolver"
git push
```

---

## Task 14: Readable cube composition

Goal: make recall/search use a mature multi-cube read scope: private/project cube plus shared/kb/public cubes, without leaking other private project cubes.

- [x] RED test: recall with a project cube returns project memory plus shared/kb memories, but excludes another private project cube.
- [x] Add `compose_readable_cube_ids()`.
- [x] Wire composed readable cube ids into `search_context()` and expose `cube_scope` metadata.
- [x] Preserve write behavior: writes still go to explicit/default private cube.

Verification:

```powershell
python -m pytest tests\test_cubes.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: compose readable cube scopes"
git push
```

---

## Task 15: Cube snapshot export/import

Goal: make Context Cubes portable through a minimal snapshot payload before heavier backup/marketplace features.

- [x] RED test: export one cube with bindings/memories, switch to a fresh SQLite/LanceDB data dir, import payload, and verify cube/memory/binding restored.
- [x] Add `export_cube_snapshot(cube_id)` returning `kind=context_cube_snapshot`, cube, bindings, memories, and counts.
- [x] Add `import_cube_snapshot(snapshot)` restoring cube, memories, and bindings into current runtime.
- [x] Expose REST: `GET /cubes/{cube_id}/snapshot`, `POST /cubes/snapshot/import`.
- [x] Expose MCP: `gcd_export_cube_snapshot`, `gcd_import_cube_snapshot`.

Verification:

```powershell
python -m pytest tests\test_cubes.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: add cube snapshot import export"
git push
```


---

## Task 16: Writable cube fan-out

Goal: borrow MemOS `writable_cube_ids` semantics so writes can target one or more explicit cubes while reads keep using readable cube scope.

- [x] RED test: `MemoryCreate(writable_cube_ids=[project, shared])` creates one memory per writable cube and returns write-scope metadata.
- [x] Add `writable_cube_ids` to `MemoryCreate` while keeping `cube_id` backward-compatible.
- [x] Make `add_memory()` fan out to each writable cube with cube-scoped deterministic IDs.
- [x] Expose `writable_cube_ids` on MCP `gcd_add_memory`; REST already accepts the schema field.

Verification:

```powershell
python -m pytest tests\test_cubes.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: add writable cube fan out"
git push
```


---

## Task 17: Asset writable cube fan-out

Goal: extend MemOS-style `writable_cube_ids` semantics from memories to governed NAS assets while preserving the external-worker manifest boundary.

- [x] RED test: `AssetCreate(writable_cube_ids=[project, shared])` creates separate cube-scoped assets with the same display `asset_key`.
- [x] Add `writable_cube_ids` to `AssetCreate` while keeping `cube_id` backward-compatible.
- [x] Make `create_asset()` fan out to each writable cube using cube-scoped internal identity so locations/versions do not collapse across cubes.
- [x] Expose `writable_cube_ids` on MCP `gcd_add_asset`; REST already accepts the schema field.
- [x] Keep NAS-first boundary: no OCR/ASR/ffmpeg/PDF processing added to the main service.

Verification:

```powershell
python -m pytest tests\test_assets.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: add asset writable cube fan out"
git push
```


---

## Task 18: Remember writable cube routing

Goal: move MemOS-style write scope from low-level services into the high-level `remember` product verb so agent clients can write memory/assets to multiple cubes through one stable entrypoint.

- [x] RED test: `RememberRequest(content_type=memory|asset, writable_cube_ids=[project, shared])` fans out to both cubes.
- [x] Add `writable_cube_ids` to `RememberRequest`.
- [x] Wire `control.remember()` memory path to `MemoryCreate.writable_cube_ids`.
- [x] Wire `control.remember()` asset path to `AssetCreate.writable_cube_ids` without changing the external worker boundary.
- [x] Expose `writable_cube_ids` on MCP `gcd_remember`; REST `/remember` already accepts the schema field.

Verification:

```powershell
python -m pytest tests\test_cubes.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: route remember writable cube ids"
git push
```


---

## Task 19: Readable cube IDs API alias

Goal: align read APIs with MemOS naming by accepting `readable_cube_ids` while keeping legacy `cube_ids` compatibility.

- [x] RED test: `RecallRequest(readable_cube_ids=[...])` and direct `search_context(readable_cube_ids=[...])` restrict results to those cubes.
- [x] RED test: `AssetSearchRequest(readable_cube_ids=[...])` restricts asset results and returns cube-scope metadata.
- [x] Add `readable_cube_ids` to `SearchRequest`, `RecallRequest`, and `AssetSearchRequest`.
- [x] Wire `search_context()` and `control.recall()` to prefer `readable_cube_ids` over legacy `cube_ids`.
- [x] Wire `search_assets()` to prefer `readable_cube_ids` and expose `cube_scope`.
- [x] Expose `readable_cube_ids` on MCP search/recall tools while preserving `cube_ids`.

Verification:

```powershell
python -m pytest tests\test_cubes.py -q
python -m pytest tests\test_assets.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

Commit:

```powershell
git add app tests docs
git commit -m "feat: accept readable cube ids"
git push
```

---

## Task 20: Diagnostics governance follow-up

Goal: close the v0.3 diagnostics gap by exposing pending promotion pressure and write-audit risk signals without adding a dashboard or heavy graph dependency.

- [x] RED test: `/diagnostics` service data reports pending memory promotion count and audit write/high-risk action counts.
- [x] Add `AuditLogsRepo.action_counts()` for grouped audit action summaries.
- [x] Add `governance.improvement.pending_promotion_count` from memory promotion proposal statuses.
- [x] Add `governance.audit.write_action_count`, `high_risk_write_action_count`, `high_risk_actions`, and grouped `write_action_counts`.
- [x] Preserve boundary: diagnostics only reports; it does not auto-apply promotions or execute external workers.

Verification:

```powershell
python -m pytest tests\test_diagnostics.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

---

## Task 21: Resume context format tightening

Goal: make the reserved `format=raw|handoff|brief` parameter operational so agent clients can request either full recovery context or a compact handoff summary without guessing which arrays are populated.

- [x] RED test: `format=raw` returns raw recent events while `format=brief` suppresses heavy arrays and returns compact counts.
- [x] RED test: unknown resume context formats are rejected with a clear `ValueError`.
- [x] Add top-level `format` to resume context responses.
- [x] Keep default `handoff` behavior backward-compatible for existing callers.
- [x] Preserve secret redaction and context budget trimming paths.

Verification:

```powershell
python -m pytest tests\test_v03_sessions_improvements.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

---

## Task 22: Retrieval eval fixture for NAS acceptance

Goal: turn retrieval eval from an ad hoc API into a reusable NAS acceptance fixture with 20+ project-oriented cases covering memory, document, asset, and session domains.

- [x] RED test: project retrieval eval fixture has at least 20 cases and covers memory/document/asset/session domains.
- [x] Add `tools/retrieval_eval_fixture.py` to emit the default project fixture or normalize a JSON fixture file.
- [x] Keep cases as plain `RetrievalEvalCase`-compatible dictionaries so REST/MCP callers can submit them directly to `/retrieval/eval` / `gcd_run_retrieval_eval`.
- [x] Include the fixture tool in NAS package verification required entries.

Verification:

```powershell
python -m pytest tests\test_retrieval_eval_fixture.py -q
python -m pytest -q
python -m compileall app tools
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
git diff --check
git status --short
```

---

## Task 23: Media manifest worker probe adapters

Goal: upgrade `tools/media_manifest_worker.py` from placeholder media probes to optional real probe/text adapters while keeping heavy OCR/ASR/ffmpeg execution outside the GCD service boundary.

- [x] RED test: video analysis manifest can use an injected ffprobe adapter and writes `probe_metadata` JSON artifacts.
- [x] RED test: image analysis manifest can attach OCR adapter text as an `ocr_text` artifact and summary.
- [x] Add `run_ffprobe()` helper and CLI flags `--ffprobe` / `--ffprobe-bin` for external ffprobe usage.
- [x] Add CLI adapter file flags `--ocr-text-file` and `--asr-text-file` for externally produced OCR/ASR text.
- [x] Preserve NAS-first boundary: GCD service still only registers manifests/artifacts; media processing stays in the worker or external tools.

Verification:

```powershell
python -m pytest tests\test_media_manifest_worker.py -q
python -m pytest -q
python -m compileall app tools
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
git diff --check
git status --short
```

---

## Task 24: MCP high-risk write audit actions

Goal: make high-risk MCP write tools more explicit in audit logs so NAS operators can see when an agent used a dangerous control-plane action, without logging secrets or adding interactive confirmation that would break MCP clients.

- [x] RED test: `gcd_delete_memory` emits a distinct `mcp.high_risk_write` audit log before deleting a memory.
- [x] Add `audit_mcp_high_risk_write()` helper that strips secret-like metadata keys and writes `target_type=mcp_tool`.
- [x] Wire explicit high-risk MCP audit into memory update/delete, memory feedback apply, memory promotion review, and asset update.
- [x] Keep existing service-level domain audit logs intact; this is an MCP-call audit layer, not a replacement.

Verification:

```powershell
python -m pytest tests\test_mcp_audit.py -q
python -m pytest -q
python -m compileall app tools
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
git diff --check
git status --short
```

---

## Task 25: Richer memory evidence source spans

Goal: make the existing `source_span` contract explicit and verified for richer provenance such as document chunk offsets, asset artifact ids, and session event quote hashes.

- [x] RED-style coverage: memory evidence can persist selector plus `source_span.metadata.asset_artifact_id`, `session_event_id`, and `document_chunk_id`.
- [x] Confirm existing `ReaderEvidenceSpan.metadata` is sufficient for richer provenance without a schema migration.
- [x] Keep evidence storage generic: source-specific identifiers stay in `source_span.metadata` rather than adding narrow columns per source type.

Verification:

```powershell
python -m pytest tests\test_reader.py -q
python -m pytest -q
python -m compileall app tools
git diff --check
git status --short
```

---

## Task 26: Memory hygiene queue

Goal: turn memory quality diagnostics into a repeatable hygiene queue so expired, conflicting, duplicate, or low-trust memories can be reviewed through scheduler tasks instead of staying as one-off reports.

- [x] RED test: `enqueue_memory_hygiene()` creates memory-quality tasks on `queue_name=memory_hygiene`.
- [x] RED test: scheduler execution of hygiene tasks returns deterministic review proposals rather than mutating formal memories automatically.
- [x] Add `enqueue_memory_hygiene()` service plus REST `/memories/hygiene/enqueue` and MCP `gcd_enqueue_memory_hygiene` entrypoints.
- [x] Add deterministic executor outputs for `verify_memory_evidence`, `refresh_stale_memory`, and `resolve_memory_conflict`.
- [x] Preserve safety: hygiene executor proposes review actions only; it does not auto-edit or archive memories.

Verification:

```powershell
python -m pytest tests\test_memory_hygiene.py -q
python -m pytest -q
python -m compileall app tools
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
git diff --check
git status --short
```

---

## Task 27: Lightweight memory relation index

Goal: explore graph-style memory navigation as a lightweight SQLite relation index, not a separate graph database or dashboard.

- [x] RED test: relation index links memories with shared tags and links memories to evidence sources.
- [x] Add `memory_relations` table and repo with source/target/relation_kind indexes.
- [x] Add `app.memory.graph_service` to build `shared_tag` and `supported_by` edges from existing memory/evidence data.
- [x] Expose REST `/memories/relations/rebuild`, `/memories/relations` and MCP `gcd_build_memory_relation_index`, `gcd_list_memory_relations`.
- [x] Add diagnostics sample count while preserving boundary: this is only a relation index on SQLite, not a graph DB replacement.

Verification:

```powershell
python -m pytest tests\test_memory_graph.py -q
python -m pytest -q
python -m compileall app tools
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
git diff --check
git status --short
```

---

## Task 28: Relation index duplicate-candidate edges

Goal: make the lightweight relation index more useful for hygiene by linking duplicate memory candidates, still without replacing SQLite/LanceDB or doing semantic graph reasoning.

- [x] RED test: relation index creates `duplicate_candidate` edges between memories with identical normalized content.
- [x] Add bidirectional `duplicate_candidate` edges with higher weight than shared-tag edges.
- [x] Keep duplicate linking deterministic and text-normalized only; semantic duplicate detection remains a future review task.

Verification:

```powershell
python -m pytest tests\test_memory_graph.py -q
python -m pytest -q
python -m compileall app tools
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1 -OutputDir ..\release
powershell -ExecutionPolicy Bypass -File scripts\verify-nas-package.ps1 ..\release\global_context_db.zip
git diff --check
git status --short
```
