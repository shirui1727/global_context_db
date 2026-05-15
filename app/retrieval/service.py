from app.retrieval.embedding import embed_text
from app.storage.vector_store import search_items


def search_context(query: str, top_k: int = 5) -> dict:
    results = search_items(query, top_k)
    cleaned = []
    for row in results:
        cleaned.append(
            {
                "id": row.get("id"),
                "kind": row.get("kind"),
                "text": row.get("text"),
                "source": row.get("source"),
                "doc_id": row.get("doc_id"),
                "chunk_index": row.get("chunk_index"),
                "tags": row.get("tags"),
                "agent_id": row.get("agent_id"),
                "conversation_id": row.get("conversation_id"),
                "score": float(1.0 / (1.0 + max(row.get("_distance", 0.0), 0.0))),
            }
        )
    return {"query": query, "results": cleaned}
