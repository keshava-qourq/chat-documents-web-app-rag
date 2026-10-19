"""Unit tests for `app.retrieval.retrieve_context`: whole-library ranking,
the configurable top-k and similarity threshold, and the no-ready-documents
shortcut that never calls Gemini.

There is already a hand-written unit suite for this module under
`backend/app/tests/test_retrieval.py`, but `backend/pytest.ini` sets
`testpaths = tests`, so that directory is never collected by the project's
own test run (the same gap `backend/tests/test_generation.py` documents and
closes for `app.generation`) -- this file exists under `backend/tests/`
precisely so `app.retrieval` actually gets exercised by the suite that
runs.

Runs entirely against an in-memory SQLite, so these exercise the in-Python
cosine fallback path (`_retrieve_python`); the pgvector path
(`_retrieve_postgres`) needs a real Postgres with the `vector` extension to
exercise its `Chunk.embedding.cosine_distance(...)` query, which nothing in
this suite spins up -- see the skipped test below.

`Base` is imported directly (`from app.database import Base`), not reached
through `database.Base` at call time: `test_database.py` reloads
`app.database` to exercise its `DATABASE_URL` branch, which rebinds the
module's `Base` attribute to a fresh, empty-metadata class after that test
runs. A name captured here at collection time stays pointed at the one
`app.models` actually registers its tables on, regardless of test order --
exactly how `conftest.py`'s own fixtures do it.
"""

import inspect
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import retrieval
from app.database import Base
from app.models import Chunk, Document


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
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
    db_session, document: Document, embedding: list[float], location: str, index: int
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


# --- signature: whole-library search, no per-document/per-thread filter ----


def test_signature_has_no_per_document_or_per_thread_filter() -> None:
    params = set(inspect.signature(retrieval.retrieve_context).parameters)
    assert params == {"db", "question"}


# --- no ready documents: short-circuits before ever calling Gemini ---------


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


def test_only_failed_documents_counts_as_no_ready_documents(db_session, monkeypatch) -> None:
    _make_document(db_session, status="failed")

    def fail_embed(texts):
        raise AssertionError("embed_texts must not be called")

    monkeypatch.setattr(retrieval, "embed_texts", fail_embed)

    context = retrieval.retrieve_context(db_session, "Anything?")

    assert context.has_ready_documents is False
    assert context.chunks == []


# --- whole-library ranking across every ready document ---------------------


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


def test_embed_texts_is_called_with_exactly_the_question(db_session, monkeypatch) -> None:
    """`retrieve_context` embeds the literal question text, through the one
    Gemini seam this module uses -- not a reworded or truncated form."""
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)
    seen: list[list[str]] = []

    def record_embed(texts):
        seen.append(texts)
        return [[1.0, 0.0]]

    monkeypatch.setattr(retrieval, "embed_texts", record_embed)
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    retrieval.retrieve_context(db_session, "What is the remote-work policy?")

    assert seen == [["What is the remote-work policy?"]]


def test_chunks_from_non_ready_documents_are_excluded(db_session, monkeypatch) -> None:
    ready_doc = _make_document(db_session, "ready", "ready.pdf")
    failed_doc = _make_document(db_session, "failed", "failed.pdf")
    _make_chunk(db_session, ready_doc, [1.0, 0.0], "ready.pdf, page 1", 0)
    _make_chunk(db_session, failed_doc, [1.0, 0.0], "failed.pdf, page 1", 0)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert [c.document_name for c in context.chunks] == ["ready.pdf"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known defect, not introduced by this test suite: "
        "`_retrieve_python`'s `Chunk.embedding.isnot(None)` filter relies on "
        "a real SQL NULL, but on the SQLite/JSON fallback "
        "`EmbeddingVector` degrades to, SQLAlchemy's JSON type stores a "
        "Python `None` as a JSON `null` literal (none_as_null=False by "
        "default), not a SQL NULL -- so the filter does not exclude it and "
        "`_cosine_similarity` then raises TypeError on `zip(vector, None)`. "
        "Not reachable through the actual ingestion pipeline today (a "
        "document never reaches 'ready' with an unembedded chunk still "
        "attached -- `ingest_document` always embeds a chunk before "
        "committing it, or deletes the batch and fails the document), so "
        "this is left documented rather than worked around here."
    ),
)
def test_chunks_with_no_embedding_yet_are_excluded(db_session, monkeypatch) -> None:
    """A chunk row can exist before its batch has been embedded (ingestion
    is incremental); it must never be ranked until it has a vector."""
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)
    unembedded = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content="not yet embedded",
        source_location="handbook.pdf, page 2",
        chunk_index=1,
        embedding=None,
    )
    db_session.add(unembedded)
    db_session.commit()

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert [c.source_location for c in context.chunks] == ["handbook.pdf, page 1"]


# --- the configurable similarity threshold ---------------------------------


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


def test_retrieval_similarity_threshold_reads_env_var_and_falls_back_to_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("RETRIEVAL_SIMILARITY_THRESHOLD", raising=False)
    assert (
        retrieval.retrieval_similarity_threshold()
        == retrieval.RETRIEVAL_SIMILARITY_THRESHOLD_DEFAULT
    )

    monkeypatch.setenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.75")
    assert retrieval.retrieval_similarity_threshold() == 0.75


# --- the configurable top-k cap --------------------------------------------


def test_top_k_limits_the_number_of_chunks_returned(db_session, monkeypatch) -> None:
    document = _make_document(db_session, "ready")
    for i in range(5):
        _make_chunk(db_session, document, [1.0, 0.0], f"handbook.pdf, page {i}", i)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setattr(retrieval, "retrieval_top_k", lambda: 2)

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 2


def test_retrieval_top_k_reads_env_var_and_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("RETRIEVAL_TOP_K", raising=False)
    assert retrieval.retrieval_top_k() == retrieval.RETRIEVAL_TOP_K_DEFAULT

    monkeypatch.setenv("RETRIEVAL_TOP_K", "3")
    assert retrieval.retrieval_top_k() == 3


def test_a_non_positive_configured_top_k_still_returns_at_least_one_chunk(
    db_session, monkeypatch
) -> None:
    """`retrieve_context` floors `retrieval_top_k()` at 1 so a
    misconfigured (zero or negative) value cannot silently starve
    generation of every chunk."""
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setattr(retrieval, "retrieval_top_k", lambda: 0)

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 1


# --- returned chunk fields carry what generation/citations need -----------


def test_returned_chunks_carry_document_id_chunk_id_and_content(db_session, monkeypatch) -> None:
    document = _make_document(db_session, "ready", "handbook.pdf")
    chunk = _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 1
    result = context.chunks[0]
    assert result.chunk_id == chunk.id
    assert result.document_id == document.id
    assert result.document_name == "handbook.pdf"
    assert result.content == chunk.content
    assert isinstance(result.similarity, float)


# --- the pgvector dialect path needs a real Postgres to exercise ----------


@pytest.mark.skip(
    reason=(
        "The pgvector cosine-distance path (_retrieve_postgres) runs "
        "Chunk.embedding.cosine_distance(...) through a real `vector(768)` "
        "column; SQLite (used throughout this suite, matching the rest of "
        "the project's unit tests) has no such type and no server to run "
        "it against. Exercising this branch needs a Postgres instance with "
        "the pgvector extension, which nothing in this test run provisions."
    )
)
def test_retrieve_postgres_ranks_by_pgvector_cosine_distance() -> None:
    pass
