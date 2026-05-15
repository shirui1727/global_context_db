import base64
import binascii
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.schemas import FeedCreateRequest, IngestRequest, UrlIngestRequest, WebCaptureRequest
from app.ingest.pipeline import ingest_text
from app.storage.repo import captures_repo, feed_items_repo, feeds_repo
from app.web.fetch import fetch_public_page, normalize_url, source_platform_from_url, strip_html_tags

MAX_HTML_CHARS = 2_000_000
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024
MIN_CAPTURE_TEXT_CHARS = 5
RSS_REFRESH_LIMIT = 8


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def safe_id(*parts: str) -> str:
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def artifacts_dir() -> Path:
    path = settings.data_dir / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_html(capture_id: str, html: str | None) -> str | None:
    if not html:
        return None
    path = artifacts_dir() / f"{capture_id}.html"
    path.write_text(html[:MAX_HTML_CHARS], encoding="utf-8")
    return str(path)


def _decode_screenshot(value: str) -> bytes:
    data = value.strip()
    if "," in data and data.lower().startswith("data:image/"):
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data, validate=True)
    if len(raw) > MAX_SCREENSHOT_BYTES:
        raise ValueError("截图太大，第一版最多保存 8 MB。")
    return raw


def _write_screenshot(capture_id: str, screenshot: str | None) -> str | None:
    if not screenshot:
        return None
    try:
        raw = _decode_screenshot(screenshot)
    except (binascii.Error, ValueError) as error:
        raise ValueError(f"截图格式无效：{error}") from error
    path = artifacts_dir() / f"{capture_id}.png"
    path.write_bytes(raw)
    return str(path)


def _record_capture(payload: WebCaptureRequest, result: dict | None, error: str | None = None) -> dict:
    created_at = utc_now()
    capture_id = safe_id(payload.url, payload.title or "", payload.text[:200], created_at)
    html_path = _write_html(capture_id, payload.html)
    screenshot_path = _write_screenshot(capture_id, payload.screenshot)
    text_preview = (payload.text or "").strip()[:300]
    row = {
        "id": capture_id,
        "document_id": result.get("document_id") if result else None,
        "url": payload.url,
        "title": payload.title or payload.url,
        "text_preview": text_preview,
        "html_path": html_path,
        "screenshot_path": screenshot_path,
        "source_platform": payload.source_platform or source_platform_from_url(payload.url),
        "capture_method": payload.capture_method,
        "tags": ",".join(payload.tags),
        "captured_at": payload.captured_at or created_at,
        "created_at": created_at,
        "status": "failed" if error else "imported",
        "error": error,
    }
    captures_repo().upsert(row)
    return row


def capture_web(payload: WebCaptureRequest) -> dict:
    text = payload.text.strip()
    if not text and payload.html:
        text = strip_html_tags(payload.html)
    if len(text) < MIN_CAPTURE_TEXT_CHARS:
        row = _record_capture(payload, None, "正文太少，无法入库。")
        return {"capture_id": row["id"], "status": "failed", "error": row["error"]}

    normalized_payload = payload.model_copy(update={"text": text})
    source = normalized_payload.title or normalized_payload.url
    if normalized_payload.url:
        source = f"{source} <{normalized_payload.url}>"
    result = ingest_text(IngestRequest(source=source, text=text))
    row = _record_capture(normalized_payload, result)
    return {"capture_id": row["id"], **result, "status": row["status"]}


def list_captures(limit: int = 50) -> list[dict]:
    return captures_repo().list_recent(limit)


async def ingest_public_url(payload: UrlIngestRequest) -> dict:
    page = await fetch_public_page(payload.url)
    result = ingest_text(
        IngestRequest(
            source=f"{page['title']} <{page['url']}>",
            text=page["text"],
        )
    )
    capture_payload = WebCaptureRequest(
        url=page["url"],
        title=page["title"],
        text=page["text"],
        html=page["html"],
        tags=payload.tags,
        source_platform=payload.source_platform or page["source_platform"],
        capture_method="url",
    )
    row = _record_capture(capture_payload, result)
    return {
        "capture_id": row["id"],
        "document_id": result["document_id"],
        "chunks": result["chunks"],
        "title": page["title"],
        "url": page["url"],
    }


def create_feed(payload: FeedCreateRequest) -> dict:
    now = utc_now()
    url = normalize_url(payload.url)
    feed_id = safe_id(url)
    feeds_repo().upsert(
        {
            "id": feed_id,
            "url": url,
            "title": payload.title or url,
            "created_at": now,
            "last_refreshed_at": None,
        }
    )
    feed = feeds_repo().get(feed_id)
    return feed or {"id": feed_id, "url": payload.url, "title": payload.title}


def list_feeds() -> list[dict]:
    feeds = feeds_repo().list_all()
    items_repo = feed_items_repo()
    return [{**feed, "items": items_repo.list_by_feed(feed["id"])} for feed in feeds]


async def refresh_feed(feed_id: str) -> dict:
    feed = feeds_repo().get(feed_id)
    if not feed:
        raise ValueError("RSS 源不存在。")

    headers = {"User-Agent": "GlobalContextDB/0.1 local desktop capture"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=12, headers=headers) as client:
        response = await client.get(feed["url"])
        response.raise_for_status()
    parsed = feedparser.parse(response.text)
    feed_title = parsed.feed.get("title") if hasattr(parsed, "feed") else None
    if feed_title and feed_title != feed.get("title"):
        feeds_repo().upsert({**feed, "title": feed_title, "last_refreshed_at": feed.get("last_refreshed_at")})

    imported = 0
    skipped = 0
    failed = 0
    rows: list[dict[str, Any]] = []
    items_repo = feed_items_repo()

    for entry in parsed.entries[:RSS_REFRESH_LIMIT]:
        url = entry.get("link") or entry.get("id")
        if not url:
            skipped += 1
            continue
        if items_repo.exists(feed_id, url):
            skipped += 1
            continue

        title = entry.get("title") or url
        published_at = entry.get("published") or entry.get("updated")
        item_id = safe_id(feed_id, url)
        now = utc_now()
        try:
            page = await fetch_public_page(url, timeout=8)
            result = ingest_text(
                IngestRequest(
                    source=f"{page['title']} <{page['url']}>",
                    text=page["text"],
                )
            )
            item_url = page["url"]
            item_title = page["title"]
            row = {
                "id": item_id,
                "feed_id": feed_id,
                "url": item_url,
                "title": item_title,
                "published_at": published_at,
                "document_id": result["document_id"],
                "status": "imported",
                "error": None,
                "created_at": now,
            }
            imported += 1
        except Exception as error:
            summary = entry.get("summary") or entry.get("description") or ""
            summary_text = BeautifulSoup(summary, "html.parser").get_text("\n", strip=True)
            if len(summary_text) >= 40:
                result = ingest_text(
                    IngestRequest(
                        source=f"{title} <{url}>",
                        text=summary_text,
                    )
                )
                row = {
                    "id": item_id,
                    "feed_id": feed_id,
                    "url": url,
                    "title": title,
                    "published_at": published_at,
                    "document_id": result["document_id"],
                    "status": "imported",
                    "error": f"已使用 RSS 摘要入库，原文抓取失败：{error}",
                    "created_at": now,
                }
                imported += 1
            else:
                row = {
                    "id": item_id,
                    "feed_id": feed_id,
                    "url": url,
                    "title": title,
                    "published_at": published_at,
                    "document_id": None,
                    "status": "failed",
                    "error": str(error),
                    "created_at": now,
                }
                failed += 1
        items_repo.upsert(row)
        rows.append(row)

    refreshed_at = utc_now()
    feeds_repo().update_refreshed_at(feed_id, refreshed_at)
    return {
        "feed_id": feed_id,
        "title": feed_title or feed.get("title"),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "items": rows,
        "last_refreshed_at": refreshed_at,
    }
