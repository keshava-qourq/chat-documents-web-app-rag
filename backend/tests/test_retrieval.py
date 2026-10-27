"""Tests for `app.retrieval.retrieve_context`: whole-library ranking, the
configurable similarity threshold, and the no-ready-documents shortcut that
never calls Gemini.

Runs entirely against its own in-memory SQLite engine (not the shared
`conftest.py` fixtures, which are wired for the FastAPI `TestClient` rather
than direct module calls), so these exercise the in-Python cosine fallback
path -- the pgvector path is exercised against a real Postgres, matching the
dialect split `models.EmbeddingVector` already draws. That Postgres-backed
path runs a real database query (`_retrieve_postgres`'s `cosine_distance`
filter/order), which belongs with the project's other database-query
coverage under `backend/tests/integration/`, not here.
"""

import inspect
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, retrieval
from app.models import Chunk, Document


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_document(db_session, status: str, file_name: str = "handbook.pdf") -> Document:
    document = Document(
        id=uuid.uuid4(),
        file_name=file_name,
        mime_type="application/pdf",
        size_bytes=10,
        storage_key=f"{uuid.uuid4()}.pdf",
        status=status,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _make_chunk(
    db_session, document: Document, embedding: list[float] | None, location: str, index: int
) -> Chunk:
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content=f"content for {location}",
        source_location=location,
        chunk_index=index,
        embedding=embedding,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


def test_signature_has_no_per_document_or_per_thread_filter() -> None:
    params = set(inspect.signature(retrieval.retrieve_context).parameters)
    assert params == {"db", "question"}


def test_no_ready_documents_returns_empty_context_without_calling_gemini(
    db_session, monkeypatch
) -> None:
    def fail_embed(texts):
        raise AssertionError("embed_texts must not be called with no ready documents")

    monkeypatch.setattr(retrieval, "embed_texts", fail_embed)

    context = retrieval.retrieve_context(db_session, "What is the policy?")

    assert context.has_ready_documents is False
    assert context.chunks == []


def test_only_processing_documents_counts_as_no_ready_documents(db_session, monkeypatch) -> None:
    _make_document(db_session, status="processing")

    def fail_embed(texts):
        raise AssertionError("embed_texts must not be called")

    monkeypatch.setattr(retrieval, "embed_texts", fail_embed)

    context = retrieval.retrieve_context(db_session, "Anything?")

    assert context.has_ready_documents is False
    assert context.chunks == []


def test_ranks_chunks_by_similarity_across_all_ready_documents(db_session, monkeypatch) -> None:
    doc_a = _make_document(db_session, "ready", "policy-a.pdf")
    doc_b = _make_document(db_session, "ready", "policy-b.pdf")
    _make_chunk(db_session, doc_a, [1.0, 0.0, 0.0], "policy-a.pdf, page 1", 0)
    _make_chunk(db_session, doc_b, [0.0, 1.0, 0.0], "policy-b.pdf, page 1", 0)
    _make_chunk(db_session, doc_b, [0.9, 0.1, 0.0], "policy-b.pdf, page 2", 1)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setattr(retrieval, "retrieval_top_k", lambda: 10)

    context = retrieval.retrieve_context(db_session, "question")

    assert context.has_ready_documents is True
    names_locations = [(c.document_name, c.source_location) for c in context.chunks]
    assert names_locations[0] == ("policy-a.pdf", "policy-a.pdf, page 1")
    assert names_locations[1] == ("policy-b.pdf", "policy-b.pdf, page 2")
    assert names_locations[2] == ("policy-b.pdf", "policy-b.pdf, page 1")


def test_chunks_from_non_ready_documents_are_excluded(db_session, monkeypatch) -> None:
    ready_doc = _make_document(db_session, "ready", "ready.pdf")
    failed_doc = _make_document(db_session, "failed", "failed.pdf")
    _make_chunk(db_session, ready_doc, [1.0, 0.0], "ready.pdf, page 1", 0)
    _make_chunk(db_session, failed_doc, [1.0, 0.0], "failed.pdf, page 1", 0)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert [c.document_name for c in context.chunks] == ["ready.pdf"]


def test_unembedded_chunks_on_a_ready_document_are_excluded(db_session, monkeypatch) -> None:
    """A document can be `'ready'` while one of its chunks never got an
    embedding (e.g. a batch retry left a gap); `_retrieve_python` filters
    those out with `Chunk.embedding.isnot(None)`, and this pins that filter
    rather than letting it silently stop running."""
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)
    _make_chunk(db_session, document, None, "handbook.pdf, page 2", 1)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert [c.source_location for c in context.chunks] == ["handbook.pdf, page 1"]


def test_ready_document_with_no_chunks_at_all_yields_empty_chunks(db_session, monkeypatch) -> None:
    """Distinct from "chunks scored below threshold": here there is nothing
    to score at all (e.g. indexing created the document row before writing
    any chunk), and `has_ready_documents` must still report `True` since a
    `'ready'` document does exist."""
    _make_document(db_session, "ready")

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert context.has_ready_documents is True
    assert context.chunks == []


def test_question_is_embedded_as_the_sole_item(db_session, monkeypatch) -> None:
    """`retrieve_context` embeds exactly the caller's question, as a single-
    item batch, not a reformulated or batched-with-something-else call."""
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)

    calls: list[list[str]] = []

    def recording_embed(texts):
        calls.append(texts)
        return [[1.0, 0.0]]

    monkeypatch.setattr(retrieval, "embed_texts", recording_embed)
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    retrieval.retrieve_context(db_session, "What is the refund policy?")

    assert calls == [["What is the refund policy?"]]


def test_chunks_below_threshold_are_discarded(db_session, monkeypatch) -> None:
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)
    _make_chunk(db_session, document, [-1.0, 0.0], "handbook.pdf, page 2", 1)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: 0.5)

    context = retrieval.retrieve_context(db_session, "question")

    assert context.has_ready_documents is True
    assert len(context.chunks) == 1
    assert context.chunks[0].source_location == "handbook.pdf, page 1"


def test_ready_documents_but_zero_chunks_above_threshold_yields_empty_chunks(
    db_session, monkeypatch
) -> None:
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [-1.0, 0.0], "handbook.pdf, page 1", 0)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: 0.5)

    context = retrieval.retrieve_context(db_session, "question")

    assert context.has_ready_documents is True
    assert context.chunks == []


def test_top_k_limits_the_number_of_chunks_returned(db_session, monkeypatch) -> None:
    document = _make_document(db_session, "ready")
    for i in range(5):
        _make_chunk(db_session, document, [1.0, 0.0], f"handbook.pdf, page {i}", i)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setattr(retrieval, "retrieval_top_k", lambda: 2)

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 2


def test_top_k_is_floored_at_one_even_when_configured_at_zero(db_session, monkeypatch) -> None:
    """`retrieve_context` takes `max(1, retrieval_top_k())`, so a
    misconfigured `RETRIEVAL_TOP_K=0` still returns the single best match
    instead of silently returning nothing."""
    document = _make_document(db_session, "ready")
    for i in range(3):
        _make_chunk(db_session, document, [1.0, 0.0], f"handbook.pdf, page {i}", i)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setenv("RETRIEVAL_TOP_K", "0")

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 1


def test_retrieval_top_k_reads_env_var_and_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("RETRIEVAL_TOP_K", raising=False)
    assert retrieval.retrieval_top_k() == retrieval.RETRIEVAL_TOP_K_DEFAULT

    monkeypatch.setenv("RETRIEVAL_TOP_K", "3")
    assert retrieval.retrieval_top_k() == 3


def test_retrieval_similarity_threshold_reads_env_var_and_falls_back_to_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("RETRIEVAL_SIMILARITY_THRESHOLD", raising=False)
    assert (
        retrieval.retrieval_similarity_threshold()
        == retrieval.RETRIEVAL_SIMILARITY_THRESHOLD_DEFAULT
    )

    monkeypatch.setenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.75")
    assert retrieval.retrieval_similarity_threshold() == pytest.approx(0.75)
