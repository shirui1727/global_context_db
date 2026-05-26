from pathlib import Path
import json

import lancedb
import numpy as np

from app.retrieval.embedding import embed_text

_db = None
_table = "context_items"
_required_columns = {
    "id",
    "kind",
    "text",
    "vector",
    "source",
    "doc_id",
    "chunk_index",
    "tags",
    "user_id",
    "agent_id",
    "session_id",
    "conversation_id",
    "memory_type",
    "context_domain",
    "status",
    "source_kind",
    "trust_level",
    "asset_id",
    "version_id",
    "artifact_id",
    "analysis_status",
    "metadata",
}


def _seed_row() -> dict:
    return {
        "id": "seed",
        "kind": "seed",
        "text": "seed",
        "vector": [0.0] * 64,
        "source": "",
        "doc_id": "",
        "chunk_index": 0,
        "tags": "",
        "user_id": "",
        "agent_id": "",
        "session_id": "",
        "conversation_id": "",
        "memory_type": "",
        "context_domain": "",
        "status": "",
        "source_kind": "",
        "trust_level": "",
        "asset_id": "",
        "version_id": "",
        "artifact_id": "",
        "analysis_status": "",
        "metadata": "{}",
    }


def init_vector_store(path: Path) -> None:
    global _db
    _db = lancedb.connect(str(path))
    if _table not in _db.table_names():
        _db.create_table(_table, data=[_seed_row()], mode="overwrite")
        return
    _ensure_vector_schema()


def _ensure_vector_schema() -> None:
    table = _db.open_table(_table)
    schema_names = {field.name for field in table.schema}
    if _required_columns.issubset(schema_names):
        return
    rows = _table_rows(table)
    if not rows:
        rows = [_seed_row()]
    normalized = [_normalize_row(row) for row in rows]
    if not any(row.get("id") == "seed" for row in normalized):
        normalized.append(_seed_row())
    _db.create_table(_table, data=normalized, mode="overwrite")


def _table_rows(table) -> list[dict]:
    if hasattr(table, "to_list"):
        return table.to_list()
    if hasattr(table, "to_arrow"):
        return table.to_arrow().to_pylist()
    if hasattr(table, "to_pandas"):
        return table.to_pandas().to_dict(orient="records")
    raise RuntimeError("LanceDB table does not support row export for schema migration")


def _table_obj():
    if _db is None:
        raise RuntimeError("Vector store not initialized")
    return _db.open_table(_table)


def _normalize_row(row: dict) -> dict:
    normalized = {
        "id": "",
        "kind": "",
        "text": "",
        "vector": [0.0] * 64,
        "source": "",
        "doc_id": "",
        "chunk_index": 0,
        "tags": "",
        "user_id": "",
        "agent_id": "",
        "session_id": "",
        "conversation_id": "",
        "memory_type": "",
        "context_domain": "",
        "status": "",
        "source_kind": "",
        "trust_level": "",
        "asset_id": "",
        "version_id": "",
        "artifact_id": "",
        "analysis_status": "",
        "metadata": "{}",
        **row,
    }
    if isinstance(normalized.get("tags"), list):
        normalized["tags"] = ",".join(str(item) for item in normalized["tags"] if item is not None)
    if isinstance(normalized.get("metadata"), (dict, list)):
        normalized["metadata"] = json.dumps(normalized["metadata"], ensure_ascii=False)
    for key in (
        "id",
        "kind",
        "text",
        "source",
        "doc_id",
        "tags",
        "user_id",
        "agent_id",
        "session_id",
        "conversation_id",
        "memory_type",
        "context_domain",
        "status",
        "source_kind",
        "trust_level",
        "asset_id",
        "version_id",
        "artifact_id",
        "analysis_status",
        "metadata",
    ):
        if normalized.get(key) is None:
            normalized[key] = ""
        else:
            normalized[key] = str(normalized[key])
    if normalized.get("chunk_index") is None:
        normalized["chunk_index"] = 0
    return normalized


def upsert_items(rows: list[dict]) -> None:
    table = _table_obj()
    for row in rows:
        normalized = _normalize_row(row)
        item_id = str(normalized.get("id", "")).replace("'", "''")
        if item_id:
            table.delete(f"id = '{item_id}'")
    table.add([_normalize_row(row) for row in rows])


def delete_item(item_id: str) -> None:
    table = _table_obj()
    safe_id = item_id.replace("'", "''")
    table.delete(f"id = '{safe_id}'")


def delete_items_by_kind(kind: str) -> None:
    table = _table_obj()
    safe_kind = kind.replace("'", "''")
    table.delete(f"kind = '{safe_kind}'")


def list_items(kind: str | None = None) -> list[dict]:
    table = _table_obj()
    rows = _table_rows(table)
    if kind:
        rows = [row for row in rows if row.get("kind") == kind]
    return [row for row in rows if row.get("kind") != "seed"]


def search_items(
    query: str,
    top_k: int,
    kind: str | None = None,
    context_domain: str | None = None,
) -> list[dict]:
    table = _table_obj()
    qv = embed_text(query).tolist()
    results = table.search(qv).limit(max(top_k * 5, top_k)).to_list()
    if kind:
        results = [r for r in results if r.get("kind") == kind]
    if context_domain:
        results = [r for r in results if r.get("context_domain") == context_domain]
    results = [r for r in results if r.get("kind") != "seed"]
    return results[:top_k]
