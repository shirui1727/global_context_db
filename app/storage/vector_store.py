from pathlib import Path
import json

import lancedb
import numpy as np

from app.retrieval.embedding import embed_text

_db = None
_table = "context_items"


def init_vector_store(path: Path) -> None:
    global _db
    _db = lancedb.connect(str(path))
    if _table not in _db.table_names():
        seed = {
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
            "metadata": "{}",
        }
        _db.create_table(_table, data=[seed], mode="overwrite")


def _table_obj():
    if _db is None:
        raise RuntimeError("Vector store not initialized")
    return _db.open_table(_table)


def _normalize_row(row: dict) -> dict:
    normalized = dict(row)
    if isinstance(normalized.get("tags"), list):
        normalized["tags"] = ",".join(str(item) for item in normalized["tags"] if item is not None)
    if isinstance(normalized.get("metadata"), (dict, list)):
        normalized["metadata"] = json.dumps(normalized["metadata"], ensure_ascii=False)
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


def search_items(query: str, top_k: int, kind: str | None = None) -> list[dict]:
    table = _table_obj()
    qv = embed_text(query).tolist()
    results = table.search(qv).limit(max(top_k * 5, top_k)).to_list()
    if kind:
        results = [r for r in results if r.get("kind") == kind]
    results = [r for r in results if r.get("kind") != "seed"]
    return results[:top_k]
