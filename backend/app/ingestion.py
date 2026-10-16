"""The background ingestion pipeline: extract, chunk, embed, persist.

`ingest_document` is the only entry point and matches exactly the contract
the upload endpoint (and, later, a task queue) calls against: a document id
and a plain `Session`, nothing else. It never reads from a request, never
assumes an open client connection, and can be called from a background task,
a worker process, or a one-off script equally well.

Original bytes are read through `app.storage`'s client factory -- the same
boto3 client the upload/delete routes use -- rather than a second storage
path. Failure handling is terminal and specific: extraction that finds no
usable text (a scanned PDF, an empty file) fails the document without ever
calling Gemini; an embedding failure after every retry fails the document
and deletes any chunk rows already written for it, so a failed document never
has partial chunks a poller or the chat endpoint could stumble on.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app import storage
from app.chunking import chunk_fragments
from app.config import chunk_overlap, chunk_size, embedding_batch_size
from app.embeddings import EmbeddingServiceError, GeminiNotConfiguredError, embed_texts
from app.extraction import extract_fragments
from app.models import Chunk, Document

NO_TEXT_REASON = (
    "No text could be extracted from this file. Scanned or image-only documents are not supported."
)
CONFIGURATION_REASON = "Gemini is not configured; set GEMINI_API_KEY to enable indexing."
EMBEDDING_FAILURE_REASON = "embedding service error"
STORAGE_READ_REASON = "Could not read the stored file; please try again."


def ingest_document(document_id: UUID, db: Session) -> None:
    """Extracts, chunks and embeds one document, leaving it in a terminal status."""
    document = db.get(Document, document_id)
    if document is None:
        return

    document.status = "processing"
    document.progress = 0
    document.failure_reason = None
    db.commit()

    try:
        content = _read_original(document)
    except Exception:
        _fail(db, document, STORAGE_READ_REASON)
        return

    try:
        fragments = extract_fragments(content, _extension(document.file_name), document.file_name)
    except Exception:
        _fail(db, document, NO_TEXT_REASON)
        return

    fragments = [(text, location) for text, location in fragments if text and text.strip()]
    if not fragments:
        _fail(db, document, NO_TEXT_REASON)
        return

    chunks = chunk_fragments(fragments, chunk_size(), chunk_overlap())
    if not chunks:
        _fail(db, document, NO_TEXT_REASON)
        return

    batch_size = max(1, embedding_batch_size())
    total = len(chunks)
    stored = 0

    try:
        for start in range(0, total, batch_size):
            batch = chunks[start : start + batch_size]
            vectors = embed_texts([piece for piece, _location, _index in batch])
            for (piece, location, index), vector in zip(batch, vectors, strict=True):
                db.add(
                    Chunk(
                        document_id=document.id,
                        content=piece,
                        source_location=location,
                        chunk_index=index,
                        embedding=vector,
                    )
                )
            stored += len(batch)
            document.progress = min(99, int(stored * 100 / total))
            db.commit()
    except GeminiNotConfiguredError:
        _delete_chunks(db, document.id)
        _fail(db, document, CONFIGURATION_REASON)
        return
    except EmbeddingServiceError:
        _delete_chunks(db, document.id)
        _fail(db, document, EMBEDDING_FAILURE_REASON)
        return
    except Exception:
        _delete_chunks(db, document.id)
        _fail(db, document, EMBEDDING_FAILURE_REASON)
        return

    document.status = "ready"
    document.progress = 100
    document.chunk_count = stored
    document.failure_reason = None
    db.commit()


def _read_original(document: Document) -> bytes:
    client = storage.get_client()
    response = client.get_object(Bucket=storage.BUCKET_NAME, Key=document.storage_key)
    return response["Body"].read()


def _extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return "." + file_name.rsplit(".", 1)[-1].lower()


def _delete_chunks(db: Session, document_id: UUID) -> None:
    db.query(Chunk).filter(Chunk.document_id == document_id).delete()
    db.commit()


def _fail(db: Session, document: Document, reason: str) -> None:
    document.status = "failed"
    document.failure_reason = reason
    document.progress = 100
    db.commit()
