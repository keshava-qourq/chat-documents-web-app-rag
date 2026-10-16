"""Unit tests for `app.models`.

Every other suite in `backend/tests/` exercises these models only through an
HTTP route -- upload, delete, post a message, and so on -- which proves the
*routes* behave, but never pins down the model definitions themselves: what
each column defaults to with nothing supplied, which columns the schema
actually refuses to leave empty, and what the ORM does to a model's
relatives when that model's own row is deleted. Those are this module's
job, exercised directly against the ORM with the `db_session` fixture from
`conftest.py` (an in-memory SQLite database, no `client`, no HTTP, no
network) -- plus `EmbeddingVector.load_dialect_impl`, which no route can
reach at all since no suite here runs against a real Postgres dialect.

Three cascades are proven directly rather than assumed from the docstrings
that name them:

* `Document.chunks` and `Thread.messages` are declared `cascade="all,
  delete-orphan"` -- deleting the parent must remove the children, not
  leave them orphaned.
* `Citation.chunk` is declared `ondelete="SET NULL"` at the column level,
  with no delete cascade on `Chunk.citations` -- deleting a chunk must
  nullify a citation's `chunk_id` and leave the citation row itself intact
  (this is exactly what `CitationOut.from_citation` reads to decide
  `document_available`). SQLite does not enforce foreign keys by default,
  so this is SQLAlchemy's own ORM-level nullification doing the work in
  this suite, not the database -- which is also why it is worth pinning
  down here rather than trusting the column's `ondelete` argument alone.
"""

import uuid

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.types import JSON

from app.models import (
    EMBEDDING_DIM,
    Chunk,
    Citation,
    Document,
    EmbeddingVector,
    Message,
    Thread,
)


# --- table names match the approved data model ------------------------------


def test_table_names_match_the_approved_data_model() -> None:
    assert Document.__tablename__ == "documents"
    assert Chunk.__tablename__ == "chunks"
    assert Thread.__tablename__ == "threads"
    assert Message.__tablename__ == "messages"
    assert Citation.__tablename__ == "citations"


# --- Document: defaults and required columns --------------------------------


def test_document_defaults_id_status_progress_chunk_count_and_timestamp(db_session) -> None:
    document = Document(
        file_name="handbook.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        storage_key="handbook.pdf",
    )

    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    assert isinstance(document.id, uuid.UUID)
    assert document.status == "processing"
    assert document.progress == 0
    assert document.chunk_count == 0
    assert document.failure_reason is None
    assert document.uploaded_at is not None


def test_document_without_a_file_name_is_rejected_by_the_schema(db_session) -> None:
    document = Document(mime_type="text/plain", size_bytes=10, storage_key="x.txt")
    db_session.add(document)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_document_without_a_storage_key_is_rejected_by_the_schema(db_session) -> None:
    document = Document(file_name="x.txt", mime_type="text/plain", size_bytes=10)
    db_session.add(document)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Chunk: required columns and the optional embedding ---------------------


def test_chunk_without_a_document_id_is_rejected_by_the_schema(db_session) -> None:
    chunk = Chunk(content="some text", chunk_index=0)
    db_session.add(chunk)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_chunk_embedding_is_optional_and_defaults_to_none(db_session) -> None:
    document = Document(file_name="a.txt", mime_type="text/plain", size_bytes=1, storage_key="a.txt")
    db_session.add(document)
    db_session.commit()

    chunk = Chunk(document_id=document.id, content="no embedding yet", chunk_index=0)
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    assert chunk.embedding is None


def test_chunk_embedding_round_trips_as_a_list_of_floats_through_a_fresh_session(
    db_session,
) -> None:
    """Writes through `db_session`, then reads back through an entirely
    separate `Session` bound to the same engine -- proving the value
    survives a real serialise/deserialise through `EmbeddingVector`, not
    just a Python object held in `db_session`'s own identity map."""
    document = Document(file_name="b.txt", mime_type="text/plain", size_bytes=1, storage_key="b.txt")
    db_session.add(document)
    db_session.commit()

    vector = [0.1, 0.2, 0.3]
    chunk = Chunk(document_id=document.id, content="has an embedding", chunk_index=0, embedding=vector)
    db_session.add(chunk)
    db_session.commit()
    chunk_id = chunk.id

    fresh_session = OrmSession(bind=db_session.get_bind())
    try:
        reloaded = fresh_session.get(Chunk, chunk_id)
        assert reloaded.embedding == vector
    finally:
        fresh_session.close()


# --- Thread: defaults --------------------------------------------------------


def test_thread_defaults_title_and_both_timestamps(db_session) -> None:
    thread = Thread()

    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    assert thread.title == "New conversation"
    assert thread.created_at is not None
    assert thread.last_active_at is not None


# --- Message: defaults and required columns ---------------------------------


def test_message_defaults_content_and_status(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()

    message = Message(thread_id=thread.id, role="user")
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    assert message.content == ""
    assert message.status == "complete"
    assert message.created_at is not None


def test_message_without_a_thread_id_is_rejected_by_the_schema(db_session) -> None:
    message = Message(role="user", content="orphaned")
    db_session.add(message)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Citation: required columns and optional chunk_id/source_location ------


def test_citation_without_a_message_id_is_rejected_by_the_schema(db_session) -> None:
    citation = Citation(document_name="a.txt", excerpt="an excerpt")
    db_session.add(citation)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_citation_chunk_id_and_source_location_default_to_none(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="assistant", content="an answer")
    db_session.add(message)
    db_session.commit()

    citation = Citation(message_id=message.id, document_name="a.txt", excerpt="an excerpt")
    db_session.add(citation)
    db_session.commit()
    db_session.refresh(citation)

    assert citation.chunk_id is None
    assert citation.source_location is None


# --- cascades: Document -> Chunk, Thread -> Message, Message -> Citation ----


def test_deleting_a_document_cascades_to_delete_its_chunks(db_session) -> None:
    document = Document(file_name="c.txt", mime_type="text/plain", size_bytes=1, storage_key="c.txt")
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(document_id=document.id, content="will be deleted", chunk_index=0)
    db_session.add(chunk)
    db_session.commit()
    chunk_id = chunk.id

    db_session.delete(document)
    db_session.commit()

    assert db_session.get(Chunk, chunk_id) is None


def test_deleting_a_thread_cascades_to_delete_its_messages(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="user", content="will be deleted")
    db_session.add(message)
    db_session.commit()
    message_id = message.id

    db_session.delete(thread)
    db_session.commit()

    assert db_session.get(Message, message_id) is None


def test_deleting_a_message_cascades_to_delete_its_citations(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="assistant", content="an answer")
    db_session.add(message)
    db_session.commit()
    citation = Citation(message_id=message.id, document_name="a.txt", excerpt="an excerpt")
    db_session.add(citation)
    db_session.commit()
    citation_id = citation.id

    db_session.delete(message)
    db_session.commit()

    assert db_session.get(Citation, citation_id) is None


def test_deleting_a_chunk_nullifies_its_citations_chunk_id_without_deleting_the_citation(
    db_session,
) -> None:
    document = Document(file_name="d.txt", mime_type="text/plain", size_bytes=1, storage_key="d.txt")
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(document_id=document.id, content="will be deleted", chunk_index=0)
    db_session.add(chunk)
    db_session.commit()
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    message = Message(thread_id=thread.id, role="assistant", content="an answer")
    db_session.add(message)
    db_session.commit()
    citation = Citation(
        message_id=message.id,
        chunk_id=chunk.id,
        document_name="d.txt",
        excerpt="an excerpt",
    )
    db_session.add(citation)
    db_session.commit()
    citation_id = citation.id

    db_session.delete(chunk)
    db_session.commit()

    surviving = db_session.get(Citation, citation_id)
    assert surviving is not None
    assert surviving.chunk_id is None


# --- EmbeddingVector: pgvector on Postgres, plain JSON everywhere else ------


class _FakeDialect:
    """Stands in for a SQLAlchemy `Dialect`: only `name` and
    `type_descriptor` are used by `EmbeddingVector.load_dialect_impl`."""

    def __init__(self, name: str) -> None:
        self.name = name

    def type_descriptor(self, type_):
        return type_


def test_embedding_vector_impl_is_json() -> None:
    assert EmbeddingVector.impl is JSON


def test_embedding_vector_resolves_to_pgvector_sized_to_embedding_dim_on_postgresql() -> None:
    resolved = EmbeddingVector().load_dialect_impl(_FakeDialect("postgresql"))

    assert isinstance(resolved, Vector)
    assert resolved.dim == EMBEDDING_DIM


def test_embedding_vector_resolves_to_plain_json_on_non_postgresql_dialects() -> None:
    resolved = EmbeddingVector().load_dialect_impl(_FakeDialect("sqlite"))

    assert isinstance(resolved, JSON)
    assert not isinstance(resolved, Vector)


def test_embedding_dim_matches_text_embedding_004s_768_dimensional_output() -> None:
    assert EMBEDDING_DIM == 768


# --- module surface -----------------------------------------------------------


def test_models_module_exports_every_entity_and_the_embedding_helpers() -> None:
    import app.models as models_module

    for name in (
        "Base",
        "Document",
        "Chunk",
        "Thread",
        "Message",
        "Citation",
        "EmbeddingVector",
        "EMBEDDING_DIM",
    ):
        assert name in models_module.__all__
        assert hasattr(models_module, name)
