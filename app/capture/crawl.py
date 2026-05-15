from app.capture.service import safe_id, utc_now
from app.core.schemas import CrawlJobCreateRequest, UrlIngestRequest
from app.storage.repo import crawl_jobs_repo


async def create_crawl_job(payload: CrawlJobCreateRequest) -> dict:
    urls = []
    seen = set()
    for value in payload.urls:
        url = value.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)

    if not urls:
        raise ValueError("请至少输入一个 URL。")

    repo = crawl_jobs_repo()
    job_id = safe_id("\n".join(urls), utc_now())
    created_at = utc_now()
    repo.upsert_job(
        {
            "id": job_id,
            "urls": "\n".join(urls),
            "created_at": created_at,
            "status": "running",
            "total": len(urls),
            "succeeded": 0,
            "failed": 0,
        }
    )

    from app.capture.service import ingest_public_url

    succeeded = 0
    failed = 0
    for index, url in enumerate(urls):
        item_id = safe_id(job_id, str(index), url)
        try:
            result = await ingest_public_url(UrlIngestRequest(url=url))
            repo.upsert_item(
                {
                    "id": item_id,
                    "job_id": job_id,
                    "url": result["url"],
                    "title": result["title"],
                    "document_id": result["document_id"],
                    "status": "imported",
                    "error": None,
                }
            )
            succeeded += 1
        except Exception as error:
            repo.upsert_item(
                {
                    "id": item_id,
                    "job_id": job_id,
                    "url": url,
                    "title": None,
                    "document_id": None,
                    "status": "failed",
                    "error": str(error),
                }
            )
            failed += 1

    repo.upsert_job(
        {
            "id": job_id,
            "urls": "\n".join(urls),
            "created_at": created_at,
            "status": "completed",
            "total": len(urls),
            "succeeded": succeeded,
            "failed": failed,
        }
    )
    job = repo.get_job(job_id)
    return job or {"id": job_id, "status": "completed", "total": len(urls), "succeeded": succeeded, "failed": failed}


def get_crawl_job(job_id: str) -> dict | None:
    return crawl_jobs_repo().get_job(job_id)
