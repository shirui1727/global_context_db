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
        """
        create table if not exists context_cubes (
            id text primary key,
            name text,
            cube_type text default 'project',
            owner_id text,
            visibility text default 'private',
            status text default 'active',
            created_by text,
            created_at text,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists cube_bindings (
            id text primary key,
            cube_id text,
            target_domain text,
            target_id text,
            binding_kind text default 'owns',
            created_at text,
            metadata text default '{}',
            unique(cube_id, target_domain, target_id, binding_kind)
        )
        """
    )
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
            cube_id text,
            tags text,
            user_id text default 'default',
            agent_id text,
            session_id text,
            conversation_id text,
            memory_type text default 'long_term',
            context_domain text default 'memory',
            status text default 'active',
            source_kind text default 'agent_note',
            trust_level text default 'verified',
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
        create table if not exists memory_evidence (
            id text primary key,
            memory_id text,
            source_domain text,
            source_id text,
            quote text,
            confidence real default 1.0,
            source_span text default '{}',
            created_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_lifecycle_events (
            id text primary key,
            memory_id text,
            from_status text,
            to_status text,
            event_kind text,
            actor text,
            created_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_relations (
            id text primary key,
            source_domain text,
            source_id text,
            relation_kind text,
            target_domain text,
            target_id text,
            weight real default 1.0,
            created_at text,
            metadata text default '{}',
            unique(source_domain, source_id, relation_kind, target_domain, target_id)
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_candidates (
            id text primary key,
            cube_id text,
            source_domain text,
            source_id text,
            content text,
            content_kind text default 'note',
            tags text,
            status text default 'candidate',
            confidence real default 1.0,
            provenance text default '{}',
            evidence text default '[]',
            created_by text,
            created_at text,
            updated_at text,
            promoted_memory_id text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_feedback (
            id text primary key,
            cube_id text,
            feedback_text text,
            target_memory_id text,
            status text default 'pending',
            created_by text,
            created_at text,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_feedback_actions (
            id text primary key,
            feedback_id text,
            action_type text,
            target_memory_id text,
            payload text default '{}',
            status text default 'pending',
            applied_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists hook_subscriptions (
            id text primary key,
            hook_name text,
            target_kind text default 'queue',
            target_ref text,
            status text default 'active',
            created_by text,
            created_at text,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists hook_events (
            id text primary key,
            hook_name text,
            subscription_id text,
            source_kind text,
            source_id text,
            payload text default '{}',
            status text default 'queued',
            created_at text,
            dispatched_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists memory_promotion_proposals (
            id text primary key,
            source_session_id text,
            source_event_ids text default '[]',
            proposed_content text,
            cube_id text,
            tags text,
            memory_type text default 'long_term',
            user_id text default 'default',
            agent_id text,
            project_path text,
            status text default 'pending',
            reason text,
            created_by text,
            reviewed_by text,
            created_at text,
            updated_at text,
            reviewed_at text,
            promoted_memory_id text,
            metadata text default '{}'
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
    conn.execute(
        """
        create table if not exists file_references (
            id text primary key,
            uri text unique,
            title text,
            media_type text,
            asset_kind text,
            asset_key text,
            size_bytes integer,
            checksum text,
            summary text,
            tags text,
            storage_mode text default 'referenced',
            context_domain text default 'asset',
            status text default 'active',
            source_kind text default 'nas_reference',
            trust_level text default 'unverified',
            version_group_id text,
            analysis_status text default 'indexed',
            last_seen_at text,
            missing_since text,
            content_changed_at text,
            derived_artifacts text default '{}',
            metadata text default '{}',
            created_at text,
            updated_at text
        )
        """
    )
    conn.execute(
        """
        create table if not exists assets (
            id text primary key,
            cube_id text,
            asset_key text,
            asset_kind text,
            title text,
            summary text,
            tags text,
            media_type text,
            status text default 'active',
            trust_level text default 'unverified',
            source_kind text default 'nas_reference',
            analysis_status text default 'indexed',
            created_by text,
            updated_by text,
            confirmed_by text,
            created_at text,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists asset_locations (
            id text primary key,
            asset_id text,
            uri text unique,
            uri_normalized text,
            storage_mode text default 'referenced',
            location_status text default 'active',
            last_seen_at text,
            missing_since text,
            forbidden_since text,
            created_at text,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists asset_versions (
            id text primary key,
            asset_id text,
            version_group_id text,
            checksum text,
            size_bytes integer,
            modified_at text,
            content_signature text,
            version_status text default 'current',
            is_current integer default 1,
            created_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists asset_artifacts (
            id text primary key,
            asset_id text,
            version_id text,
            artifact_kind text,
            artifact_uri text,
            media_type text,
            checksum text,
            status text default 'pending',
            generated_by text,
            created_at text,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists asset_scan_runs (
            id text primary key,
            scope_prefix text,
            status text,
            observed_count integer default 0,
            created_by text,
            started_at text,
            finished_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists agent_sessions (
            id text primary key,
            cube_id text,
            source_agent text,
            project_path text,
            status text default 'running',
            title text,
            summary text,
            started_at text,
            last_activity_at text,
            ended_at text,
            created_by text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists session_events (
            id text primary key,
            session_id text,
            event_type text,
            role text,
            content text,
            tool_name text,
            tool_args text default '{}',
            tool_result text,
            created_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists session_traces (
            id text primary key,
            session_id text,
            trace_id text,
            origin_function text,
            status text,
            memory_query text,
            memory_context text,
            method_params text default '{}',
            method_return_value text,
            error_message text,
            feedback_text text,
            created_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists session_summaries (
            id text primary key,
            session_id text,
            summary_kind text,
            content text,
            status text default 'active',
            created_by text,
            created_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists session_model_usage (
            id text primary key,
            session_id text,
            model text,
            tokens_in integer default 0,
            tokens_out integer default 0,
            cost_usd real default 0,
            updated_at text,
            metadata text default '{}'
        )
        """
    )
    conn.execute(
        """
        create table if not exists improvement_tasks (
            id text primary key,
            cube_id text,
            task_kind text,
            target_domain text,
            target_id text,
            status text default 'pending',
            priority integer default 50,
            reason text,
            created_by text,
            claimed_by text,
            created_at text,
            updated_at text,
            finished_at text,
            error_message text,
            retry_count integer default 0,
            max_retries integer default 3,
            next_run_at text,
            claimed_at text,
            claimed_until text,
            worker_id text,
            queue_name text default 'default',
            last_error text,
            metadata text default '{}',
            unique(task_kind, target_domain, target_id)
        )
        """
    )
    _ensure_columns(
        conn,
        "memories",
        {
            "cube_id": "text",
            "context_domain": "text default 'memory'",
            "status": "text default 'active'",
            "source_kind": "text default 'agent_note'",
            "trust_level": "text default 'verified'",
        },
    )
    _ensure_columns(
        conn,
        "file_references",
        {
            "asset_kind": "text",
            "asset_key": "text",
            "context_domain": "text default 'asset'",
            "status": "text default 'active'",
            "source_kind": "text default 'nas_reference'",
            "trust_level": "text default 'unverified'",
            "version_group_id": "text",
            "analysis_status": "text default 'indexed'",
            "last_seen_at": "text",
            "missing_since": "text",
            "content_changed_at": "text",
            "derived_artifacts": "text default '{}'",
        },
    )
    _ensure_columns(
        conn,
        "assets",
        {
            "cube_id": "text",
            "analysis_status": "text default 'indexed'",
            "updated_by": "text",
        },
    )
    _ensure_columns(conn, "agent_sessions", {"cube_id": "text"})
    _ensure_columns(
        conn,
        "improvement_tasks",
        {
            "cube_id": "text",
            "retry_count": "integer default 0",
            "max_retries": "integer default 3",
            "next_run_at": "text",
            "claimed_at": "text",
            "claimed_until": "text",
            "worker_id": "text",
            "queue_name": "text default 'default'",
            "last_error": "text",
        },
    )
    _ensure_columns(conn, "memory_promotion_proposals", {"cube_id": "text"})
    _ensure_columns(conn, "memory_evidence", {"source_span": "text default '{}'"})
    _ensure_columns(
        conn,
        "memory_candidates",
        {
            "cube_id": "text",
            "promoted_memory_id": "text",
            "evidence": "text default '[]'",
        },
    )
    _ensure_indexes(conn)
    conn.commit()
    conn.close()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table} add column {name} {definition}")


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    indexes = [
        "create index if not exists idx_context_cubes_type on context_cubes(cube_type)",
        "create index if not exists idx_context_cubes_owner on context_cubes(owner_id)",
        "create index if not exists idx_cube_bindings_cube on cube_bindings(cube_id)",
        "create index if not exists idx_cube_bindings_target on cube_bindings(target_domain, target_id)",
        "create index if not exists idx_assets_cube on assets(cube_id)",
        "create index if not exists idx_memories_cube on memories(cube_id)",
        "create index if not exists idx_sessions_cube on agent_sessions(cube_id)",
        "create index if not exists idx_assets_asset_key on assets(asset_key)",
        "create index if not exists idx_assets_status on assets(status)",
        "create index if not exists idx_assets_kind on assets(asset_kind)",
        "create index if not exists idx_assets_trust on assets(trust_level)",
        "create index if not exists idx_memory_evidence_memory_id on memory_evidence(memory_id)",
        "create index if not exists idx_memory_evidence_source on memory_evidence(source_domain, source_id)",
        "create index if not exists idx_memory_lifecycle_memory_id on memory_lifecycle_events(memory_id)",
        "create index if not exists idx_memory_lifecycle_kind on memory_lifecycle_events(event_kind)",
        "create index if not exists idx_memory_relations_source on memory_relations(source_domain, source_id)",
        "create index if not exists idx_memory_relations_target on memory_relations(target_domain, target_id)",
        "create index if not exists idx_memory_relations_kind on memory_relations(relation_kind)",
        "create index if not exists idx_memory_candidates_status on memory_candidates(status)",
        "create index if not exists idx_memory_candidates_source on memory_candidates(source_domain, source_id)",
        "create index if not exists idx_hook_subscriptions_name_status on hook_subscriptions(hook_name, status)",
        "create index if not exists idx_hook_events_name_status on hook_events(hook_name, status)",
        "create index if not exists idx_hook_events_subscription on hook_events(subscription_id)",
        "create index if not exists idx_memory_promotions_status on memory_promotion_proposals(status)",
        "create index if not exists idx_memory_promotions_session on memory_promotion_proposals(source_session_id)",
        "create index if not exists idx_asset_locations_asset_id on asset_locations(asset_id)",
        "create index if not exists idx_asset_locations_uri_normalized on asset_locations(uri_normalized)",
        "create index if not exists idx_asset_locations_status on asset_locations(location_status)",
        "create index if not exists idx_asset_versions_asset_id on asset_versions(asset_id)",
        "create index if not exists idx_asset_versions_current on asset_versions(asset_id, is_current)",
        "create index if not exists idx_asset_artifacts_asset_id on asset_artifacts(asset_id)",
        "create index if not exists idx_asset_artifacts_version_id on asset_artifacts(version_id)",
        "create index if not exists idx_asset_scan_runs_scope on asset_scan_runs(scope_prefix)",
        "create index if not exists idx_audit_logs_target on audit_logs(target_type, target_id)",
        "create index if not exists idx_agent_sessions_status on agent_sessions(status)",
        "create index if not exists idx_agent_sessions_project_path on agent_sessions(project_path)",
        "create index if not exists idx_agent_sessions_last_activity on agent_sessions(last_activity_at)",
        "create index if not exists idx_session_events_session_id on session_events(session_id)",
        "create index if not exists idx_session_events_type on session_events(event_type)",
        "create index if not exists idx_session_traces_session_id on session_traces(session_id)",
        "create index if not exists idx_session_summaries_session_id on session_summaries(session_id)",
        "create index if not exists idx_session_model_usage_session_id on session_model_usage(session_id)",
        "create index if not exists idx_improvement_tasks_status on improvement_tasks(status)",
        "create index if not exists idx_improvement_tasks_target on improvement_tasks(target_domain, target_id)",
    ]
    for statement in indexes:
        conn.execute(statement)


def _json_loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _hash_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_uri(uri: str) -> str:
    return uri.strip().replace("\\", "/")


def _conn() -> sqlite3.Connection:
    if _sqlite_path is None:
        raise RuntimeError("SQLite not initialized")
    return sqlite3.connect(_sqlite_path)


def sqlite_path() -> Path:
    if _sqlite_path is None:
        raise RuntimeError("SQLite not initialized")
    return _sqlite_path


def db_counts() -> dict[str, int]:
    tables = [
        "context_cubes",
        "cube_bindings",
        "documents",
        "chunks",
        "memories",
        "memory_versions",
        "memory_evidence",
        "memory_lifecycle_events",
        "memory_relations",
        "memory_candidates",
        "memory_feedback",
        "memory_feedback_actions",
        "hook_subscriptions",
        "hook_events",
        "memory_promotion_proposals",
        "audit_logs",
        "captures",
        "feeds",
        "feed_items",
        "crawl_jobs",
        "crawl_job_items",
        "file_references",
        "assets",
        "asset_locations",
        "asset_versions",
        "asset_artifacts",
        "asset_scan_runs",
        "agent_sessions",
        "session_events",
        "session_traces",
        "session_summaries",
        "session_model_usage",
        "improvement_tasks",
    ]
    with _conn() as conn:
        return {table: int(conn.execute(f"select count(*) from {table}").fetchone()[0]) for table in tables}


def failed_operations(limit: int = 20) -> list[dict]:
    query = """
        select 'capture' as source, id, status, error, created_at
        from captures
        where status = 'failed' or error is not null
        union all
        select 'feed_item' as source, id, status, error, created_at
        from feed_items
        where status = 'failed' or error is not null
        union all
        select 'crawl_item' as source, id, status, error, null as created_at
        from crawl_job_items
        where status = 'failed' or error is not null
        order by created_at desc
        limit ?
    """
    with _conn() as conn:
        rows = conn.execute(query, (limit,)).fetchall()
    return [
        {
            "source": row[0],
            "id": row[1],
            "status": row[2],
            "error": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


class ContextCubesRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into context_cubes(
                    id, name, cube_type, owner_id, visibility, status,
                    created_by, created_at, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    name=coalesce(excluded.name, context_cubes.name),
                    cube_type=coalesce(excluded.cube_type, context_cubes.cube_type),
                    owner_id=coalesce(excluded.owner_id, context_cubes.owner_id),
                    visibility=coalesce(excluded.visibility, context_cubes.visibility),
                    status=coalesce(excluded.status, context_cubes.status),
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("name"),
                    row.get("cube_type") or "project",
                    row.get("owner_id"),
                    row.get("visibility") or "private",
                    row.get("status") or "active",
                    row.get("created_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, cube_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, name, cube_type, owner_id, visibility, status,
                       created_by, created_at, updated_at, metadata
                from context_cubes where id = ?
                """,
                (cube_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(
        self,
        limit: int = 100,
        cube_type: str | None = None,
        owner_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        where = []
        params: list[str | int] = []
        if cube_type:
            where.append("cube_type = ?")
            params.append(cube_type)
        if owner_id:
            where.append("owner_id = ?")
            params.append(owner_id)
        if status:
            where.append("status = ?")
            params.append(status)
        query = """
            select id, name, cube_type, owner_id, visibility, status,
                   created_by, created_at, updated_at, metadata
            from context_cubes
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by updated_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "name": row[1],
            "cube_type": row[2] or "project",
            "owner_id": row[3],
            "visibility": row[4] or "private",
            "status": row[5] or "active",
            "created_by": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "metadata": _json_loads(row[9], {}),
        }


class CubeBindingsRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into cube_bindings(
                    id, cube_id, target_domain, target_id, binding_kind, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(cube_id, target_domain, target_id, binding_kind) do update set
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("cube_id"),
                    row.get("target_domain"),
                    row.get("target_id"),
                    row.get("binding_kind") or "owns",
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
            saved = conn.execute(
                """
                select id, cube_id, target_domain, target_id, binding_kind, created_at, metadata
                from cube_bindings
                where cube_id = ? and target_domain = ? and target_id = ? and binding_kind = ?
                """,
                (row.get("cube_id"), row.get("target_domain"), row.get("target_id"), row.get("binding_kind") or "owns"),
            ).fetchone()
        return self._decode(saved)

    def list_by_cube(self, cube_id: str, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, cube_id, target_domain, target_id, binding_kind, created_at, metadata
                from cube_bindings
                where cube_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (cube_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def list_by_target(self, target_domain: str, target_id: str, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, cube_id, target_domain, target_id, binding_kind, created_at, metadata
                from cube_bindings
                where target_domain = ? and target_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (target_domain, target_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "cube_id": row[1],
            "target_domain": row[2],
            "target_id": row[3],
            "binding_kind": row[4] or "owns",
            "created_at": row[5],
            "metadata": _json_loads(row[6], {}),
        }


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


class FileReferencesRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into file_references(
                    id, uri, title, media_type, asset_kind, asset_key, size_bytes,
                    checksum, summary, tags, storage_mode, context_domain, status,
                    source_kind, trust_level, version_group_id, analysis_status,
                    last_seen_at, missing_since, content_changed_at, derived_artifacts,
                    metadata, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(uri) do update set
                    title=excluded.title,
                    media_type=excluded.media_type,
                    asset_kind=excluded.asset_kind,
                    asset_key=excluded.asset_key,
                    size_bytes=excluded.size_bytes,
                    checksum=excluded.checksum,
                    summary=excluded.summary,
                    tags=excluded.tags,
                    storage_mode=excluded.storage_mode,
                    context_domain=excluded.context_domain,
                    status=excluded.status,
                    source_kind=excluded.source_kind,
                    trust_level=excluded.trust_level,
                    version_group_id=excluded.version_group_id,
                    analysis_status=excluded.analysis_status,
                    last_seen_at=excluded.last_seen_at,
                    missing_since=excluded.missing_since,
                    content_changed_at=excluded.content_changed_at,
                    derived_artifacts=excluded.derived_artifacts,
                    metadata=excluded.metadata,
                    updated_at=excluded.updated_at
                """,
                (
                    row["id"],
                    row.get("uri"),
                    row.get("title"),
                    row.get("media_type"),
                    row.get("asset_kind"),
                    row.get("asset_key"),
                    row.get("size_bytes"),
                    row.get("checksum"),
                    row.get("summary"),
                    ",".join(row.get("tags", [])),
                    row.get("storage_mode") or "referenced",
                    row.get("context_domain") or "asset",
                    row.get("status") or "active",
                    row.get("source_kind") or "nas_reference",
                    row.get("trust_level") or "unverified",
                    row.get("version_group_id"),
                    row.get("analysis_status") or "indexed",
                    row.get("last_seen_at"),
                    row.get("missing_since"),
                    row.get("content_changed_at"),
                    json.dumps(row.get("derived_artifacts") or {}, ensure_ascii=False),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                    row.get("created_at"),
                    row.get("updated_at"),
                ),
            )

    def get_by_uri(self, uri: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, uri, title, media_type, asset_kind, asset_key, size_bytes,
                       checksum, summary, tags, storage_mode, context_domain, status,
                       source_kind, trust_level, version_group_id, analysis_status,
                       last_seen_at, missing_since, content_changed_at, derived_artifacts,
                       metadata, created_at, updated_at
                from file_references
                where uri = ?
                """,
                (uri,),
            ).fetchone()
        return self._decode(row) if row else None

    def get(self, file_reference_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, uri, title, media_type, asset_kind, asset_key, size_bytes,
                       checksum, summary, tags, storage_mode, context_domain, status,
                       source_kind, trust_level, version_group_id, analysis_status,
                       last_seen_at, missing_since, content_changed_at, derived_artifacts,
                       metadata, created_at, updated_at
                from file_references
                where id = ?
                """,
                (file_reference_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(
        self,
        limit: int = 100,
        status: str | None = None,
        media_type: str | None = None,
        asset_kind: str | None = None,
        trust_level: str | None = None,
    ) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if media_type:
            where.append("media_type = ?")
            params.append(media_type)
        if asset_kind:
            where.append("asset_kind = ?")
            params.append(asset_kind)
        if trust_level:
            where.append("trust_level = ?")
            params.append(trust_level)
        query = """
                select id, uri, title, media_type, asset_kind, asset_key, size_bytes,
                       checksum, summary, tags, storage_mode, context_domain, status,
                       source_kind, trust_level, version_group_id, analysis_status,
                       last_seen_at, missing_since, content_changed_at, derived_artifacts,
                       metadata, created_at, updated_at
                from file_references
                """
        if where:
            query += " where " + " and ".join(where)
        query += " order by updated_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        try:
            derived_artifacts = json.loads(row[20] or "{}")
        except json.JSONDecodeError:
            derived_artifacts = {}
        try:
            metadata = json.loads(row[21] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": row[0],
            "uri": row[1],
            "title": row[2],
            "media_type": row[3],
            "asset_kind": row[4],
            "asset_key": row[5],
            "size_bytes": row[6],
            "checksum": row[7],
            "summary": row[8],
            "tags": [tag for tag in (row[9] or "").split(",") if tag],
            "storage_mode": row[10] or "referenced",
            "context_domain": row[11] or "asset",
            "status": row[12] or "active",
            "source_kind": row[13] or "nas_reference",
            "trust_level": row[14] or "unverified",
            "version_group_id": row[15],
            "analysis_status": row[16] or "indexed",
            "last_seen_at": row[17],
            "missing_since": row[18],
            "content_changed_at": row[19],
            "derived_artifacts": derived_artifacts,
            "metadata": metadata,
            "created_at": row[22],
            "updated_at": row[23],
        }

    def status_counts(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(status, 'active'), coalesce(analysis_status, 'indexed'),
                       coalesce(trust_level, 'unverified'), count(*)
                from file_references
                group by coalesce(status, 'active'), coalesce(analysis_status, 'indexed'),
                         coalesce(trust_level, 'unverified')
                order by count(*) desc
                """
            ).fetchall()
        return [
            {
                "status": row[0],
                "analysis_status": row[1],
                "trust_level": row[2],
                "count": row[3],
            }
            for row in rows
        ]

    def duplicate_assets(self, limit: int = 50) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(asset_key, checksum), count(*) as duplicate_count,
                       group_concat(id), group_concat(uri), max(updated_at)
                from file_references
                where coalesce(asset_key, checksum, '') != ''
                group by coalesce(asset_key, checksum)
                having count(*) > 1
                order by duplicate_count desc, max(updated_at) desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "asset_key": row[0],
                "duplicate_count": row[1],
                "ids": [item for item in (row[2] or "").split(",") if item],
                "uris": [item for item in (row[3] or "").split(",") if item],
                "last_updated_at": row[4],
            }
            for row in rows
        ]


class AssetsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into assets(
                    id, cube_id, asset_key, asset_kind, title, summary, tags, media_type, status,
                    trust_level, source_kind, analysis_status, created_by, updated_by,
                    confirmed_by, created_at, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    cube_id=coalesce(excluded.cube_id, assets.cube_id),
                    asset_key=coalesce(excluded.asset_key, assets.asset_key),
                    asset_kind=coalesce(excluded.asset_kind, assets.asset_kind),
                    title=coalesce(excluded.title, assets.title),
                    summary=coalesce(excluded.summary, assets.summary),
                    tags=coalesce(excluded.tags, assets.tags),
                    media_type=coalesce(excluded.media_type, assets.media_type),
                    status=coalesce(excluded.status, assets.status),
                    trust_level=coalesce(excluded.trust_level, assets.trust_level),
                    source_kind=coalesce(excluded.source_kind, assets.source_kind),
                    analysis_status=coalesce(excluded.analysis_status, assets.analysis_status),
                    updated_by=coalesce(excluded.updated_by, assets.updated_by),
                    confirmed_by=coalesce(excluded.confirmed_by, assets.confirmed_by),
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("cube_id"),
                    row.get("asset_key"),
                    row.get("asset_kind"),
                    row.get("title"),
                    row.get("summary"),
                    ",".join(row.get("tags", [])) if isinstance(row.get("tags"), list) else row.get("tags"),
                    row.get("media_type"),
                    row.get("status") or "active",
                    row.get("trust_level") or "unverified",
                    row.get("source_kind") or "nas_reference",
                    row.get("analysis_status") or "indexed",
                    row.get("created_by"),
                    row.get("updated_by"),
                    row.get("confirmed_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def get(self, asset_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, cube_id, asset_key, asset_kind, title, summary, tags, media_type, status,
                       trust_level, source_kind, analysis_status, created_by, updated_by,
                       confirmed_by, created_at, updated_at, metadata
                from assets
                where id = ?
                """,
                (asset_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def get_by_legacy_file_reference_id(self, file_reference_id: str) -> dict | None:
        with _conn() as conn:
            uri_row = conn.execute("select uri from file_references where id = ?", (file_reference_id,)).fetchone()
            if not uri_row:
                return None
            location_row = conn.execute("select asset_id from asset_locations where uri = ?", (uri_row[0],)).fetchone()
        if not location_row:
            return None
        return self.get(location_row[0])

    def list_recent(
        self,
        limit: int = 100,
        status: str | None = None,
        asset_kind: str | None = None,
        trust_level: str | None = None,
    ) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if asset_kind:
            where.append("asset_kind = ?")
            params.append(asset_kind)
        if trust_level:
            where.append("trust_level = ?")
            params.append(trust_level)
        query = """
            select id, cube_id, asset_key, asset_kind, title, summary, tags, media_type, status,
                   trust_level, source_kind, analysis_status, created_by, updated_by,
                   confirmed_by, created_at, updated_at, metadata
            from assets
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by updated_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def status_counts(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(status, 'active'), coalesce(analysis_status, 'indexed'),
                       coalesce(trust_level, 'unverified'), count(*)
                from assets
                group by coalesce(status, 'active'), coalesce(analysis_status, 'indexed'),
                         coalesce(trust_level, 'unverified')
                order by count(*) desc
                """
            ).fetchall()
        return [
            {
                "status": row[0],
                "analysis_status": row[1],
                "trust_level": row[2],
                "count": row[3],
            }
            for row in rows
        ]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "cube_id": row[1],
            "asset_key": row[2],
            "asset_kind": row[3],
            "title": row[4],
            "summary": row[5] or "",
            "tags": [tag for tag in (row[6] or "").split(",") if tag],
            "media_type": row[7],
            "status": row[8] or "active",
            "trust_level": row[9] or "unverified",
            "source_kind": row[10] or "nas_reference",
            "analysis_status": row[11] or "indexed",
            "created_by": row[12],
            "updated_by": row[13],
            "confirmed_by": row[14],
            "created_at": row[15],
            "updated_at": row[16],
            "metadata": _json_loads(row[17], {}),
        }


class AssetLocationsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into asset_locations(
                    id, asset_id, uri, uri_normalized, storage_mode, location_status,
                    last_seen_at, missing_since, forbidden_since, created_at, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(uri) do update set
                    asset_id=excluded.asset_id,
                    uri_normalized=excluded.uri_normalized,
                    storage_mode=excluded.storage_mode,
                    location_status=excluded.location_status,
                    last_seen_at=excluded.last_seen_at,
                    missing_since=excluded.missing_since,
                    forbidden_since=excluded.forbidden_since,
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("asset_id"),
                    row.get("uri"),
                    row.get("uri_normalized"),
                    row.get("storage_mode") or "referenced",
                    row.get("location_status") or "active",
                    row.get("last_seen_at"),
                    row.get("missing_since"),
                    row.get("forbidden_since"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_by_asset(self, asset_id: str) -> list[dict]:
        return self._query("where asset_id = ?", [asset_id])

    def get_by_uri(self, uri: str) -> dict | None:
        rows = self._query("where uri = ?", [uri])
        return rows[0] if rows else None

    def list_by_scope(self, scope_prefix: str) -> list[dict]:
        return self._query("where uri_normalized like ?", [f"{scope_prefix.rstrip('/')}%"])

    def mark_missing_not_observed(self, scope_prefix: str, observed_uris: set[str], missing_since: str) -> int:
        rows = self.list_by_scope(scope_prefix)
        changed = 0
        for row in rows:
            if row["uri_normalized"] in observed_uris:
                continue
            row["location_status"] = "missing"
            row["missing_since"] = row.get("missing_since") or missing_since
            row["updated_at"] = missing_since
            self.upsert(row)
            changed += 1
        return changed

    def _query(self, where: str, params: list) -> list[dict]:
        query = f"""
            select id, asset_id, uri, uri_normalized, storage_mode, location_status,
                   last_seen_at, missing_since, forbidden_since, created_at, updated_at, metadata
            from asset_locations
            {where}
            order by updated_at desc, rowid desc
        """
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "asset_id": row[1],
            "uri": row[2],
            "uri_normalized": row[3],
            "storage_mode": row[4] or "referenced",
            "location_status": row[5] or "active",
            "last_seen_at": row[6],
            "missing_since": row[7],
            "forbidden_since": row[8],
            "created_at": row[9],
            "updated_at": row[10],
            "metadata": _json_loads(row[11], {}),
        }


class AssetVersionsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into asset_versions(
                    id, asset_id, version_group_id, checksum, size_bytes, modified_at,
                    content_signature, version_status, is_current, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    version_group_id=excluded.version_group_id,
                    checksum=excluded.checksum,
                    size_bytes=excluded.size_bytes,
                    modified_at=excluded.modified_at,
                    content_signature=excluded.content_signature,
                    version_status=excluded.version_status,
                    is_current=excluded.is_current,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("asset_id"),
                    row.get("version_group_id"),
                    row.get("checksum"),
                    row.get("size_bytes"),
                    row.get("modified_at"),
                    row.get("content_signature"),
                    row.get("version_status") or "current",
                    1 if row.get("is_current", True) else 0,
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def supersede_current(self, asset_id: str) -> None:
        with _conn() as conn:
            conn.execute(
                "update asset_versions set version_status = 'superseded', is_current = 0 where asset_id = ? and is_current = 1",
                (asset_id,),
            )

    def get_current(self, asset_id: str) -> dict | None:
        rows = self.list_by_asset(asset_id)
        for row in rows:
            if row["is_current"]:
                return row
        return None

    def list_by_asset(self, asset_id: str) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, asset_id, version_group_id, checksum, size_bytes, modified_at,
                       content_signature, version_status, is_current, created_at, metadata
                from asset_versions
                where asset_id = ?
                order by is_current desc, created_at desc, rowid desc
                """,
                (asset_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "asset_id": row[1],
            "version_group_id": row[2],
            "checksum": row[3],
            "size_bytes": row[4],
            "modified_at": row[5],
            "content_signature": row[6],
            "version_status": row[7] or "current",
            "is_current": bool(row[8]),
            "created_at": row[9],
            "metadata": _json_loads(row[10], {}),
        }


class AssetArtifactsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into asset_artifacts(
                    id, asset_id, version_id, artifact_kind, artifact_uri, media_type,
                    checksum, status, generated_by, created_at, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    artifact_uri=coalesce(excluded.artifact_uri, asset_artifacts.artifact_uri),
                    media_type=coalesce(excluded.media_type, asset_artifacts.media_type),
                    checksum=coalesce(excluded.checksum, asset_artifacts.checksum),
                    status=coalesce(excluded.status, asset_artifacts.status),
                    generated_by=coalesce(excluded.generated_by, asset_artifacts.generated_by),
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("asset_id"),
                    row.get("version_id"),
                    row.get("artifact_kind"),
                    row.get("artifact_uri"),
                    row.get("media_type"),
                    row.get("checksum"),
                    row.get("status") or "pending",
                    row.get("generated_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def stale_for_old_versions(self, asset_id: str, current_version_id: str | None, updated_at: str) -> None:
        with _conn() as conn:
            conn.execute(
                """
                update asset_artifacts
                set status = 'stale', updated_at = ?
                where asset_id = ? and status in ('pending', 'ready') and coalesce(version_id, '') != coalesce(?, '')
                """,
                (updated_at, asset_id, current_version_id),
            )

    def get(self, artifact_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, asset_id, version_id, artifact_kind, artifact_uri, media_type,
                       checksum, status, generated_by, created_at, updated_at, metadata
                from asset_artifacts where id = ?
                """,
                (artifact_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_by_asset(self, asset_id: str) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, asset_id, version_id, artifact_kind, artifact_uri, media_type,
                       checksum, status, generated_by, created_at, updated_at, metadata
                from asset_artifacts
                where asset_id = ?
                order by updated_at desc, rowid desc
                """,
                (asset_id,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "asset_id": row[1],
            "version_id": row[2],
            "artifact_kind": row[3],
            "artifact_uri": row[4],
            "media_type": row[5],
            "checksum": row[6],
            "status": row[7] or "pending",
            "generated_by": row[8],
            "created_at": row[9],
            "updated_at": row[10],
            "metadata": _json_loads(row[11], {}),
        }


class AssetScanRunsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into asset_scan_runs(
                    id, scope_prefix, status, observed_count, created_by,
                    started_at, finished_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("scope_prefix"),
                    row.get("status"),
                    row.get("observed_count", 0),
                    row.get("created_by"),
                    row.get("started_at"),
                    row.get("finished_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def get(self, scan_run_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, scope_prefix, status, observed_count, created_by,
                       started_at, finished_at, metadata
                from asset_scan_runs where id = ?
                """,
                (scan_run_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "scope_prefix": row[1],
            "status": row[2],
            "observed_count": row[3],
            "created_by": row[4],
            "started_at": row[5],
            "finished_at": row[6],
            "metadata": _json_loads(row[7], {}),
        }


class AgentSessionsRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert into agent_sessions(
                    id, cube_id, source_agent, project_path, status, title, summary,
                    started_at, last_activity_at, ended_at, created_by, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    cube_id=coalesce(excluded.cube_id, agent_sessions.cube_id),
                    source_agent=coalesce(excluded.source_agent, agent_sessions.source_agent),
                    project_path=coalesce(excluded.project_path, agent_sessions.project_path),
                    status=coalesce(excluded.status, agent_sessions.status),
                    title=coalesce(excluded.title, agent_sessions.title),
                    summary=coalesce(excluded.summary, agent_sessions.summary),
                    last_activity_at=coalesce(excluded.last_activity_at, agent_sessions.last_activity_at),
                    ended_at=coalesce(excluded.ended_at, agent_sessions.ended_at),
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("cube_id"),
                    row.get("source_agent"),
                    row.get("project_path"),
                    row.get("status") or "running",
                    row.get("title"),
                    row.get("summary"),
                    row.get("started_at"),
                    row.get("last_activity_at"),
                    row.get("ended_at"),
                    row.get("created_by"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def get(self, session_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, cube_id, source_agent, project_path, status, title, summary,
                       started_at, last_activity_at, ended_at, created_by, metadata
                from agent_sessions
                where id = ?
                """,
                (session_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(
        self,
        limit: int = 100,
        status: str | None = None,
        source_agent: str | None = None,
        project_path: str | None = None,
    ) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if source_agent:
            where.append("source_agent = ?")
            params.append(source_agent)
        if project_path:
            where.append("project_path = ?")
            params.append(project_path)
        query = """
            select id, cube_id, source_agent, project_path, status, title, summary,
                   started_at, last_activity_at, ended_at, created_by, metadata
            from agent_sessions
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by last_activity_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def touch(self, session_id: str, last_activity_at: str) -> None:
        with _conn() as conn:
            conn.execute(
                "update agent_sessions set last_activity_at = ? where id = ?",
                (last_activity_at, session_id),
            )

    def status_counts(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(status, 'running'), coalesce(source_agent, ''), count(*)
                from agent_sessions
                group by coalesce(status, 'running'), coalesce(source_agent, '')
                order by count(*) desc
                """
            ).fetchall()
        return [{"status": row[0], "source_agent": row[1], "count": row[2]} for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "cube_id": row[1],
            "source_agent": row[2],
            "project_path": row[3],
            "status": row[4] or "running",
            "title": row[5],
            "summary": row[6] or "",
            "started_at": row[7],
            "last_activity_at": row[8],
            "ended_at": row[9],
            "created_by": row[10],
            "metadata": _json_loads(row[11], {}),
        }


class SessionEventsRepo:
    def insert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into session_events(
                    id, session_id, event_type, role, content, tool_name,
                    tool_args, tool_result, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("session_id"),
                    row.get("event_type"),
                    row.get("role"),
                    row.get("content"),
                    row.get("tool_name"),
                    json.dumps(row.get("tool_args") or {}, ensure_ascii=False),
                    row.get("tool_result"),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_by_session(self, session_id: str, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, session_id, event_type, role, content, tool_name,
                       tool_args, tool_result, created_at, metadata
                from session_events
                where session_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "session_id": row[1],
            "event_type": row[2],
            "role": row[3],
            "content": row[4] or "",
            "tool_name": row[5],
            "tool_args": _json_loads(row[6], {}),
            "tool_result": row[7],
            "created_at": row[8],
            "metadata": _json_loads(row[9], {}),
        }


class SessionTracesRepo:
    def insert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into session_traces(
                    id, session_id, trace_id, origin_function, status, memory_query,
                    memory_context, method_params, method_return_value, error_message,
                    feedback_text, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("session_id"),
                    row.get("trace_id"),
                    row.get("origin_function"),
                    row.get("status"),
                    row.get("memory_query"),
                    row.get("memory_context"),
                    json.dumps(row.get("method_params") or {}, ensure_ascii=False),
                    json.dumps(row.get("method_return_value"), ensure_ascii=False),
                    row.get("error_message"),
                    row.get("feedback_text"),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_by_session(self, session_id: str, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, session_id, trace_id, origin_function, status, memory_query,
                       memory_context, method_params, method_return_value, error_message,
                       feedback_text, created_at, metadata
                from session_traces
                where session_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "session_id": row[1],
            "trace_id": row[2],
            "origin_function": row[3],
            "status": row[4],
            "memory_query": row[5] or "",
            "memory_context": row[6] or "",
            "method_params": _json_loads(row[7], {}),
            "method_return_value": _json_loads(row[8], None),
            "error_message": row[9] or "",
            "feedback_text": row[10] or "",
            "created_at": row[11],
            "metadata": _json_loads(row[12], {}),
        }


class SessionSummariesRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into session_summaries(
                    id, session_id, summary_kind, content, status, created_by, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("session_id"),
                    row.get("summary_kind"),
                    row.get("content"),
                    row.get("status") or "active",
                    row.get("created_by"),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_by_session(self, session_id: str, limit: int = 20) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, session_id, summary_kind, content, status, created_by, created_at, metadata
                from session_summaries
                where session_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "session_id": row[1],
            "summary_kind": row[2],
            "content": row[3] or "",
            "status": row[4] or "active",
            "created_by": row[5],
            "created_at": row[6],
            "metadata": _json_loads(row[7], {}),
        }


class SessionModelUsageRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into session_model_usage(
                    id, session_id, model, tokens_in, tokens_out, cost_usd, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("session_id"),
                    row.get("model"),
                    row.get("tokens_in", 0),
                    row.get("tokens_out", 0),
                    row.get("cost_usd", 0),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_by_session(self, session_id: str) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, session_id, model, tokens_in, tokens_out, cost_usd, updated_at, metadata
                from session_model_usage
                where session_id = ?
                order by updated_at desc, rowid desc
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "session_id": row[1],
                "model": row[2],
                "tokens_in": row[3],
                "tokens_out": row[4],
                "cost_usd": row[5],
                "updated_at": row[6],
                "metadata": _json_loads(row[7], {}),
            }
            for row in rows
        ]


class ImprovementTasksRepo:
    _columns = """
        id, cube_id, task_kind, target_domain, target_id, status, priority, reason,
        created_by, claimed_by, created_at, updated_at, finished_at, error_message,
        retry_count, max_retries, next_run_at, claimed_at, claimed_until, worker_id,
        queue_name, last_error, metadata
    """

    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into improvement_tasks(
                    id, cube_id, task_kind, target_domain, target_id, status, priority, reason,
                    created_by, claimed_by, created_at, updated_at, finished_at, error_message,
                    retry_count, max_retries, next_run_at, claimed_at, claimed_until, worker_id,
                    queue_name, last_error, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(task_kind, target_domain, target_id) do update set
                    status=case
                        when improvement_tasks.status in ('done', 'running') then improvement_tasks.status
                        else excluded.status
                    end,
                    priority=min(improvement_tasks.priority, excluded.priority),
                    reason=coalesce(excluded.reason, improvement_tasks.reason),
                    max_retries=excluded.max_retries,
                    next_run_at=excluded.next_run_at,
                    queue_name=excluded.queue_name,
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("cube_id"),
                    row.get("task_kind"),
                    row.get("target_domain"),
                    row.get("target_id"),
                    row.get("status") or "pending",
                    row.get("priority", 50),
                    row.get("reason"),
                    row.get("created_by"),
                    row.get("claimed_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    row.get("finished_at"),
                    row.get("error_message"),
                    row.get("retry_count", 0),
                    row.get("max_retries", 3),
                    row.get("next_run_at"),
                    row.get("claimed_at"),
                    row.get("claimed_until"),
                    row.get("worker_id"),
                    row.get("queue_name") or "default",
                    row.get("last_error"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
            saved = conn.execute(
                f"""
                select {self._columns}
                from improvement_tasks
                where task_kind = ? and target_domain = ? and target_id = ?
                """,
                (row.get("task_kind"), row.get("target_domain"), row.get("target_id")),
            ).fetchone()
        return self._decode(saved)

    def get(self, task_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                f"""
                select {self._columns}
                from improvement_tasks
                where id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def update(self, task_id: str, changes: dict) -> dict | None:
        current = self.get(task_id)
        if not current:
            return None
        updated = {**current, **{key: value for key, value in changes.items() if value is not None}}
        with _conn() as conn:
            conn.execute(
                """
                update improvement_tasks
                set status = ?, priority = ?, reason = ?, claimed_by = ?, updated_at = ?,
                    finished_at = ?, error_message = ?, retry_count = ?, max_retries = ?,
                    next_run_at = ?, claimed_at = ?, claimed_until = ?, worker_id = ?,
                    queue_name = ?, last_error = ?, metadata = ?
                where id = ?
                """,
                (
                    updated.get("status"),
                    updated.get("priority"),
                    updated.get("reason"),
                    updated.get("claimed_by"),
                    updated.get("updated_at"),
                    updated.get("finished_at"),
                    updated.get("error_message"),
                    updated.get("retry_count", 0),
                    updated.get("max_retries", 3),
                    updated.get("next_run_at"),
                    updated.get("claimed_at"),
                    updated.get("claimed_until"),
                    updated.get("worker_id"),
                    updated.get("queue_name") or "default",
                    updated.get("last_error"),
                    json.dumps(updated.get("metadata") or {}, ensure_ascii=False),
                    task_id,
                ),
            )
        return self.get(task_id)

    def claim_next(self, queue_name: str, worker_id: str, now: str, claimed_until: str) -> dict | None:
        with _conn() as conn:
            conn.execute("begin immediate")
            row = conn.execute(
                """
                select id
                from improvement_tasks
                where status = 'pending'
                  and coalesce(queue_name, 'default') = ?
                  and (next_run_at is null or next_run_at <= ?)
                order by priority asc, created_at asc, rowid asc
                limit 1
                """,
                (queue_name, now),
            ).fetchone()
            if not row:
                conn.commit()
                return None
            task_id = row[0]
            conn.execute(
                """
                update improvement_tasks
                set status = 'running', claimed_by = ?, worker_id = ?, claimed_at = ?,
                    claimed_until = ?, updated_at = ?, finished_at = null, error_message = null
                where id = ? and status = 'pending'
                """,
                (worker_id, worker_id, now, claimed_until, now, task_id),
            )
            claimed = conn.execute(
                f"""
                select {self._columns}
                from improvement_tasks
                where id = ?
                """,
                (task_id,),
            ).fetchone()
            conn.commit()
        return self._decode(claimed) if claimed else None

    def release_expired_claims(self, now: str) -> int:
        with _conn() as conn:
            cursor = conn.execute(
                """
                update improvement_tasks
                set status = 'pending', claimed_by = null, worker_id = null,
                    claimed_at = null, claimed_until = null, updated_at = ?
                where status = 'running' and claimed_until is not null and claimed_until <= ?
                """,
                (now, now),
            )
            return cursor.rowcount

    def retry_failed(self, now: str) -> int:
        with _conn() as conn:
            cursor = conn.execute(
                """
                update improvement_tasks
                set status = 'pending', claimed_by = null, worker_id = null,
                    claimed_at = null, claimed_until = null, finished_at = null,
                    error_message = null, updated_at = ?
                where status = 'failed'
                  and retry_count < max_retries
                  and (next_run_at is null or next_run_at <= ?)
                """,
                (now, now),
            )
            return cursor.rowcount

    def list_recent(
        self,
        limit: int = 100,
        status: str | None = None,
        task_kind: str | None = None,
        target_domain: str | None = None,
        target_id: str | None = None,
    ) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if task_kind:
            where.append("task_kind = ?")
            params.append(task_kind)
        if target_domain:
            where.append("target_domain = ?")
            params.append(target_domain)
        if target_id:
            where.append("target_id = ?")
            params.append(target_id)
        query = f"""
            select {self._columns}
            from improvement_tasks
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by priority asc, updated_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def status_counts(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(status, 'pending'), coalesce(task_kind, ''), count(*)
                from improvement_tasks
                group by coalesce(status, 'pending'), coalesce(task_kind, '')
                order by count(*) desc
                """
            ).fetchall()
        return [{"status": row[0], "task_kind": row[1], "count": row[2]} for row in rows]

    def queue_counts(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(queue_name, 'default'), coalesce(status, 'pending'), count(*)
                from improvement_tasks
                group by coalesce(queue_name, 'default'), coalesce(status, 'pending')
                order by coalesce(queue_name, 'default') asc, coalesce(status, 'pending') asc
                """
            ).fetchall()
        return [{"queue_name": row[0], "status": row[1], "count": row[2]} for row in rows]

    def failed_retry_counts_by_queue(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(queue_name, 'default'),
                       case when retry_count < max_retries then 'retryable' else 'exhausted' end,
                       count(*)
                from improvement_tasks
                where status = 'failed'
                group by coalesce(queue_name, 'default'),
                         case when retry_count < max_retries then 'retryable' else 'exhausted' end
                order by coalesce(queue_name, 'default') asc
                """
            ).fetchall()
        return [{"queue_name": row[0], "retry_state": row[1], "count": row[2]} for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "cube_id": row[1],
            "task_kind": row[2],
            "target_domain": row[3],
            "target_id": row[4],
            "status": row[5] or "pending",
            "priority": row[6],
            "reason": row[7],
            "created_by": row[8],
            "claimed_by": row[9],
            "created_at": row[10],
            "updated_at": row[11],
            "finished_at": row[12],
            "error_message": row[13],
            "retry_count": row[14] or 0,
            "max_retries": row[15] if row[15] is not None else 3,
            "next_run_at": row[16],
            "claimed_at": row[17],
            "claimed_until": row[18],
            "worker_id": row[19],
            "queue_name": row[20] or "default",
            "last_error": row[21],
            "metadata": _json_loads(row[22], {}),
        }


class MemoriesRepo:
    def upsert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into memories(
                    id, content, cube_id, tags, user_id, agent_id, session_id, conversation_id,
                    memory_type, context_domain, status, source_kind, trust_level,
                    metadata, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["content"],
                    row.get("cube_id"),
                    ",".join(row.get("tags", [])),
                    row.get("user_id") or "default",
                    row.get("agent_id"),
                    row.get("session_id"),
                    row.get("conversation_id"),
                    row.get("memory_type") or "long_term",
                    row.get("context_domain") or "memory",
                    row.get("status") or "active",
                    row.get("source_kind") or "agent_note",
                    row.get("trust_level") or "verified",
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                    row.get("created_at"),
                    row.get("updated_at"),
                ),
            )

    def get(self, memory_id: str) -> dict | None:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, content, cube_id, tags, user_id, agent_id, session_id, conversation_id,
                       memory_type, context_domain, status, source_kind, trust_level,
                       metadata, created_at, updated_at
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
            select id, content, cube_id, tags, user_id, agent_id, session_id, conversation_id,
                   memory_type, context_domain, status, source_kind, trust_level,
                   metadata, created_at, updated_at
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

    def duplicate_candidates(self, limit: int = 50) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select user_id, coalesce(agent_id, ''), coalesce(session_id, ''),
                       coalesce(conversation_id, ''), memory_type, content,
                       count(*) as duplicate_count,
                       group_concat(id) as ids,
                       min(created_at) as first_created_at,
                       max(updated_at) as last_updated_at
                from memories
                group by user_id, coalesce(agent_id, ''), coalesce(session_id, ''),
                         coalesce(conversation_id, ''), memory_type, content
                having count(*) > 1
                order by duplicate_count desc, last_updated_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "user_id": row[0] or "default",
                "agent_id": row[1] or None,
                "session_id": row[2] or None,
                "conversation_id": row[3] or None,
                "memory_type": row[4] or "long_term",
                "content_preview": (row[5] or "")[:200],
                "duplicate_count": row[6],
                "ids": [item for item in (row[7] or "").split(",") if item],
                "first_created_at": row[8],
                "last_updated_at": row[9],
            }
            for row in rows
        ]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        try:
            metadata = json.loads(row[13] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": row[0],
            "content": row[1],
            "cube_id": row[2],
            "tags": [t for t in (row[3] or "").split(",") if t],
            "user_id": row[4] or "default",
            "agent_id": row[5],
            "session_id": row[6],
            "conversation_id": row[7],
            "memory_type": row[8] or "long_term",
            "context_domain": row[9] or "memory",
            "status": row[10] or "active",
            "source_kind": row[11] or "agent_note",
            "trust_level": row[12] or "verified",
            "metadata": metadata,
            "created_at": row[14],
            "updated_at": row[15],
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


class MemoryEvidenceRepo:
    def insert(self, row: dict) -> None:
        with _conn() as conn:
            conn.execute(
                """
                insert or replace into memory_evidence(
                    id, memory_id, source_domain, source_id, quote, confidence, source_span, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("memory_id"),
                    row.get("source_domain"),
                    row.get("source_id"),
                    row.get("quote"),
                    row.get("confidence", 1.0),
                    json.dumps(row.get("source_span") or {}, ensure_ascii=False),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )

    def list_by_memory(self, memory_id: str, limit: int = 50) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, memory_id, source_domain, source_id, quote, confidence, source_span, created_at, metadata
                from memory_evidence
                where memory_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (memory_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def list_recent(self, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, memory_id, source_domain, source_id, quote, confidence, source_span, created_at, metadata
                from memory_evidence
                order by created_at desc, rowid desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "memory_id": row[1],
            "source_domain": row[2],
            "source_id": row[3],
            "quote": row[4] or "",
            "confidence": row[5],
            "source_span": _json_loads(row[6], {}),
            "created_at": row[7],
            "metadata": _json_loads(row[8], {}),
        }


class MemoryRelationsRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_relations(
                    id, source_domain, source_id, relation_kind, target_domain, target_id,
                    weight, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(source_domain, source_id, relation_kind, target_domain, target_id) do update set
                    weight=excluded.weight,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("source_domain"),
                    row.get("source_id"),
                    row.get("relation_kind"),
                    row.get("target_domain"),
                    row.get("target_id"),
                    row.get("weight", 1.0),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return row

    def list_by_source(self, source_domain: str = "memory", source_id: str | None = None, limit: int = 100) -> list[dict]:
        where = ["source_domain = ?"]
        params: list[str | int] = [source_domain]
        if source_id:
            where.append("source_id = ?")
            params.append(source_id)
        query = """
            select id, source_domain, source_id, relation_kind, target_domain, target_id,
                   weight, created_at, metadata
            from memory_relations
            where {where}
            order by weight desc, rowid desc
            limit ?
        """.format(where=" and ".join(where))
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def count_by_kind(self, source_domain: str = "memory") -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select relation_kind, count(*)
                from memory_relations
                where source_domain = ?
                group by relation_kind
                order by count(*) desc, relation_kind asc
                """,
                (source_domain,),
            ).fetchall()
        return [{"relation_kind": row[0], "count": row[1]} for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "source_domain": row[1],
            "source_id": row[2],
            "relation_kind": row[3],
            "target_domain": row[4],
            "target_id": row[5],
            "weight": row[6],
            "created_at": row[7],
            "metadata": _json_loads(row[8], {}),
        }


class MemoryLifecycleEventsRepo:
    def insert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_lifecycle_events(
                    id, memory_id, from_status, to_status, event_kind, actor, created_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row.get("memory_id"),
                    row.get("from_status"),
                    row.get("to_status"),
                    row.get("event_kind"),
                    row.get("actor"),
                    row.get("created_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, event_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, memory_id, from_status, to_status, event_kind, actor, created_at, metadata
                from memory_lifecycle_events
                where id = ?
                """,
                (event_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_by_memory(self, memory_id: str, limit: int = 50) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, memory_id, from_status, to_status, event_kind, actor, created_at, metadata
                from memory_lifecycle_events
                where memory_id = ?
                order by created_at desc, rowid desc
                limit ?
                """,
                (memory_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def list_recent(self, limit: int = 100, event_kind: str | None = None) -> list[dict]:
        params: list[str | int] = []
        query = """
            select id, memory_id, from_status, to_status, event_kind, actor, created_at, metadata
            from memory_lifecycle_events
        """
        if event_kind:
            query += " where event_kind = ?"
            params.append(event_kind)
        query += " order by created_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "memory_id": row[1],
            "from_status": row[2],
            "to_status": row[3],
            "event_kind": row[4],
            "actor": row[5],
            "created_at": row[6],
            "metadata": _json_loads(row[7], {}),
        }


class MemoryCandidatesRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_candidates(
                    id, cube_id, source_domain, source_id, content, content_kind, tags,
                    status, confidence, provenance, evidence, created_by, created_at, updated_at,
                    promoted_memory_id, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    cube_id=excluded.cube_id,
                    source_domain=excluded.source_domain,
                    source_id=excluded.source_id,
                    content=excluded.content,
                    content_kind=excluded.content_kind,
                    tags=excluded.tags,
                    status=excluded.status,
                    confidence=excluded.confidence,
                    provenance=excluded.provenance,
                    evidence=excluded.evidence,
                    updated_at=excluded.updated_at,
                    promoted_memory_id=coalesce(excluded.promoted_memory_id, memory_candidates.promoted_memory_id),
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("cube_id"),
                    row.get("source_domain"),
                    row.get("source_id"),
                    row.get("content"),
                    row.get("content_kind") or "note",
                    ",".join(row.get("tags") or []),
                    row.get("status") or "candidate",
                    row.get("confidence", 1.0),
                    json.dumps(row.get("provenance") or {}, ensure_ascii=False),
                    json.dumps(row.get("evidence") or [], ensure_ascii=False),
                    row.get("created_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    row.get("promoted_memory_id"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, candidate_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, cube_id, source_domain, source_id, content, content_kind, tags,
                       status, confidence, provenance, evidence, created_by, created_at, updated_at,
                       promoted_memory_id, metadata
                from memory_candidates
                where id = ?
                """,
                (candidate_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(self, limit: int = 100, status: str | None = None, source_domain: str | None = None) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if source_domain:
            where.append("source_domain = ?")
            params.append(source_domain)
        query = """
            select id, cube_id, source_domain, source_id, content, content_kind, tags,
                   status, confidence, provenance, evidence, created_by, created_at, updated_at,
                   promoted_memory_id, metadata
            from memory_candidates
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by created_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "cube_id": row[1],
            "source_domain": row[2],
            "source_id": row[3],
            "content": row[4] or "",
            "content_kind": row[5] or "note",
            "tags": [tag for tag in (row[6] or "").split(",") if tag],
            "status": row[7] or "candidate",
            "confidence": row[8],
            "provenance": _json_loads(row[9], {}),
            "evidence": _json_loads(row[10], []),
            "created_by": row[11],
            "created_at": row[12],
            "updated_at": row[13],
            "promoted_memory_id": row[14],
            "metadata": _json_loads(row[15], {}),
        }


class MemoryFeedbackRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_feedback(
                    id, cube_id, feedback_text, target_memory_id, status, created_by, created_at, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    cube_id=excluded.cube_id,
                    feedback_text=excluded.feedback_text,
                    target_memory_id=excluded.target_memory_id,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("cube_id"),
                    row.get("feedback_text"),
                    row.get("target_memory_id"),
                    row.get("status") or "pending",
                    row.get("created_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, feedback_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, cube_id, feedback_text, target_memory_id, status, created_by, created_at, updated_at, metadata
                from memory_feedback
                where id = ?
                """,
                (feedback_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(self, limit: int = 100, status: str | None = None, target_memory_id: str | None = None) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if target_memory_id:
            where.append("target_memory_id = ?")
            params.append(target_memory_id)
        query = """
            select id, cube_id, feedback_text, target_memory_id, status, created_by, created_at, updated_at, metadata
            from memory_feedback
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by created_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "cube_id": row[1],
            "feedback_text": row[2],
            "target_memory_id": row[3],
            "status": row[4] or "pending",
            "created_by": row[5],
            "created_at": row[6],
            "updated_at": row[7],
            "metadata": _json_loads(row[8], {}),
        }


class MemoryFeedbackActionsRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_feedback_actions(
                    id, feedback_id, action_type, target_memory_id, payload, status, applied_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    action_type=excluded.action_type,
                    target_memory_id=excluded.target_memory_id,
                    payload=excluded.payload,
                    status=excluded.status,
                    applied_at=excluded.applied_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("feedback_id"),
                    row.get("action_type"),
                    row.get("target_memory_id"),
                    json.dumps(row.get("payload") or {}, ensure_ascii=False),
                    row.get("status") or "pending",
                    row.get("applied_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, action_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, feedback_id, action_type, target_memory_id, payload, status, applied_at, metadata
                from memory_feedback_actions
                where id = ?
                """,
                (action_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_by_feedback(self, feedback_id: str, limit: int = 100) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select id, feedback_id, action_type, target_memory_id, payload, status, applied_at, metadata
                from memory_feedback_actions
                where feedback_id = ?
                order by rowid asc
                limit ?
                """,
                (feedback_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "feedback_id": row[1],
            "action_type": row[2],
            "target_memory_id": row[3],
            "payload": _json_loads(row[4], {}),
            "status": row[5] or "pending",
            "applied_at": row[6],
            "metadata": _json_loads(row[7], {}),
        }


class HookSubscriptionsRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into hook_subscriptions(
                    id, hook_name, target_kind, target_ref, status, created_by, created_at, updated_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    hook_name=excluded.hook_name,
                    target_kind=excluded.target_kind,
                    target_ref=excluded.target_ref,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("hook_name"),
                    row.get("target_kind") or "queue",
                    row.get("target_ref"),
                    row.get("status") or "active",
                    row.get("created_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, subscription_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, hook_name, target_kind, target_ref, status, created_by, created_at, updated_at, metadata
                from hook_subscriptions
                where id = ?
                """,
                (subscription_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def first_active_for_hook(self, hook_name: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, hook_name, target_kind, target_ref, status, created_by, created_at, updated_at, metadata
                from hook_subscriptions
                where hook_name = ? and status = 'active'
                order by created_at asc, rowid asc
                limit 1
                """,
                (hook_name,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(self, limit: int = 100, hook_name: str | None = None, status: str | None = None) -> list[dict]:
        where = []
        params: list[str | int] = []
        if hook_name:
            where.append("hook_name = ?")
            params.append(hook_name)
        if status:
            where.append("status = ?")
            params.append(status)
        query = """
            select id, hook_name, target_kind, target_ref, status, created_by, created_at, updated_at, metadata
            from hook_subscriptions
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by created_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "hook_name": row[1],
            "target_kind": row[2] or "queue",
            "target_ref": row[3],
            "status": row[4] or "active",
            "created_by": row[5],
            "created_at": row[6],
            "updated_at": row[7],
            "metadata": _json_loads(row[8], {}),
        }


class HookEventsRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into hook_events(
                    id, hook_name, subscription_id, source_kind, source_id, payload, status, created_at, dispatched_at, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    hook_name=excluded.hook_name,
                    subscription_id=excluded.subscription_id,
                    source_kind=excluded.source_kind,
                    source_id=excluded.source_id,
                    payload=excluded.payload,
                    status=excluded.status,
                    dispatched_at=excluded.dispatched_at,
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("hook_name"),
                    row.get("subscription_id"),
                    row.get("source_kind") or "manual",
                    row.get("source_id"),
                    json.dumps(row.get("payload") or {}, ensure_ascii=False),
                    row.get("status") or "queued",
                    row.get("created_at"),
                    row.get("dispatched_at"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, event_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, hook_name, subscription_id, source_kind, source_id, payload, status, created_at, dispatched_at, metadata
                from hook_events
                where id = ?
                """,
                (event_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(self, limit: int = 100, hook_name: str | None = None, status: str | None = None) -> list[dict]:
        where = []
        params: list[str | int] = []
        if hook_name:
            where.append("hook_name = ?")
            params.append(hook_name)
        if status:
            where.append("status = ?")
            params.append(status)
        query = """
            select id, hook_name, subscription_id, source_kind, source_id, payload, status, created_at, dispatched_at, metadata
            from hook_events
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by created_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "hook_name": row[1],
            "subscription_id": row[2],
            "source_kind": row[3] or "manual",
            "source_id": row[4],
            "payload": _json_loads(row[5], {}),
            "status": row[6] or "queued",
            "created_at": row[7],
            "dispatched_at": row[8],
            "metadata": _json_loads(row[9], {}),
        }


class MemoryPromotionProposalsRepo:
    def upsert(self, row: dict) -> dict:
        with _conn() as conn:
            conn.execute(
                """
                insert into memory_promotion_proposals(
                    id, source_session_id, source_event_ids, proposed_content, cube_id, tags,
                    memory_type, user_id, agent_id, project_path, status, reason,
                    created_by, reviewed_by, created_at, updated_at, reviewed_at,
                    promoted_memory_id, metadata
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    proposed_content=coalesce(excluded.proposed_content, memory_promotion_proposals.proposed_content),
                    cube_id=coalesce(excluded.cube_id, memory_promotion_proposals.cube_id),
                    tags=coalesce(excluded.tags, memory_promotion_proposals.tags),
                    memory_type=coalesce(excluded.memory_type, memory_promotion_proposals.memory_type),
                    status=coalesce(excluded.status, memory_promotion_proposals.status),
                    reason=coalesce(excluded.reason, memory_promotion_proposals.reason),
                    reviewed_by=coalesce(excluded.reviewed_by, memory_promotion_proposals.reviewed_by),
                    updated_at=excluded.updated_at,
                    reviewed_at=coalesce(excluded.reviewed_at, memory_promotion_proposals.reviewed_at),
                    promoted_memory_id=coalesce(excluded.promoted_memory_id, memory_promotion_proposals.promoted_memory_id),
                    metadata=excluded.metadata
                """,
                (
                    row["id"],
                    row.get("source_session_id"),
                    json.dumps(row.get("source_event_ids") or [], ensure_ascii=False),
                    row.get("proposed_content"),
                    row.get("cube_id"),
                    ",".join(row.get("tags", [])),
                    row.get("memory_type") or "long_term",
                    row.get("user_id") or "default",
                    row.get("agent_id"),
                    row.get("project_path"),
                    row.get("status") or "pending",
                    row.get("reason"),
                    row.get("created_by"),
                    row.get("reviewed_by"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    row.get("reviewed_at"),
                    row.get("promoted_memory_id"),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        return self.get(row["id"])

    def get(self, proposal_id: str) -> dict | None:
        with _conn() as conn:
            row = conn.execute(
                """
                select id, source_session_id, source_event_ids, proposed_content, cube_id, tags,
                       memory_type, user_id, agent_id, project_path, status, reason,
                       created_by, reviewed_by, created_at, updated_at, reviewed_at,
                       promoted_memory_id, metadata
                from memory_promotion_proposals
                where id = ?
                """,
                (proposal_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def list_recent(self, limit: int = 100, status: str | None = None, source_session_id: str | None = None) -> list[dict]:
        where = []
        params: list[str | int] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if source_session_id:
            where.append("source_session_id = ?")
            params.append(source_session_id)
        query = """
            select id, source_session_id, source_event_ids, proposed_content, cube_id, tags,
                   memory_type, user_id, agent_id, project_path, status, reason,
                   created_by, reviewed_by, created_at, updated_at, reviewed_at,
                   promoted_memory_id, metadata
            from memory_promotion_proposals
        """
        if where:
            query += " where " + " and ".join(where)
        query += " order by updated_at desc, rowid desc limit ?"
        params.append(limit)
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode(row) for row in rows]

    def status_counts(self) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(status, 'pending'), coalesce(memory_type, 'long_term'), count(*)
                from memory_promotion_proposals
                group by coalesce(status, 'pending'), coalesce(memory_type, 'long_term')
                order by count(*) desc
                """
            ).fetchall()
        return [{"status": row[0], "memory_type": row[1], "count": row[2]} for row in rows]

    def _decode(self, row: sqlite3.Row | tuple) -> dict:
        return {
            "id": row[0],
            "source_session_id": row[1],
            "source_event_ids": _json_loads(row[2], []),
            "proposed_content": row[3] or "",
            "cube_id": row[4],
            "tags": [tag for tag in (row[5] or "").split(",") if tag],
            "memory_type": row[6] or "long_term",
            "user_id": row[7] or "default",
            "agent_id": row[8],
            "project_path": row[9],
            "status": row[10] or "pending",
            "reason": row[11] or "",
            "created_by": row[12],
            "reviewed_by": row[13],
            "created_at": row[14],
            "updated_at": row[15],
            "reviewed_at": row[16],
            "promoted_memory_id": row[17],
            "metadata": _json_loads(row[18], {}),
        }


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

    def action_counts(self, limit: int = 20) -> list[dict]:
        with _conn() as conn:
            rows = conn.execute(
                """
                select coalesce(action, ''), count(*)
                from audit_logs
                group by coalesce(action, '')
                order by count(*) desc, coalesce(action, '') asc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [{"action": r[0], "count": r[1]} for r in rows]


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


def context_cubes_repo() -> ContextCubesRepo:
    return ContextCubesRepo()


def cube_bindings_repo() -> CubeBindingsRepo:
    return CubeBindingsRepo()


def documents_repo() -> DocumentsRepo:
    return DocumentsRepo()


def chunks_repo() -> ChunksRepo:
    return ChunksRepo()


def file_references_repo() -> FileReferencesRepo:
    return FileReferencesRepo()


def assets_repo() -> AssetsRepo:
    return AssetsRepo()


def asset_locations_repo() -> AssetLocationsRepo:
    return AssetLocationsRepo()


def asset_versions_repo() -> AssetVersionsRepo:
    return AssetVersionsRepo()


def asset_artifacts_repo() -> AssetArtifactsRepo:
    return AssetArtifactsRepo()


def asset_scan_runs_repo() -> AssetScanRunsRepo:
    return AssetScanRunsRepo()


def agent_sessions_repo() -> AgentSessionsRepo:
    return AgentSessionsRepo()


def session_events_repo() -> SessionEventsRepo:
    return SessionEventsRepo()


def session_traces_repo() -> SessionTracesRepo:
    return SessionTracesRepo()


def session_summaries_repo() -> SessionSummariesRepo:
    return SessionSummariesRepo()


def session_model_usage_repo() -> SessionModelUsageRepo:
    return SessionModelUsageRepo()


def improvement_tasks_repo() -> ImprovementTasksRepo:
    return ImprovementTasksRepo()


def memories_repo() -> MemoriesRepo:
    return MemoriesRepo()


def memory_versions_repo() -> MemoryVersionsRepo:
    return MemoryVersionsRepo()


def memory_evidence_repo() -> MemoryEvidenceRepo:
    return MemoryEvidenceRepo()


def memory_relations_repo() -> MemoryRelationsRepo:
    return MemoryRelationsRepo()


def memory_lifecycle_events_repo() -> MemoryLifecycleEventsRepo:
    return MemoryLifecycleEventsRepo()


def memory_candidates_repo() -> MemoryCandidatesRepo:
    return MemoryCandidatesRepo()


def memory_feedback_repo() -> MemoryFeedbackRepo:
    return MemoryFeedbackRepo()


def memory_feedback_actions_repo() -> MemoryFeedbackActionsRepo:
    return MemoryFeedbackActionsRepo()


def hook_subscriptions_repo() -> HookSubscriptionsRepo:
    return HookSubscriptionsRepo()


def hook_events_repo() -> HookEventsRepo:
    return HookEventsRepo()


def memory_promotion_proposals_repo() -> MemoryPromotionProposalsRepo:
    return MemoryPromotionProposalsRepo()


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
