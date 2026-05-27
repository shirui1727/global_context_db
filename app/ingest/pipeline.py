from hashlib import sha256

from app.core.schemas import IngestRequest
from app.storage.repo import documents_repo, chunks_repo
from app.reader.service import read_text_fast
from app.retrieval.embedding import embed_text
from app.storage.vector_store import upsert_items
from app.text.chunking import chunk_text


def ingest_text(payload: IngestRequest) -> dict:
    doc_id = sha256((payload.source + "\n" + payload.text).encode("utf-8")).hexdigest()
    documents_repo().upsert(doc_id, payload.source, payload.text)

    reader_item = read_text_fast(
        source=payload.source,
        text=payload.text,
        cube_id=payload.cube_id,
        tags=payload.tags,
        metadata=payload.metadata,
    )
    chunks = chunk_text(reader_item.content)
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
                "cube_id": payload.cube_id,
                "source": payload.source,
                "doc_id": doc_id,
                "chunk_index": i,
                "tags": reader_item.tags,
                "context_domain": "document",
                "source_kind": "reader_fast",
                "metadata": {
                    **reader_item.metadata,
                    "reader": {
                        "source_domain": reader_item.source_domain,
                        "source_id": reader_item.source_id,
                        "content_kind": reader_item.content_kind,
                        "provenance": reader_item.provenance,
                    },
                },
            }
        )

    upsert_items(rows)
    return {"document_id": doc_id, "chunks": len(rows)}

