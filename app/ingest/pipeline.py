from hashlib import sha256

from app.core.schemas import IngestRequest
from app.storage.repo import documents_repo, chunks_repo
from app.retrieval.embedding import embed_text
from app.storage.vector_store import upsert_items
from app.text.chunking import chunk_text


def ingest_text(payload: IngestRequest) -> dict:
    doc_id = sha256((payload.source + "\n" + payload.text).encode("utf-8")).hexdigest()
    documents_repo().upsert(doc_id, payload.source, payload.text)

    chunks = chunk_text(payload.text)
    rows = []
    for i, chunk in enumerate(chunks):
        chunk_id = sha256(f"{doc_id}:{i}:{chunk}".encode("utf-8")).hexdigest()
        vec = embed_text(chunk)
        chunks_repo().upsert(chunk_id, doc_id, i, chunk)
        rows.append(
            {
                "id": chunk_id,
                "kind": "chunk",
                "text": chunk,
                "vector": vec.tolist(),
                "source": payload.source,
                "doc_id": doc_id,
                "chunk_index": i,
            }
        )

    upsert_items(rows)
    return {"document_id": doc_id, "chunks": len(rows)}

