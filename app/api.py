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
from app.ingest.pipeline import ingest_text
from app.memory.service import add_memory, delete_memory, list_memories, search_memory, update_memory
from app.retrieval.service import search_context
from app.storage.repo import documents_repo

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Global Context DB</title>
      <style>
        :root { color-scheme: light; --bg:#f6f8fb; --panel:#ffffff; --text:#162033; --muted:#5f6b85; --accent:#0b6bcb; --line:#d9e1ef; }
        * { box-sizing:border-box; }
        body { margin:0; font-family: "Segoe UI", "PingFang SC", sans-serif; background:linear-gradient(135deg,#eef4ff,#f9fbff 45%,#f3f7f1); color:var(--text); }
        .wrap { max-width:1100px; margin:0 auto; padding:24px; }
        .hero { display:grid; gap:16px; margin-bottom:20px; }
        .hero h1 { margin:0; font-size:32px; }
        .hero p { margin:0; color:var(--muted); }
        .grid { display:grid; grid-template-columns:1.2fr 1fr; gap:16px; }
        .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; box-shadow:0 10px 30px rgba(32,52,89,0.06); }
        .panel h2 { margin:0 0 12px; font-size:18px; }
        textarea, input { width:100%; border:1px solid var(--line); border-radius:8px; padding:10px 12px; font:inherit; }
        textarea { min-height:160px; resize:vertical; }
        .row { display:grid; gap:10px; margin-bottom:12px; }
        .actions { display:flex; gap:10px; flex-wrap:wrap; }
        button { border:0; background:var(--accent); color:#fff; padding:10px 14px; border-radius:8px; font:inherit; cursor:pointer; }
        button.secondary { background:#e9f1fb; color:#16456d; }
        pre { white-space:pre-wrap; word-break:break-word; background:#0f172a; color:#e5eefc; padding:12px; border-radius:8px; min-height:140px; }
        .list { display:grid; gap:10px; max-height:420px; overflow:auto; }
        .item { border:1px solid var(--line); border-radius:8px; padding:10px; background:#fbfdff; }
        .item small { color:var(--muted); display:block; margin-bottom:6px; }
        @media (max-width: 900px) { .grid { grid-template-columns:1fr; } }
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="hero">
          <h1>Global Context DB</h1>
          <p>导入资料，写入记忆，搜索上下文。第一版已经可用。</p>
        </div>
        <div class="grid">
          <div class="panel">
            <h2>Search</h2>
            <div class="row">
              <input id="query" placeholder="输入要搜索的问题或关键词" />
            </div>
            <div class="actions">
              <button onclick="runSearch()">搜索</button>
            </div>
            <pre id="searchResult"></pre>
          </div>
          <div class="panel">
            <h2>Upload Document</h2>
            <div class="row">
              <input id="file" type="file" />
            </div>
            <div class="actions">
              <button onclick="uploadFile()">上传文件</button>
            </div>
            <pre id="uploadResult"></pre>
          </div>
          <div class="panel">
            <h2>Add Memory</h2>
            <div class="row">
              <textarea id="memory" placeholder="输入一条需要长期记住的信息"></textarea>
              <input id="tags" placeholder="标签，逗号分隔" />
            </div>
            <div class="actions">
              <button onclick="addMemory()">写入记忆</button>
            </div>
            <pre id="memoryResult"></pre>
          </div>
          <div class="panel">
            <h2>Data Overview</h2>
            <div class="actions">
              <button class="secondary" onclick="loadDocuments()">刷新文档</button>
              <button class="secondary" onclick="loadMemories()">刷新记忆</button>
            </div>
            <div class="list" id="overview"></div>
          </div>
        </div>
      </div>
      <script>
        async function runSearch() {
          const query = document.getElementById('query').value.trim();
          const res = await fetch('/search', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ query, top_k: 5 }) });
          document.getElementById('searchResult').textContent = JSON.stringify(await res.json(), null, 2);
        }
        async function uploadFile() {
          const file = document.getElementById('file').files[0];
          const fd = new FormData();
          fd.append('file', file);
          const res = await fetch('/documents/upload', { method:'POST', body:fd });
          document.getElementById('uploadResult').textContent = JSON.stringify(await res.json(), null, 2);
          loadDocuments();
        }
        async function addMemory() {
          const content = document.getElementById('memory').value.trim();
          const tags = document.getElementById('tags').value.split(',').map(s => s.trim()).filter(Boolean);
          const res = await fetch('/memories', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ content, tags }) });
          document.getElementById('memoryResult').textContent = JSON.stringify(await res.json(), null, 2);
          loadMemories();
        }
        async function loadDocuments() {
          const res = await fetch('/documents');
          const docs = await res.json();
          render('文档', docs);
        }
        async function loadMemories() {
          const res = await fetch('/memories');
          const mems = await res.json();
          render('记忆', mems);
        }
        function render(title, rows) {
          const host = document.getElementById('overview');
          const items = rows.map(row => `<div class="item"><small>${title}</small><div>${(row.source || row.id || '').replace(/</g, '&lt;')}</div><div>${(row.content_preview || row.content || '').replace(/</g, '&lt;')}</div></div>`).join('');
          if (title === '文档') {
            host.innerHTML = items + host.innerHTML;
          } else {
            host.innerHTML += items;
          }
        }
        loadDocuments();
        loadMemories();
      </script>
    </body>
    </html>
    """


@router.get("/health")
def health() -> dict:
    return {"ok": True}


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
