from pathlib import Path

from app.assets.service import permission_policy
from app.core.config import settings
from app.memory.service import list_audit_logs, memory_quality_report
from app.memory.graph_service import memory_relation_index_summary
from app.storage.repo import (
    agent_sessions_repo,
    assets_repo,
    audit_logs_repo,
    db_counts,
    failed_operations,
    file_references_repo,
    improvement_tasks_repo,
    memory_promotion_proposals_repo,
    memories_repo,
    sqlite_path,
)


HIGH_RISK_WRITE_ACTIONS = {
    "mcp.high_risk_write",
    "memory.deleted",
    "memory.updated",
    "memory_promotion.promoted",
    "memory_feedback.applied",
}


def _path_state(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def diagnostics() -> dict:
    counts = db_counts()
    promotion_status_counts = memory_promotion_proposals_repo().status_counts()
    pending_promotion_count = sum(
        item["count"] for item in promotion_status_counts if item.get("status") in {"pending", "approved"}
    )
    write_action_counts = [
        item
        for item in audit_logs_repo().action_counts(limit=50)
        if item.get("action") and not item["action"].startswith(("diagnostics.", "search.", "recall."))
    ]
    write_action_count = sum(item["count"] for item in write_action_counts)
    high_risk_write_action_count = sum(
        item["count"] for item in write_action_counts if item.get("action") in HIGH_RISK_WRITE_ACTIONS
    )
    improvement_queue_counts = improvement_tasks_repo().queue_counts()
    pending_by_queue = {item["queue_name"]: item["count"] for item in improvement_queue_counts if item["status"] == "pending"}
    failed_by_queue = {item["queue_name"]: item["count"] for item in improvement_queue_counts if item["status"] == "failed"}
    failed_retry_counts = improvement_tasks_repo().failed_retry_counts_by_queue()
    retryable_failed_by_queue = {item["queue_name"]: item["count"] for item in failed_retry_counts if item["retry_state"] == "retryable"}
    exhausted_failed_by_queue = {item["queue_name"]: item["count"] for item in failed_retry_counts if item["retry_state"] == "exhausted"}
    oldest_pending_rows = improvement_tasks_repo().oldest_pending_by_queue()
    oldest_pending_by_queue = {item["queue_name"]: item["oldest_pending_at"] for item in oldest_pending_rows}
    queue_names = sorted({item["queue_name"] for item in improvement_queue_counts} | set(oldest_pending_by_queue))
    queue_health = [
        {
            "queue_name": queue_name,
            "pending_count": pending_by_queue.get(queue_name, 0),
            "failed_count": failed_by_queue.get(queue_name, 0),
            "retryable_failed_count": retryable_failed_by_queue.get(queue_name, 0),
            "exhausted_failed_count": exhausted_failed_by_queue.get(queue_name, 0),
            "oldest_pending_at": oldest_pending_by_queue.get(queue_name),
        }
        for queue_name in queue_names
    ]
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
                "relation_index": memory_relation_index_summary(sample_limit=20),
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
                "queue_counts": improvement_queue_counts,
                "pending_by_queue": pending_by_queue,
                "failed_by_queue": failed_by_queue,
                "failed_retry_counts": failed_retry_counts,
                "retryable_failed_by_queue": retryable_failed_by_queue,
                "exhausted_failed_by_queue": exhausted_failed_by_queue,
                "oldest_pending_by_queue": oldest_pending_by_queue,
                "queue_health": queue_health,
                "pending_promotion_count": pending_promotion_count,
            },
            "audit": {
                "domain": "audit",
                "write_action_count": write_action_count,
                "high_risk_write_action_count": high_risk_write_action_count,
                "high_risk_actions": sorted(HIGH_RISK_WRITE_ACTIONS),
                "write_action_counts": write_action_counts,
            },
            "recent_audit_logs": list_audit_logs(limit=10),
            "recent_failures": failed_operations(limit=20),
        },
    }
