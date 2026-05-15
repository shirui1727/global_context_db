from pathlib import Path

from app.core.config import settings
from app.memory.service import list_audit_logs
from app.storage.repo import db_counts, failed_operations, memories_repo, sqlite_path


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
            "dedup_rule": "sha256(user_id, agent_id, session_id, conversation_id, memory_type, content)",
            "duplicate_candidates": memories_repo().duplicate_candidates(limit=20),
            "recent_audit_logs": list_audit_logs(limit=10),
            "recent_failures": failed_operations(limit=20),
        },
    }
