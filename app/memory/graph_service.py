from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from itertools import combinations
from typing import Any

from app.storage.repo import memories_repo, memory_evidence_repo, memory_relations_repo


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _relation_id(source_domain: str, source_id: str, relation_kind: str, target_domain: str, target_id: str) -> str:
    return sha256(f"{source_domain}:{source_id}:{relation_kind}:{target_domain}:{target_id}".encode("utf-8")).hexdigest()


def _upsert_relation(
    source_domain: str,
    source_id: str,
    relation_kind: str,
    target_domain: str,
    target_id: str,
    weight: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> dict:
    return memory_relations_repo().upsert(
        {
            "id": _relation_id(source_domain, source_id, relation_kind, target_domain, target_id),
            "source_domain": source_domain,
            "source_id": source_id,
            "relation_kind": relation_kind,
            "target_domain": target_domain,
            "target_id": target_id,
            "weight": weight,
            "created_at": _now(),
            "metadata": metadata or {},
        }
    )


def build_memory_relation_index(limit: int = 500, created_by: str | None = None) -> dict:
    memories = memories_repo().list_all(limit=limit)
    created = []

    tag_buckets: dict[tuple[str | None, str], list[dict]] = {}
    for memory in memories:
        for tag in memory.get("tags") or []:
            tag_buckets.setdefault((memory.get("cube_id"), tag), []).append(memory)

    for (cube_id, tag), bucket in tag_buckets.items():
        if len(bucket) < 2:
            continue
        for left, right in combinations(bucket[:30], 2):
            metadata = {"tag": tag, "cube_id": cube_id, "created_by": created_by or "memory_graph"}
            created.append(_upsert_relation("memory", left["id"], "shared_tag", "memory", right["id"], 0.6, metadata))
            created.append(_upsert_relation("memory", right["id"], "shared_tag", "memory", left["id"], 0.6, metadata))

    for evidence in memory_evidence_repo().list_recent(limit=limit):
        created.append(
            _upsert_relation(
                "memory",
                evidence["memory_id"],
                "supported_by",
                evidence["source_domain"],
                evidence["source_id"],
                float(evidence.get("confidence") or 1.0),
                {"evidence_id": evidence["id"], "created_by": created_by or "memory_graph"},
            )
        )

    return {"created_count": len(created), "relations": created}


def list_memory_relations(source_id: str | None = None, limit: int = 100) -> list[dict]:
    return memory_relations_repo().list_by_source(source_domain="memory", source_id=source_id, limit=limit)
