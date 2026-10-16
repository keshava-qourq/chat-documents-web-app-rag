"""Whole-library grounded retrieval.

Embeds the question through `app.embeddings` (the only Gemini seam this
module uses) and ranks chunks by vector similarity across every document
with status `'ready'` in the shared library. There is deliberately no
per-document or per-thread filter anywhere in `retrieve_context`'s
signature -- whole-library search is the agreed behaviour for this release,
not an oversight to be tightened later.

Ranking runs against pgvector's cosine distance when `DATABASE_URL` points
at Postgres, and degrades to an in-Python cosine similarity over the plain
JSON array `EmbeddingVector` stores on SQLite -- the same dialect split
`models.EmbeddingVector` already draws, kept consistent here rather than
introducing a second way to tell the two apart.
"""

import math
import os
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.embeddings import embed_texts
from app.models import Chunk, Document

RETRIEVAL_TOP_K_DEFAULT = 8
RETRIEVAL_SIMILARITY_THRESHOLD_DEFAULT = 0.5


def retrieval_top_k() -> int:
    """Maximum number of chunks handed to generation for one question."""
    return int(os.getenv("RETRIEVAL_TOP_K", str(RETRIEVAL_TOP_K_DEFAULT)))


def retrieval_similarity_threshold() -> float:
    """Chunks scoring below this cosine similarity are discarded before generation."""
    return float(
        os.getenv("RETRIEVAL_SIMILARITY_THRESHOLD", str(RETRIEVAL_SIMILARITY_THRESHOLD_DEFAULT))
    )


@dataclass
class RetrievedChunk:
    """One chunk that survived retrieval, carrying what generation and
    citations need from it."""

    chunk_id: UUID
    document_id: UUID
    document_name: str
    source_location: str | None
    content: str
    similarity: float


@dataclass
class RetrievedContext:
    """What `retrieve_context` hands to `generate_answer`."""

    chunks: list[RetrievedChunk] = field(default_factory=list)
    has_ready_documents: bool = False


def retrieve_context(db: Session, question: str) -> RetrievedContext:
    """Ranks chunks across every `'ready'` document by similarity to `question`.

    Returns an empty, `has_ready_documents=False` context without calling
    Gemini at all when no document in the shared library is `'ready'` yet.
    """
    ready_exists = db.query(Document.id).filter(Document.status == "ready").first() is not None
    if not ready_exists:
        return RetrievedContext(chunks=[], has_ready_documents=False)

    [query_vector] = embed_texts([question])
    threshold = retrieval_similarity_threshold()
    top_k = max(1, retrieval_top_k())

    dialect = db.get_bind().dialect.name

    if dialect == "postgresql":
        scored = _retrieve_postgres(db, query_vector, top_k)
    else:
        scored = _retrieve_python(db, query_vector, top_k)

    chunks = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            document_name=document.file_name,
            source_location=chunk.source_location,
            content=chunk.content,
            similarity=similarity,
        )
        for similarity, chunk, document in scored
        if similarity >= threshold
    ]
    return RetrievedContext(chunks=chunks, has_ready_documents=True)


def _retrieve_postgres(
    db: Session, query_vector: list[float], top_k: int
) -> list[tuple[float, Chunk, Document]]:
    distance = Chunk.embedding.cosine_distance(query_vector)
    rows = (
        db.query(Chunk, Document, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.status == "ready")
        .filter(Chunk.embedding.isnot(None))
        .order_by(distance)
        .limit(top_k)
        .all()
    )
    return [(1.0 - dist, chunk, document) for chunk, document, dist in rows]


def _retrieve_python(
    db: Session, query_vector: list[float], top_k: int
) -> list[tuple[float, Chunk, Document]]:
    rows = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.status == "ready")
        .filter(Chunk.embedding.isnot(None))
        .all()
    )
    scored = [
        (_cosine_similarity(query_vector, chunk.embedding), chunk, document)
        for chunk, document in rows
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


__all__ = [
    "RetrievedChunk",
    "RetrievedContext",
    "retrieve_context",
    "retrieval_top_k",
    "retrieval_similarity_threshold",
]
