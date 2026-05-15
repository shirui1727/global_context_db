from hashlib import sha256
from datetime import datetime, timezone
import json

from app.core.schemas import MemoryCreate, MemoryUpdate
from app.retrieval.embedding import embed_text
from app.storage.repo import memories_repo
from app.storage.vector_store import delete_item, search_items, upsert_items


def add_memory(payload: MemoryCreate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    memory_id = sha256(
        "|".join(
            [
                payload.user_id,
                payload.agent_id or "",
                payload.session_id or "",
                payload.conversation_id or "",
                payload.memory_type,
                payload.content,
            ]
        ).encode("utf-8")
    ).hexdigest()
    row = {
        "id": memory_id,
        "content": payload.content,
        "tags": payload.tags,
        "user_id": payload.user_id,
        "agent_id": payload.agent_id,
        "session_id": payload.session_id,
        "conversation_id": payload.conversation_id,
        "memory_type": payload.memory_type,
        "metadata": payload.metadata,
        "created_at": now,
        "updated_at": now,
    }
    memories_repo().upsert(row)
    upsert_items(
        [
            {
                "id": memory_id,
                "kind": "memory",
                "text": payload.content,
                "vector": embed_text(payload.content).tolist(),
                "tags": payload.tags,
                "user_id": payload.user_id,
                "agent_id": payload.agent_id,
                "session_id": payload.session_id,
                "conversation_id": payload.conversation_id,
                "memory_type": payload.memory_type,
                "metadata": payload.metadata,
            }
        ]
    )
    return {"memory_id": memory_id, "memory": memories_repo().get(memory_id)}


def _decode_metadata(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def search_memory(
    query: str,
    top_k: int = 5,
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
) -> dict:
    results = search_items(query, max(top_k * 5, top_k), kind="memory")
    cleaned = []
    for row in results:
        if user_id and row.get("user_id") != user_id:
            continue
        if agent_id and row.get("agent_id") != agent_id:
            continue
        if memory_type and row.get("memory_type") != memory_type:
            continue
        cleaned.append(
            {
                "id": row.get("id"),
                "kind": row.get("kind"),
                "text": row.get("text"),
                "tags": row.get("tags"),
                "user_id": row.get("user_id"),
                "agent_id": row.get("agent_id"),
                "session_id": row.get("session_id"),
                "conversation_id": row.get("conversation_id"),
                "memory_type": row.get("memory_type"),
                "metadata": _decode_metadata(row.get("metadata")),
                "score": float(1.0 / (1.0 + max(row.get("_distance", 0.0), 0.0))),
            }
        )
    return {"results": cleaned[:top_k]}


def list_memories(user_id: str | None = None, agent_id: str | None = None, memory_type: str | None = None, limit: int = 100) -> list[dict]:
    return memories_repo().list_all(user_id=user_id, agent_id=agent_id, memory_type=memory_type, limit=limit)


def update_memory(memory_id: str, payload: MemoryUpdate) -> dict:
    current = memories_repo().get(memory_id)
    if current is None:
        raise ValueError("memory not found")
    updated = {
        **current,
        **{k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    memories_repo().upsert(updated)
    delete_item(memory_id)
    upsert_items(
        [
            {
                "id": memory_id,
                "kind": "memory",
                "text": updated["content"],
                "vector": embed_text(updated["content"]).tolist(),
                "tags": updated.get("tags", []),
                "user_id": updated.get("user_id", "default"),
                "agent_id": updated.get("agent_id"),
                "session_id": updated.get("session_id"),
                "conversation_id": updated.get("conversation_id"),
                "memory_type": updated.get("memory_type", "long_term"),
                "metadata": updated.get("metadata", {}),
            }
        ]
    )
    return {"memory_id": memory_id, "memory": memories_repo().get(memory_id)}


def delete_memory(memory_id: str) -> dict:
    existed = memories_repo().delete(memory_id)
    delete_item(memory_id)
    return {"deleted": existed, "memory_id": memory_id}
