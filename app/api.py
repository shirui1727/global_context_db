from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.backup.service import export_snapshot, list_snapshots, restore_snapshot
from app.capture.crawl import create_crawl_job, get_crawl_job
from app.capture.service import (
    capture_web,
    create_feed,
    ingest_public_url,
    list_captures,
    list_feeds,
    refresh_feed,
)
from app.core.auth import require_api_key
from app.core.config import settings
from app.core.schemas import (
    AssetArtifactCreate,
    AssetArtifactUpdate,
    AssetAnalysisManifest,
    AssetCreate,
    ContextCubeBindingCreate,
    ContextCubeCreate,
    ContextCubeUpdate,
    AssetScanRunCreate,
    AssetSearchRequest,
    AssetUpdate,
    CrawlJobCreateRequest,
    FineReaderRequest,
    FileReferenceCreate,
    FileReferenceUpdate,
    FeedCreateRequest,
    ForgetRequest,
    HookEventDispatch,
    HookEventEmit,
    HookSubscriptionCreate,
    ImprovementTaskCreate,
    ImprovementTaskUpdate,
    ImproveRequest,
    IngestRequest,
    MemoryCreate,
    MemoryEvidenceCreate,
    MemoryFeedbackActionCreate,
    MemoryFeedbackCreate,
    MemoryPromotionCreate,
    MemoryPromotionReview,
    MemoryPromotionUpdate,
    MemoryUpdate,
    ReaderItem,
    RecallRequest,
    RememberRequest,
    ResumeContextRequest,
    RetrievalEvalRequest,
    SearchRequest,
    SessionCreate,
    SessionEventCreate,
    SessionModelUsageCreate,
    SessionSummaryCreate,
    SessionTraceCreate,
    SessionUpdate,
    SnapshotCreateRequest,
    SnapshotRestoreRequest,
    UrlIngestRequest,
    WebCaptureRequest,
)
from app.assets.service import (
    AssetPermissionError,
    asset_maintenance_preflight,
    create_asset,
    fresh_install_preflight,
    get_asset,
    get_asset_scan_run,
    list_asset_artifacts,
    list_assets,
    rebuild_asset_vectors,
    register_asset_analysis_manifest,
    register_asset_artifact,
    run_asset_scan,
    search_assets,
    update_asset,
    update_asset_artifact,
)
from app.files.service import add_file_reference, list_file_references, update_file_reference
from app.governance.service import diagnostics
from app.handlers.cube_handler import CubeHandler
from app.handlers.feedback_handler import FeedbackHandler
from app.handlers.hook_handler import HookHandler
from app.handlers.memory_handler import MemoryHandler
from app.handlers.scheduler_handler import SchedulerHandler
from app.runtime.components import get_runtime_components
from app.control.service import forget as control_forget
from app.control.service import improve as control_improve
from app.control.service import recall as control_recall
from app.control.service import remember as control_remember
from app.improvements.service import create_improvement_task, list_improvement_tasks, update_improvement_task
from app.ingest.pipeline import ingest_text
from app.memory.service import (
    add_memory,
    add_memory_evidence,
    create_memory_promotion,
    delete_memory,
    list_audit_logs,
    list_memory_evidence,
    list_memory_promotions,
    list_memories,
    list_memory_versions,
    enqueue_memory_quality_improvements,
    memory_quality_report,
    review_memory_promotion,
    search_memory,
    update_memory_promotion,
    update_memory,
)
from app.retrieval.service import run_retrieval_eval, search_context
from app.sessions.service import (
    add_session_event,
    add_session_model_usage,
    add_session_summary,
    add_session_trace,
    create_session,
    get_resume_context,
    get_session,
    list_session_events,
    list_session_traces,
    list_sessions,
    update_session,
)
from app.storage.repo import documents_repo

router = APIRouter()


def _cube_handler() -> CubeHandler:
    return CubeHandler(get_runtime_components(settings))


def _scheduler_handler() -> SchedulerHandler:
    return SchedulerHandler(get_runtime_components(settings))


def _feedback_handler() -> FeedbackHandler:
    return FeedbackHandler(get_runtime_components(settings))


def _hook_handler() -> HookHandler:
    return HookHandler(get_runtime_components(settings))


def _memory_handler() -> MemoryHandler:
    return MemoryHandler(get_runtime_components(settings))


@router.get("/", response_class=HTMLResponse)
def home() -> str:
    mcp_url = f"http://NAS_IP:{settings.mcp_port}{settings.mcp_path}"
    return """
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Global Context DB</title>
      <style>
        :root { color-scheme: light; --bg:#f6f8fb; --panel:#ffffff; --text:#162033; --muted:#5f6b85; --line:#d9e1ef; --ok:#16833a; }
        * { box-sizing:border-box; }
        body { margin:0; font-family:"Segoe UI", "PingFang SC", sans-serif; background:var(--bg); color:var(--text); }
        .wrap { max-width:1100px; margin:0 auto; padding:28px; }
        .hero { display:grid; gap:10px; margin-bottom:20px; }
        h1 { margin:0; font-size:32px; }
        p { margin:0; color:var(--muted); line-height:1.7; }
        .status { display:inline-flex; align-items:center; gap:8px; color:var(--ok); font-weight:700; }
        .dot { width:9px; height:9px; border-radius:999px; background:var(--ok); }
        .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
        .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }
        .panel h2 { margin:0 0 10px; font-size:18px; }
        code { background:#eef3fb; border:1px solid var(--line); border-radius:6px; padding:2px 6px; }
        @media (max-width: 900px) { .grid { grid-template-columns:1fr; } }
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="hero">
          <h1>Global Context DB</h1>
          <p class="status"><span class="dot"></span>服务运行中</p>
          <p>这是 NAS 公共记忆库后端。Codex、OpenClaw 等 AI 工具通过 MCP 或 REST 接入，不直接操作数据库文件。</p>
        </div>
        <div class="grid">
          <div class="panel"><h2>MCP 接入</h2><p><code>__MCP_URL__</code> 给支持远程 MCP 的 AI 工具使用。</p></div>
          <div class="panel"><h2>REST 健康检查</h2><p><code>/health</code> 返回服务名、版本、数据目录和 MCP 配置。</p></div>
          <div class="panel"><h2>治理诊断</h2><p><code>/diagnostics</code> 返回统计、审计、失败记录和重复候选。</p></div>
          <div class="panel"><h2>快照恢复</h2><p><code>/snapshots</code> 支持手动导出和恢复 NAS 数据快照。</p></div>
        </div>
      </div>
    </body>
    </html>
    """.replace("__MCP_URL__", mcp_url)


@router.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": settings.service_name,
        "version": settings.service_version,
        "data_dir": str(settings.data_dir),
        "sqlite_path": str(settings.sqlite_path),
        "mcp": {
            "host": settings.mcp_host,
            "port": settings.mcp_port,
            "path": settings.mcp_path,
        },
    }


@router.get("/diagnostics")
def diagnostics_get() -> dict:
    return diagnostics()


@router.post("/remember", dependencies=[Depends(require_api_key)])
def remember_post(payload: RememberRequest) -> dict:
    try:
        return control_remember(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/recall")
def recall_post(payload: RecallRequest) -> dict:
    try:
        return control_recall(payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/forget", dependencies=[Depends(require_api_key)])
def forget_post(payload: ForgetRequest) -> dict:
    try:
        return control_forget(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/improve", dependencies=[Depends(require_api_key)])
def improve_post(payload: ImproveRequest) -> dict:
    try:
        return control_improve(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/snapshots", dependencies=[Depends(require_api_key)])
def snapshots_create(payload: SnapshotCreateRequest) -> dict:
    return export_snapshot(payload.label)


@router.get("/snapshots")
def snapshots_list(limit: int = 20) -> list[dict]:
    return list_snapshots(limit)


@router.post("/snapshots/restore", dependencies=[Depends(require_api_key)])
def snapshots_restore(payload: SnapshotRestoreRequest) -> dict:
    try:
        return restore_snapshot(payload.snapshot_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/documents/ingest")
def documents_ingest(payload: IngestRequest) -> dict:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    return ingest_text(payload)


@router.post("/documents/upload")
async def documents_upload(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    text = raw.decode("utf-8")
    return ingest_text(IngestRequest(source=file.filename or "upload", text=text))


@router.post("/documents/ingest-url")
async def documents_ingest_url(payload: UrlIngestRequest) -> dict:
    try:
        return await ingest_public_url(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"URL 导入失败：{error}") from error


@router.get("/documents")
def documents() -> list[dict]:
    rows = documents_repo().list_all()
    return [
        {
            "id": row["id"],
            "source": row["source"],
            "content_preview": row["content"][:200],
        }
        for row in rows
    ]


@router.post("/documents/search")
def documents_search(payload: SearchRequest) -> dict:
    return search_context(
        payload.query,
        payload.top_k,
        kind="chunk",
        mode="document_search",
        legacy_flat=True,
        context_budget_chars=payload.context_budget_chars,
    )


@router.post("/file-references", dependencies=[Depends(require_api_key)])
def file_references_create(payload: FileReferenceCreate) -> dict:
    try:
        return add_file_reference(payload)
    except AssetPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/file-references")
def file_references_list(
    limit: int = 100,
    status: str | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> list[dict]:
    return list_file_references(
        limit,
        status=status,
        media_type=media_type,
        asset_kind=asset_kind,
        trust_level=trust_level,
    )


@router.patch("/file-references/{file_reference_id}", dependencies=[Depends(require_api_key)])
def file_references_update(file_reference_id: str, payload: FileReferenceUpdate) -> dict:
    try:
        return update_file_reference(file_reference_id, payload)
    except AssetPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/assets", dependencies=[Depends(require_api_key)])
def assets_create(payload: AssetCreate) -> dict:
    try:
        return create_asset(payload)
    except AssetPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/assets")
def assets_list(
    limit: int = 100,
    status: str | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> list[dict]:
    return list_assets(limit, status=status, asset_kind=asset_kind, trust_level=trust_level)


@router.post("/assets/search")
def assets_search(payload: AssetSearchRequest) -> dict:
    return search_assets(payload)


@router.post("/assets/maintenance/rebuild-vectors", dependencies=[Depends(require_api_key)])
def assets_maintenance_rebuild_vectors(clean_legacy: bool = True) -> dict:
    return rebuild_asset_vectors(clean_legacy=clean_legacy)


@router.get("/assets/maintenance/preflight")
def assets_maintenance_preflight() -> dict:
    return asset_maintenance_preflight()


@router.get("/assets/maintenance/fresh-install-preflight")
def assets_maintenance_fresh_install_preflight() -> dict:
    return fresh_install_preflight()


@router.post("/sessions", dependencies=[Depends(require_api_key)])
def sessions_create(payload: SessionCreate) -> dict:
    try:
        return create_session(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sessions")
def sessions_list(
    limit: int = 100,
    status: str | None = None,
    source_agent: str | None = None,
    project_path: str | None = None,
) -> list[dict]:
    return list_sessions(limit=limit, status=status, source_agent=source_agent, project_path=project_path)


@router.get("/sessions/{session_id}")
def sessions_get(session_id: str) -> dict:
    try:
        return get_session(session_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/sessions/{session_id}", dependencies=[Depends(require_api_key)])
def sessions_update(session_id: str, payload: SessionUpdate) -> dict:
    try:
        return update_session(session_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sessions/{session_id}/events", dependencies=[Depends(require_api_key)])
def sessions_events_create(session_id: str, payload: SessionEventCreate) -> dict:
    try:
        return add_session_event(session_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sessions/{session_id}/events")
def sessions_events_list(session_id: str, limit: int = 100) -> list[dict]:
    try:
        return list_session_events(session_id, limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sessions/{session_id}/traces", dependencies=[Depends(require_api_key)])
def sessions_traces_create(session_id: str, payload: SessionTraceCreate) -> dict:
    try:
        return add_session_trace(session_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sessions/{session_id}/traces")
def sessions_traces_list(session_id: str, limit: int = 100) -> list[dict]:
    try:
        return list_session_traces(session_id, limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sessions/{session_id}/summaries", dependencies=[Depends(require_api_key)])
def sessions_summaries_create(session_id: str, payload: SessionSummaryCreate) -> dict:
    try:
        return add_session_summary(session_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sessions/{session_id}/model-usage", dependencies=[Depends(require_api_key)])
def sessions_model_usage_create(session_id: str, payload: SessionModelUsageCreate) -> dict:
    try:
        return add_session_model_usage(session_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sessions/{session_id}/resume-context")
def sessions_resume_context_get(
    session_id: str,
    query: str | None = None,
    top_k: int = 5,
    include_raw_events: bool = True,
    context_budget_chars: int = 12000,
) -> dict:
    try:
        return get_resume_context(
            ResumeContextRequest(
                session_id=session_id,
                query=query,
                top_k=top_k,
                include_raw_events=include_raw_events,
                context_budget_chars=context_budget_chars,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/context/resume")
def context_resume(payload: ResumeContextRequest) -> dict:
    try:
        return get_resume_context(payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/agent-hooks/session-start", dependencies=[Depends(require_api_key)])
def agent_hook_session_start(payload: SessionCreate) -> dict:
    return sessions_create(payload)


@router.post("/agent-hooks/user-prompt", dependencies=[Depends(require_api_key)])
def agent_hook_user_prompt(session_id: str, payload: SessionEventCreate) -> dict:
    payload.event_type = "user_prompt"
    return sessions_events_create(session_id, payload)


@router.post("/agent-hooks/tool-use", dependencies=[Depends(require_api_key)])
def agent_hook_tool_use(session_id: str, payload: SessionTraceCreate) -> dict:
    return sessions_traces_create(session_id, payload)


@router.post("/agent-hooks/pre-compact", dependencies=[Depends(require_api_key)])
def agent_hook_pre_compact(session_id: str, payload: SessionEventCreate) -> dict:
    payload.event_type = "pre_compact"
    return sessions_events_create(session_id, payload)


@router.post("/agent-hooks/session-end", dependencies=[Depends(require_api_key)])
def agent_hook_session_end(session_id: str, payload: SessionUpdate | None = None) -> dict:
    return sessions_update(session_id, payload or SessionUpdate(status="ended"))


@router.post("/improvements", dependencies=[Depends(require_api_key)])
def improvements_create(payload: ImprovementTaskCreate) -> dict:
    try:
        return create_improvement_task(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/improvements")
def improvements_list(
    limit: int = 100,
    status: str | None = None,
    task_kind: str | None = None,
    target_domain: str | None = None,
    target_id: str | None = None,
) -> list[dict]:
    return list_improvement_tasks(
        limit=limit,
        status=status,
        task_kind=task_kind,
        target_domain=target_domain,
        target_id=target_id,
    )


@router.patch("/improvements/{task_id}", dependencies=[Depends(require_api_key)])
def improvements_update(task_id: str, payload: ImprovementTaskUpdate) -> dict:
    try:
        return update_improvement_task(task_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/scheduler/claim", dependencies=[Depends(require_api_key)])
def scheduler_claim(queue_name: str = "default", worker_id: str = "local", lease_seconds: int = 300) -> dict | None:
    try:
        return _scheduler_handler().claim_next(queue_name=queue_name, worker_id=worker_id, lease_seconds=lease_seconds)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/scheduler/run-pending", dependencies=[Depends(require_api_key)])
def scheduler_run_pending(limit: int = 10, queue_name: str = "default", worker_id: str = "local") -> dict:
    try:
        return _scheduler_handler().run_pending(limit=limit, queue_name=queue_name, worker_id=worker_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/scheduler/release-expired", dependencies=[Depends(require_api_key)])
def scheduler_release_expired() -> dict:
    return _scheduler_handler().release_expired()


@router.get("/scheduler/status")
def scheduler_status_get() -> dict:
    return _scheduler_handler().status()


@router.post("/hooks/subscriptions", dependencies=[Depends(require_api_key)])
def hooks_subscriptions_create(payload: HookSubscriptionCreate) -> dict:
    try:
        return _hook_handler().create_subscription(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/hooks/subscriptions")
def hooks_subscriptions_list(
    hook_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return _hook_handler().list_subscriptions(hook_name=hook_name, status=status, limit=limit)


@router.post("/hooks/events", dependencies=[Depends(require_api_key)])
def hooks_events_emit(payload: HookEventEmit) -> dict:
    try:
        return _hook_handler().emit_event(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/hooks/events")
def hooks_events_list(
    hook_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return _hook_handler().list_events(hook_name=hook_name, status=status, limit=limit)


@router.post("/hooks/events/{event_id}/dispatch", dependencies=[Depends(require_api_key)])
def hooks_events_dispatch(event_id: str, payload: HookEventDispatch | None = None) -> dict:
    try:
        return _hook_handler().mark_dispatched(event_id, metadata=(payload.metadata if payload else None))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/assets/scan-runs", dependencies=[Depends(require_api_key)])
def assets_scan_runs_create(payload: AssetScanRunCreate) -> dict:
    try:
        return run_asset_scan(payload)
    except AssetPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/assets/scan-runs/{scan_run_id}")
def assets_scan_runs_get(scan_run_id: str) -> dict:
    try:
        return get_asset_scan_run(scan_run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/assets/{asset_id}")
def assets_get(asset_id: str) -> dict:
    try:
        return get_asset(asset_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/assets/{asset_id}", dependencies=[Depends(require_api_key)])
def assets_update(asset_id: str, payload: AssetUpdate) -> dict:
    try:
        return update_asset(asset_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/assets/{asset_id}/versions")
def assets_versions(asset_id: str) -> list[dict]:
    try:
        return get_asset(asset_id)["versions"]
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/assets/{asset_id}/locations")
def assets_locations(asset_id: str) -> list[dict]:
    try:
        return get_asset(asset_id)["locations"]
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/assets/{asset_id}/artifacts", dependencies=[Depends(require_api_key)])
def assets_artifacts_create(asset_id: str, payload: AssetArtifactCreate) -> dict:
    try:
        return register_asset_artifact(asset_id, payload)
    except AssetPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/assets/{asset_id}/analysis-manifest", dependencies=[Depends(require_api_key)])
def assets_analysis_manifest(asset_id: str, payload: AssetAnalysisManifest) -> dict:
    try:
        return register_asset_analysis_manifest(asset_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/assets/{asset_id}/artifacts")
def assets_artifacts_list(asset_id: str) -> list[dict]:
    try:
        return list_asset_artifacts(asset_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/asset-artifacts/{artifact_id}", dependencies=[Depends(require_api_key)])
def assets_artifacts_update(artifact_id: str, payload: AssetArtifactUpdate) -> dict:
    try:
        return update_asset_artifact(artifact_id, payload)
    except AssetPermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/captures/web", dependencies=[Depends(require_api_key)])
def captures_web(payload: WebCaptureRequest) -> dict:
    try:
        return capture_web(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/captures")
def captures(limit: int = 50) -> list[dict]:
    return list_captures(limit)


@router.post("/feeds", dependencies=[Depends(require_api_key)])
def feeds_create(payload: FeedCreateRequest) -> dict:
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="url is required")
    try:
        return create_feed(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/feeds")
def feeds_list() -> list[dict]:
    return list_feeds()


@router.post("/feeds/{feed_id}/refresh", dependencies=[Depends(require_api_key)])
async def feeds_refresh(feed_id: str) -> dict:
    try:
        return await refresh_feed(feed_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"RSS 刷新失败：{error}") from error


@router.post("/crawl/jobs", dependencies=[Depends(require_api_key)])
async def crawl_jobs_create(payload: CrawlJobCreateRequest) -> dict:
    try:
        return await create_crawl_job(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/crawl/jobs/{job_id}")
def crawl_jobs_get(job_id: str) -> dict:
    job = get_crawl_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/search")
def search(payload: SearchRequest) -> dict:
    return search_context(
        payload.query,
        payload.top_k,
        cube_id=payload.cube_id,
        cube_ids=payload.cube_ids,
        context_domain=payload.context_domain,
        kind=payload.kind,
        mode=payload.mode,
        legacy_flat=payload.legacy_flat,
        context_budget_chars=payload.context_budget_chars,
    )


@router.post("/cubes", dependencies=[Depends(require_api_key)])
def cubes_create(payload: ContextCubeCreate) -> dict:
    try:
        return _cube_handler().create_cube(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/cubes")
def cubes_list(
    limit: int = 100,
    cube_type: str | None = None,
    owner_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    return _cube_handler().list_cubes(limit=limit, cube_type=cube_type, owner_id=owner_id, status=status)


@router.get("/cubes/{cube_id}")
def cubes_get(cube_id: str) -> dict:
    try:
        return _cube_handler().get_cube(cube_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/cubes/{cube_id}", dependencies=[Depends(require_api_key)])
def cubes_update(cube_id: str, payload: ContextCubeUpdate) -> dict:
    try:
        return _cube_handler().update_cube(cube_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/cubes/{cube_id}/bindings", dependencies=[Depends(require_api_key)])
def cubes_bindings_create(cube_id: str, payload: ContextCubeBindingCreate) -> dict:
    try:
        return _cube_handler().bind_to_cube(cube_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/cubes/{cube_id}/bindings")
def cubes_bindings_list(cube_id: str, limit: int = 100) -> list[dict]:
    try:
        return _cube_handler().list_bindings(cube_id, limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/retrieval/eval")
def retrieval_eval(payload: RetrievalEvalRequest) -> dict:
    return run_retrieval_eval([case.model_dump() for case in payload.cases], top_k=payload.top_k)


@router.post("/memories", dependencies=[Depends(require_api_key)])
def memories(payload: MemoryCreate) -> dict:
    return add_memory(payload)


@router.post("/memory-feedback", dependencies=[Depends(require_api_key)])
def memory_feedback_create(payload: MemoryFeedbackCreate) -> dict:
    return _feedback_handler().create_feedback(payload)


@router.get("/memory-feedback")
def memory_feedback_list(
    limit: int = 100,
    status: str | None = None,
    target_memory_id: str | None = None,
) -> list[dict]:
    return _feedback_handler().list_feedback(limit=limit, status=status, target_memory_id=target_memory_id)


@router.post("/memory-feedback/{feedback_id}/actions", dependencies=[Depends(require_api_key)])
def memory_feedback_actions_create(feedback_id: str, payload: MemoryFeedbackActionCreate) -> dict:
    try:
        return _feedback_handler().add_action(feedback_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/memory-feedback/{feedback_id}/actions")
def memory_feedback_actions_list(feedback_id: str, limit: int = 100) -> list[dict]:
    try:
        return _feedback_handler().list_actions(feedback_id, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/memory-feedback/{feedback_id}/propose-actions", dependencies=[Depends(require_api_key)])
def memory_feedback_actions_propose(feedback_id: str, planner: str = "deterministic") -> dict:
    try:
        return _feedback_handler().propose_actions(feedback_id, planner=planner)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/memory-feedback/{feedback_id}/apply", dependencies=[Depends(require_api_key)])
def memory_feedback_apply(feedback_id: str, actor: str = "memory_feedback") -> dict:
    try:
        return _feedback_handler().apply(feedback_id, actor=actor)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/memory-promotions", dependencies=[Depends(require_api_key)])
def memory_promotions_create(payload: MemoryPromotionCreate) -> dict:
    return create_memory_promotion(payload)


@router.get("/memory-promotions")
def memory_promotions_list(
    limit: int = 100,
    status: str | None = None,
    source_session_id: str | None = None,
) -> list[dict]:
    return list_memory_promotions(limit=limit, status=status, source_session_id=source_session_id)


@router.patch("/memory-promotions/{proposal_id}", dependencies=[Depends(require_api_key)])
def memory_promotions_update(proposal_id: str, payload: MemoryPromotionUpdate) -> dict:
    try:
        return update_memory_promotion(proposal_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/memory-promotions/{proposal_id}/review", dependencies=[Depends(require_api_key)])
def memory_promotions_review(proposal_id: str, payload: MemoryPromotionReview) -> dict:
    try:
        return review_memory_promotion(proposal_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/memories")
def memories_list(
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return list_memories(user_id=user_id, agent_id=agent_id, memory_type=memory_type, limit=limit)


@router.get("/memories/search")
def memories_search(
    q: str,
    top_k: int = 5,
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
) -> dict:
    return search_memory(q, top_k, user_id=user_id, agent_id=agent_id, memory_type=memory_type)


@router.get("/memories/quality")
def memories_quality(limit: int = 100) -> dict:
    return memory_quality_report(limit)


@router.post("/memories/quality/enqueue-improvements", dependencies=[Depends(require_api_key)])
def memories_quality_enqueue(limit: int = 100, created_by: str | None = None) -> dict:
    return enqueue_memory_quality_improvements(limit=limit, created_by=created_by)


@router.post("/memory-candidates", dependencies=[Depends(require_api_key)])
def memory_candidates_create(payload: ReaderItem, created_by: str | None = None) -> dict:
    return _memory_handler().create_candidate(payload, created_by=created_by)


@router.post("/memory-candidates/from-fine-reader", dependencies=[Depends(require_api_key)])
def memory_candidates_from_fine_reader(payload: FineReaderRequest) -> dict:
    return _memory_handler().create_candidates_from_fine_reader(payload)


@router.get("/memory-candidates")
def memory_candidates_list(
    limit: int = 100,
    status: str | None = None,
    source_domain: str | None = None,
) -> list[dict]:
    return _memory_handler().list_candidates(limit=limit, status=status, source_domain=source_domain)


@router.post("/memory-candidates/{candidate_id}/promote", dependencies=[Depends(require_api_key)])
def memory_candidates_promote(
    candidate_id: str,
    reviewed_by: str | None = None,
    trust_level: str = "verified",
    status_on_memory: str = "active",
) -> dict:
    try:
        return _memory_handler().promote_candidate(
            candidate_id,
            reviewed_by=reviewed_by,
            trust_level=trust_level,
            status_on_memory=status_on_memory,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/memories/{memory_id}", dependencies=[Depends(require_api_key)])
def memories_update(memory_id: str, payload: MemoryUpdate) -> dict:
    try:
        return update_memory(memory_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/memories/{memory_id}", dependencies=[Depends(require_api_key)])
def memories_delete(memory_id: str) -> dict:
    return delete_memory(memory_id)


@router.get("/memories/{memory_id}/versions")
def memories_versions(memory_id: str, limit: int = 20) -> list[dict]:
    return list_memory_versions(memory_id, limit)


@router.get("/memories/{memory_id}/lifecycle")
def memories_lifecycle(memory_id: str, limit: int = 50) -> list[dict]:
    return _memory_handler().list_lifecycle_events(memory_id, limit)


@router.post("/memories/{memory_id}/evidence", dependencies=[Depends(require_api_key)])
def memories_evidence_create(memory_id: str, payload: MemoryEvidenceCreate) -> dict:
    try:
        return add_memory_evidence(memory_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/memories/{memory_id}/evidence")
def memories_evidence_list(memory_id: str, limit: int = 50) -> list[dict]:
    try:
        return list_memory_evidence(memory_id, limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/audit-logs")
def audit_logs(limit: int = 100) -> list[dict]:
    return list_audit_logs(limit)
