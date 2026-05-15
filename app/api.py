from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.capture.crawl import create_crawl_job, get_crawl_job
from app.capture.service import (
    capture_web,
    create_feed,
    ingest_public_url,
    list_captures,
    list_feeds,
    refresh_feed,
)
from app.core.schemas import (
    CrawlJobCreateRequest,
    FeedCreateRequest,
    IngestRequest,
    MemoryCreate,
    MemoryUpdate,
    SearchRequest,
    UrlIngestRequest,
    WebCaptureRequest,
)
from app.core.auth import require_api_key
from app.core.config import settings
from app.ingest.pipeline import ingest_text
from app.memory.service import (
    add_memory,
    delete_memory,
    list_audit_logs,
    list_memories,
    list_memory_versions,
    search_memory,
    update_memory,
)
from app.retrieval.service import search_context
from app.storage.repo import documents_repo

router = APIRouter()


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
          <div class="panel"><h2>REST 健康检查</h2><p><code>/health</code> 返回服务名、数据目录和 MCP 配置。</p></div>
          <div class="panel"><h2>长期记忆</h2><p>支持写入、搜索、去重、版本历史和审计日志。</p></div>
          <div class="panel"><h2>桌面管理</h2><p>桌面端负责导入、检索、治理和连接 NAS 服务。</p></div>
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
        raise HTTPException(status_code=404, detail="任务不存在。")
    return job


@router.post("/search")
def search(payload: SearchRequest) -> dict:
    return search_context(payload.query, payload.top_k)


@router.post("/memories", dependencies=[Depends(require_api_key)])
def memories(payload: MemoryCreate) -> dict:
    return add_memory(payload)


@router.get("/memories")
def memories_list(user_id: str | None = None, agent_id: str | None = None, memory_type: str | None = None, limit: int = 100) -> list[dict]:
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


@router.get("/audit-logs")
def audit_logs(limit: int = 100) -> list[dict]:
    return list_audit_logs(limit)
