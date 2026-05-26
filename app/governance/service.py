from pathlib import Path

from app.assets.service import permission_policy
from app.core.config import settings
from app.memory.service import list_audit_logs, memory_quality_report
from app.storage.repo import (
    agent_sessions_repo,
    assets_repo,
    db_counts,
    failed_operations,
    file_references_repo,
    improvement_tasks_repo,
    memory_promotion_proposals_repo,
    memories_repo,
    sqlite_path,
)


def _path_state(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def diagnostics() -> dict:
    counts = db_counts()
    return {
        "ok": True,
        "service": settings.service_name,
        "version": settings.service_version,
        "data_dir": str(settings.data_dir),
        "sqlite": _path_state(sqlite_path()),
        "lancedb": {
            "path": str(settings.lancedb_dir),
            "exists": settings.lancedb_dir.exists(),
        },
        "artifacts": {
            "path": str(settings.data_dir / "artifacts"),
            "exists": (settings.data_dir / "artifacts").exists(),
        },
        "counts": counts,
        "governance": {
            "memory": {
                "domain": "memory",
                "dedup_rule": "sha256(user_id, agent_id, session_id, conversation_id, memory_type, content)",
                "duplicate_candidates": memories_repo().duplicate_candidates(limit=20),
                "promotion_status_counts": memory_promotion_proposals_repo().status_counts(),
                "quality": memory_quality_report(limit=20),
            },
            "asset": {
                "domain": "asset",
                "identity_rule": "asset_key if provided, else checksum if provided, else sha256(uri)",
                "uri_rule": "asset identity is separate from physical locations",
                "permission_policy": permission_policy(),
                "status_counts": assets_repo().status_counts(),
                "legacy_file_reference_status_counts": file_references_repo().status_counts(),
                "duplicate_candidates": file_references_repo().duplicate_assets(limit=20),
            },
            "session": {
                "domain": "session",
                "purpose": "short-lived agent process history for deterministic resume context",
                "status_counts": agent_sessions_repo().status_counts(),
            },
            "improvement": {
                "domain": "improvement",
                "purpose": "deterministic task queue for rebuild, reindex, recovery, and promotion work",
                "status_counts": improvement_tasks_repo().status_counts(),
            },
            "recent_audit_logs": list_audit_logs(limit=10),
            "recent_failures": failed_operations(limit=20),
        },
    }
