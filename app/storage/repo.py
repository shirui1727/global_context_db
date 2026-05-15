import sqlite3
import json
from pathlib import Path

_sqlite_path: Path | None = None


def init_sqlite(path: Path) -> None:
    global _sqlite_path
    _sqlite_path = path
    conn = sqlite3.connect(path)
    conn.execute("pragma journal_mode = wal")
    conn.execute(
        "create table if not exists documents (id text primary key, source text, content text)"
    )
    conn.execute(
        "create table if not exists chunks (id text primary key, doc_id text, chunk_index integer, content text)"
    )
    conn.execute(
        """
        create table if not exists memories (
            id text primary key,
            content text,
            tags text,
            user_id text default 'default',
            agent_id text,
            session_id text,
            conversation_id text,
            memory_type text default 'long_term',
            metadata text default '{}',
            created_at text,
            updated_at text
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_versions (
            id text primary key,
            memory_id text,
            content text,
            tags text,
            user_id text,
            agent_id text,
            session_id text,
            conversation_id text,
            memory_type text,
            metadata text,
            changed_at text,
            change_type text
        )
        """
    )
    conn.execute(
        """
        create table if not exists audit_logs (
            id text primary key,
            actor text,
            action text,
            target_type text,
            target_id text,
            created_at text,
            metadata text
        )
        """
    )
    conn.execute(
        """
        create table if not exists captures (
            id text primary key,
            document_id text,
            url text,
            title text,
            text_preview text,
            html_path text,
            screenshot_path text,
            source_platform text,
            capture_method text,
            tags text,
            captured_at text,
            created_at text,
            status text,
            error text
        )
        """
    )
    conn.execute(
        """
        create table if not exists feeds (
            id text primary key,
            url text unique,
            title text,
            created_at text,
            last_refreshed_at text
        )
        """
    )
    conn.execute(
        """
        create table if not exists feed_items (
            id text primary key,
            feed_id text,
            url text,
            title text,
            published_at text,
            document_id text,
            status text,
            error text,
            created_at text,
            unique(feed_id, url)
        )
        """
    )
    conn.execute(
        """
        create table if not exists crawl_jobs (
            id text primary key,
            urls text,
            created_at text,
            status text,
            total integer,
            succeeded integer,
            failed integer
        )
        """
    )
    conn.execute(
        """
        create table if not exists crawl_job_items (
            id text primary key,
            job_id text,
            url text,
            title text,
            document_id text,
            status text,
            error text
        )
        """
    )
    conn.commit()
    conn.close()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table} add column {name} {definition}")


def _conn() -> sqlite3.Connection:
    if _sqlite_path is None:
        raise RuntimeError("SQLite not initialized")
    return sqlite3.connect(_sqlite_path)


class DocumentsRepo:
    def upsert(self, doc_id: str, source: str, content: str) -> None:
        with _conn() as conn:
            conn.execute(
                "insert or replace into documents(id, source, content) values (?, ?, ?)",
                (doc_id, source, content),
            )

    def list_all(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                "select id, source, content from documents order by rowid desc"
            ).fetchall()
        return [{"id": r[0], "source": r[1], "content": r[2]} for r in rows]


class ChunksRepo:
    def upsert(self, chunk_id: str, doc_id: str, chunk_index: int, content: str) -> None:
        with _conn() as conn:
            conn.execute(
                "insert or replace into chunks(id, doc_id, chunk_index, content) values (?, ?, ?, ?)",
                (chunk_id, doc_id, chunk_index, content),
            )


class MemoriesRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into memories(
                    id, content, tags, user_id, agent_id, session_id, conversation_id,
                    memory_type, metadata, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["content"],
                    ",".join(row.get("tags", [])),
                    row.get("user_id") or "default",
                    row.get("agent_id"),
                    row.get("session_id"),
                    row.get("conversation_id"),
                    row.get("memory_type") or "long_term",
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                    row.get("created_at"),
                    row.get("updated_at"),
                ),
            )

    def get(self, memory_id: str) -> dict | None:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, content, tags, user_id, agent_id, session_id, conversation_id,
                       memory_type, metadata, created_at, updated_at
                from memories
                where id = ?
                """,
                (memory_id,),
            ).fetchall()
        if not rows:
            return None
        return self._decode(rows[0])

    def list_all(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        where = []
        params: list[str | int] = []
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        if agent_id:
            where.append("agent_id = ?")
            params.append(agent_id)
        if memory_type:
            where.append("memory_type = ?")
            params.append(memory_type)
        query = """
            select id, content, tags, user_id, agent_id, session_id, conversation_id,
                   memory_type, metadata, created_at, updated_at
            from memories
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        with _conn() as conn:
            cursor = conn.execute("delete from memories where id = ?", (memory_id,))
            return cursor.rowcount > 0

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        try:
            metadata = json.loads(row[8] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": row[0],
            "content": row[1],
            "tags": [t for t in (row[2] or "").split(",") if t],
            "user_id": row[3] or "default",
            "agent_id": row[4],
            "session_id": row[5],
            "conversation_id": row[6],
            "memory_type": row[7] or "long_term",
            "metadata": metadata,
            "created_at": row[9],
            "updated_at": row[10],
        }


class MemoryVersionsRepo:
    def insert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_versions(
                    id, memory_id, content, tags, user_id, agent_id, session_id,
                    conversation_id, memory_type, metadata, changed_at, change_type
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["memory_id"],
                    row.get("content"),
                    ",".join(row.get("tags", [])),
                    row.get("user_id"),
                    row.get("agent_id"),
                    row.get("session_id"),
                    row.get("conversation_id"),
                    row.get("memory_type"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                    row.get("changed_at"),
                    row.get("change_type"),
                ),
            )

    def list_by_memory(self, memory_id: str, limit: int = 20) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, memory_id, content, tags, user_id, agent_id, session_id,
                       conversation_id, memory_type, metadata, changed_at, change_type
                from memory_versions
                where memory_id = ?
                order by rowid desc
                limit ?
                """,
                (memory_id, limit),
            ).fetchall()
        return [
            {
                "id": r[0],
                "memory_id": r[1],
                "content": r[2],
                "tags": [t for t in (r[3] or "").split(",") if t],
                "user_id": r[4],
                "agent_id": r[5],
                "session_id": r[6],
                "conversation_id": r[7],
                "memory_type": r[8],
                "metadata": json.loads(r[9] or "{}"),
                "changed_at": r[10],
                "change_type": r[11],
            }
            for r in rows
        ]


class AuditLogsRepo:
    def insert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into audit_logs(id, actor, action, target_type, target_id, created_at, metadata)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("actor"),
                    row.get("action"),
                    row.get("target_type"),
                    row.get("target_id"),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_recent(self, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, actor, action, target_type, target_id, created_at, metadata
                from audit_logs
                order by rowid desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "actor": r[1],
                "action": r[2],
                "target_type": r[3],
                "target_id": r[4],
                "created_at": r[5],
                "metadata": json.loads(r[6] or "{}"),
            }
            for r in rows
        ]


class CapturesRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into captures(
                    id, document_id, url, title, text_preview, html_path, screenshot_path,
                    source_platform, capture_method, tags, captured_at, created_at, status, error
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("document_id"),
                    row.get("url"),
                    row.get("title"),
                    row.get("text_preview"),
                    row.get("html_path"),
                    row.get("screenshot_path"),
                    row.get("source_platform"),
                    row.get("capture_method"),
                    row.get("tags", ""),
                    row.get("captured_at"),
                    row.get("created_at"),
                    row.get("status"),
                    row.get("error"),
                ),
            )

    def list_recent(self, limit: int = 50) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, document_id, url, title, text_preview, html_path, screenshot_path,
                       source_platform, capture_method, tags, captured_at, created_at, status, error
                from captures
                order by created_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "document_id": r[1],
                "url": r[2],
                "title": r[3],
                "text_preview": r[4],
                "html_path": r[5],
                "screenshot_path": r[6],
                "source_platform": r[7],
                "capture_method": r[8],
                "tags": [t for t in (r[9] or "").split(",") if t],
                "captured_at": r[10],
                "created_at": r[11],
                "status": r[12],
                "error": r[13],
            }
            for r in rows
        ]


class FeedsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into feeds(id, url, title, created_at, last_refreshed_at)
                values (?, ?, ?, ?, ?)
                on conflict(url) do update set
                    title=excluded.title,
                    last_refreshed_at=coalesce(excluded.last_refreshed_at, feeds.last_refreshed_at)
                """,
                (
                    row["id"],
                    row.get("url"),
                    row.get("title"),
                    row.get("created_at"),
                    row.get("last_refreshed_at"),
                ),
            )

    def update_refreshed_at(self, feed_id: str, refreshed_at: str) -> None:
        with _conn() as conn:
            conn.execute(
                "update feeds set last_refreshed_at = ? where id = ?",
                (refreshed_at, feed_id),
            )

    def list_all(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                "select id, url, title, created_at, last_refreshed_at from feeds order by created_at desc"
            ).fetchall()
        return [
            {
                "id": r[0],
                "url": r[1],
                "title": r[2],
                "created_at": r[3],
                "last_refreshed_at": r[4],
            }
            for r in rows
        ]

    def get(self, feed_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                "select id, url, title, created_at, last_refreshed_at from feeds where id = ?",
                (feed_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "url": row[1],
            "title": row[2],
            "created_at": row[3],
            "last_refreshed_at": row[4],
        }


class FeedItemsRepo:
    def exists(self, feed_id: str, url: str) -> bool:
        with _conn() as conn:
            row = conn.execute(
                "select 1 from feed_items where feed_id = ? and url = ?",
                (feed_id, url),
            ).fetchone()
        return row is not None

    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into feed_items(
                    id, feed_id, url, title, published_at, document_id, status, error, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("feed_id"),
                    row.get("url"),
                    row.get("title"),
                    row.get("published_at"),
                    row.get("document_id"),
                    row.get("status"),
                    row.get("error"),
                    row.get("created_at"),
                ),
            )

    def list_by_feed(self, feed_id: str) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, feed_id, url, title, published_at, document_id, status, error, created_at
                from feed_items
                where feed_id = ?
                order by created_at desc
                """,
                (feed_id,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "feed_id": r[1],
                "url": r[2],
                "title": r[3],
                "published_at": r[4],
                "document_id": r[5],
                "status": r[6],
                "error": r[7],
                "created_at": r[8],
            }
            for r in rows
        ]


class CrawlJobsRepo:
    def upsert_job(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into crawl_jobs(id, urls, created_at, status, total, succeeded, failed)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("urls", ""),
                    row.get("created_at"),
                    row.get("status"),
                    row.get("total", 0),
                    row.get("succeeded", 0),
                    row.get("failed", 0),
                ),
            )

    def upsert_item(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into crawl_job_items(
                    id, job_id, url, title, document_id, status, error
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("job_id"),
                    row.get("url"),
                    row.get("title"),
                    row.get("document_id"),
                    row.get("status"),
                    row.get("error"),
                ),
            )

    def get_job(self, job_id: str) -> dict | None:
        with _conn() as conn:
            job = conn.execute(
                "select id, urls, created_at, status, total, succeeded, failed from crawl_jobs where id = ?",
                (job_id,),
            ).fetchone()
            items = conn.execute(
                """
                select id, job_id, url, title, document_id, status, error
                from crawl_job_items
                where job_id = ?
                order by rowid asc
                """,
                (job_id,),
            ).fetchall()
        if job is None:
            return None
        return {
            "id": job[0],
            "urls": [u for u in (job[1] or "").splitlines() if u],
            "created_at": job[2],
            "status": job[3],
            "total": job[4],
            "succeeded": job[5],
            "failed": job[6],
            "items": [
                {
                    "id": r[0],
                    "job_id": r[1],
                    "url": r[2],
                    "title": r[3],
                    "document_id": r[4],
                    "status": r[5],
                    "error": r[6],
                }
                for r in items
            ],
        }


def documents_repo() -> DocumentsRepo:
    return DocumentsRepo()


def chunks_repo() -> ChunksRepo:
    return ChunksRepo()


def memories_repo() -> MemoriesRepo:
    return MemoriesRepo()


def memory_versions_repo() -> MemoryVersionsRepo:
    return MemoryVersionsRepo()


def audit_logs_repo() -> AuditLogsRepo:
    return AuditLogsRepo()


def captures_repo() -> CapturesRepo:
    return CapturesRepo()


def feeds_repo() -> FeedsRepo:
    return FeedsRepo()


def feed_items_repo() -> FeedItemsRepo:
    return FeedItemsRepo()


def crawl_jobs_repo() -> CrawlJobsRepo:
    return CrawlJobsRepo()
