"""Unit tests for `app.models`: column defaults, the relationship cascades
and foreign-key `ondelete` behaviour the approved data model calls for, and
the `EmbeddingVector` TypeDecorator's Postgres/SQLite dialect split.

This ticket carries no acceptance criteria of its own -- `models.py` is pure
schema with no endpoint attached. These tests follow the contract
documented in the module's own docstrings and comments instead, the same
approach `test_database.py` takes for `app.database`.

Runs against its own throwaway in-memory SQLite engine, the same pattern
`test_retrieval.py` uses for direct model work, rather than the
`conftest.py` fixtures wired for the FastAPI `TestClient`. The pgvector path
of `EmbeddingVector` (the real `vector(768)` column on Postgres) is exercised
directly against dialect objects below -- without a connection, since that
is all `load_dialect_impl` needs -- rather than against a live Postgres,
which this test tree does not assume. Other suites already prove every
*behavioural* consequence of this schema (chunks disappearing when their
document is deleted via the API in `test_document_delete.py`, citations
surviving with `chunk_id=None` in `test_threads.py`, and so on); this file
instead proves the schema itself -- the configuration that makes those
behaviours possible -- would fail if the model changed out from under them.
"""

import uuid

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON

from app import models
from app.models import (
    EMBEDDING_DIM,
    Chunk,
    Citation,
    Document,
    EmbeddingVector,
    Message,
    Thread,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _document(**overrides) -> Document:
    defaults = dict(
        file_name="handbook.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        storage_key=f"{uuid.uuid4()}.pdf",
    )
    defaults.update(overrides)
    return Document(**defaults)


# --- EMBEDDING_DIM and the EmbeddingVector dialect split --------------------


def test_embedding_dim_is_768() -> None:
    assert EMBEDDING_DIM == 768


def test_embedding_vector_resolves_to_a_768_dim_pgvector_column_on_postgres() -> None:
    impl = EmbeddingVector().load_dialect_impl(postgresql.dialect())

    assert isinstance(impl, Vector)
    assert impl.dim == EMBEDDING_DIM


def test_embedding_vector_resolves_to_json_on_every_other_dialect() -> None:
    """SQLite has no vector type -- the module docstring's whole point is
    that this column degrades to JSON there, so a fresh clone with no
    Postgres can still create the schema and round-trip an embedding."""
    impl = EmbeddingVector().load_dialect_impl(sqlite.dialect())

    assert isinstance(impl, JSON)
    assert not isinstance(impl, Vector)


def test_embedding_vector_shares_vectors_comparator_factory() -> None:
    """`app.retrieval`'s own docstring says its pgvector path orders chunks
    by `Chunk.embedding.cosine_distance(...)` -- an operator the plain JSON
    comparator does not have. That is only reachable because this column's
    comparator is `Vector`'s own, not JSON's default."""
    assert EmbeddingVector.comparator_factory is Vector.comparator_factory


def test_embedding_round_trips_through_a_chunk_on_sqlite(db_session) -> None:
    document = _document()
    db_session.add(document)
    db_session.commit()
    vector = [0.1, 0.2, 0.3]
    chunk = Chunk(
        document_id=document.id,
        content="some text",
        source_location="p.1",
        chunk_index=0,
        embedding=vector,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.expire_all()

    reloaded = db_session.get(Chunk, chunk.id)

    assert reloaded.embedding == vector


def test_embedding_defaults_to_none_when_not_yet_computed(db_session) -> None:
    """A freshly extracted chunk is persisted before embedding runs -- the
    column has to tolerate that, not reject the insert."""
    document = _document()
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(document_id=document.id, content="raw text", source_location="p.1", chunk_index=0)

    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    assert chunk.embedding is None


# --- column defaults ---------------------------------------------------------


def test_document_defaults(db_session) -> None:
    document = _document()

    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert isinstance(document.id, uuid.UUID)
    assert document.status == "processing"
    assert document.progress == 0
    assert document.chunk_count == 0
    assert document.failure_reason is None
    assert document.uploaded_at is not None


def test_thread_defaults(db_session) -> None:
    thread = Thread()

    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    assert isinstance(thread.id, uuid.UUID)
    assert thread.title == "New conversation"
    assert thread.created_at is not None
    assert thread.last_active_at is not None


def test_message_defaults(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="assistant")

    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    assert message.content == ""
    assert message.status == "complete"
    assert message.created_at is not None


# --- table names, matching the approved data model --------------------------


@pytest.mark.parametrize(
    "model,expected_table",
    [
        (Document, "documents"),
        (Chunk, "chunks"),
        (Thread, "threads"),
        (Message, "messages"),
        (Citation, "citations"),
    ],
)
def test_table_names_match_the_approved_data_model(model, expected_table) -> None:
    assert model.__tablename__ == expected_table


# --- foreign key ondelete, as the migration encodes it -----------------------


def _ondelete(column) -> str | None:
    (foreign_key,) = column.foreign_keys
    return foreign_key.ondelete


def test_chunk_document_id_cascades_on_delete() -> None:
    assert _ondelete(Chunk.__table__.c.document_id) == "CASCADE"


def test_message_thread_id_cascades_on_delete() -> None:
    assert _ondelete(Message.__table__.c.thread_id) == "CASCADE"


def test_citation_message_id_cascades_on_delete() -> None:
    assert _ondelete(Citation.__table__.c.message_id) == "CASCADE"


def test_citation_chunk_id_is_nullable_and_set_null_on_delete() -> None:
    """A citation must survive its source chunk being deleted (the document
    it came from can be removed per AC-015/016) -- `SET NULL` plus a
    nullable column is what lets the row persist instead of being rejected
    or cascading away the citation itself."""
    assert Citation.__table__.c.chunk_id.nullable is True
    assert _ondelete(Citation.__table__.c.chunk_id) == "SET NULL"


# --- relationship cascades, exercised through the ORM ------------------------


def test_deleting_a_document_deletes_its_chunks(db_session) -> None:
    document = _document()
    db_session.add(document)
    db_session.commit()
    db_session.add_all(
        [
            Chunk(document_id=document.id, content="a", source_location="p.1", chunk_index=0),
            Chunk(document_id=document.id, content="b", source_location="p.2", chunk_index=1),
        ]
    )
    db_session.commit()
    assert db_session.query(Chunk).filter(Chunk.document_id == document.id).count() == 2

    db_session.delete(document)
    db_session.commit()

    assert db_session.query(Chunk).filter(Chunk.document_id == document.id).count() == 0


def test_removing_a_chunk_from_its_documents_collection_deletes_the_orphan(db_session) -> None:
    """`cascade="all, delete-orphan"` on `Document.chunks` means a chunk
    detached from its parent's own collection is deleted outright, not left
    behind with a dangling reference -- distinct from the whole-parent
    delete case above, and the behaviour `delete-orphan` specifically adds
    on top of a plain cascading delete."""
    document = _document()
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(document_id=document.id, content="a", source_location="p.1", chunk_index=0)
    document.chunks.append(chunk)
    db_session.commit()
    chunk_id = chunk.id

    document.chunks.remove(chunk)
    db_session.commit()

    assert db_session.get(Chunk, chunk_id) is None


def test_deleting_a_thread_deletes_its_messages(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    db_session.add_all(
        [
            Message(thread_id=thread.id, role="user", content="hi"),
            Message(thread_id=thread.id, role="assistant", content="hello"),
        ]
    )
    db_session.commit()
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 2

    db_session.delete(thread)
    db_session.commit()

    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0


def test_deleting_a_message_deletes_its_citations(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="assistant", content="answer")
    db_session.add(message)
    db_session.commit()
    db_session.add(
        Citation(
            message_id=message.id,
            chunk_id=None,
            document_name="handbook.pdf",
            source_location="p.1",
            excerpt="an excerpt",
        )
    )
    db_session.commit()
    assert db_session.query(Citation).filter(Citation.message_id == message.id).count() == 1

    db_session.delete(message)
    db_session.commit()

    assert db_session.query(Citation).filter(Citation.message_id == message.id).count() == 0


def test_citation_can_reference_no_chunk(db_session) -> None:
    """A citation outlives the document it quoted (the delete endpoint this
    column exists for), so the model must allow `chunk_id=None` without
    rejecting the insert."""
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="assistant", content="answer")
    db_session.add(message)
    db_session.commit()

    citation = Citation(
        message_id=message.id,
        chunk_id=None,
        document_name="handbook.pdf",
        source_location="p.1",
        excerpt="an excerpt",
    )
    db_session.add(citation)
    db_session.commit()
    db_session.refresh(citation)

    assert citation.chunk_id is None
    assert citation.chunk is None


# --- module exports -----------------------------------------------------------


def test_all_exports_every_model_and_the_embedding_pieces() -> None:
    assert set(models.__all__) == {
        "Base",
        "Document",
        "Chunk",
        "Thread",
        "Message",
        "Citation",
        "EmbeddingVector",
        "EMBEDDING_DIM",
    }
