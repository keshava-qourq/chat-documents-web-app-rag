"""Unit tests for `app.models`: column defaults, the `EmbeddingVector`
dialect switch, the foreign keys' `ondelete` configuration, and the ORM-level
cascade/orphan/nullify behaviour the routers lean on when they call
`db.delete(...)` directly.

Exercises the models directly against the `db_session` fixture from
`conftest.py` (an in-memory SQLite database created from `Base.metadata`) --
no HTTP client, no router, no service layer -- so what fails here is the
model declaration itself, not anything built on top of it.

`backend/tests/test_document_delete.py` and `test_threads.py` already prove
these cascades end-to-end through `DELETE /documents/{id}` and
`DELETE /threads/{id}`; this file does not repeat those routes. It instead
covers what only a direct, model-level test can reach: the defaults a bare
`Document()`/`Thread()`/`Message()` gets with no router or service in the
way, the `ondelete` clause actually declared on each foreign key (not just
its observed effect through one particular route), delete-orphan removal
triggered by editing a relationship collection rather than deleting its
parent, and the `EmbeddingVector` type's Postgres branch -- which, since the
whole suite otherwise runs on SQLite, no other test in this repository ever
reaches at all.
"""

import uuid

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.types import JSON

from app.models import EMBEDDING_DIM, Chunk, Citation, Document, EmbeddingVector, Message, Thread

# --- defaults: a bare instance, no router or service involved ---------------


def test_document_gets_a_uuid_and_its_documented_defaults(db_session) -> None:
    document = Document(
        file_name="handbook.pdf",
        mime_type="application/pdf",
        size_bytes=1234,
        storage_key="some-key.pdf",
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


def test_thread_defaults_to_new_conversation_and_sets_both_timestamps(db_session) -> None:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    assert isinstance(thread.id, uuid.UUID)
    assert thread.title == "New conversation"
    assert thread.created_at is not None
    assert thread.last_active_at is not None


def test_message_defaults_to_empty_content_and_complete_status(db_session) -> None:
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


# --- EmbeddingVector: the dialect switch itself -----------------------------


def test_embedding_vector_resolves_to_json_on_a_non_postgresql_dialect() -> None:
    column_type = EmbeddingVector()

    resolved = column_type.load_dialect_impl(sqlite.dialect())

    assert isinstance(resolved, JSON)


def test_embedding_vector_resolves_to_a_768_dimensional_pgvector_on_postgresql() -> None:
    """`load_dialect_impl` hands back `dialect.type_descriptor(Vector(768))`,
    which the Postgres dialect adapts to its own dialect-specific `VECTOR`
    impl class rather than returning the `pgvector.sqlalchemy.Vector`
    instance unchanged -- so this asserts on the one thing that survives
    that adaptation and is what actually matters: the column really is a
    vector type, sized for the 768-dimensional embeddings this project's
    embedding model produces, not the JSON fallback every other test in this
    suite (running on SQLite) would otherwise silently get instead."""
    column_type = EmbeddingVector()

    resolved = column_type.load_dialect_impl(postgresql.dialect())

    assert "VECTOR" in type(resolved).__name__.upper()
    assert resolved.dim == EMBEDDING_DIM


def test_embedding_round_trips_through_sqlite_as_a_plain_list_of_floats(db_session) -> None:
    """On the SQLite engine every other test in this suite runs against,
    `EmbeddingVector` degrades to JSON -- proves a value written through the
    ORM reads back as the same list of floats after a real commit, not just
    within the same in-memory Python object."""
    document = Document(
        file_name="doc.txt",
        mime_type="text/plain",
        size_bytes=10,
        storage_key="doc.txt",
    )
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(
        document_id=document.id,
        content="some chunk text",
        chunk_index=0,
        embedding=[0.25, -0.5, 1.0],
    )
    db_session.add(chunk)
    db_session.commit()
    chunk_id = chunk.id

    db_session.expire_all()
    reloaded = db_session.get(Chunk, chunk_id)

    assert reloaded.embedding == [0.25, -0.5, 1.0]


# --- foreign keys: the declared ondelete, not just one route's effect ------


def test_chunk_document_id_cascades_on_delete() -> None:
    (fk,) = Chunk.__table__.columns["document_id"].foreign_keys
    assert fk.ondelete == "CASCADE"


def test_message_thread_id_cascades_on_delete() -> None:
    (fk,) = Message.__table__.columns["thread_id"].foreign_keys
    assert fk.ondelete == "CASCADE"


def test_citation_message_id_cascades_on_delete() -> None:
    (fk,) = Citation.__table__.columns["message_id"].foreign_keys
    assert fk.ondelete == "CASCADE"


def test_citation_chunk_id_sets_null_on_delete_and_is_nullable() -> None:
    column = Citation.__table__.columns["chunk_id"]
    (fk,) = column.foreign_keys
    assert fk.ondelete == "SET NULL"
    assert column.nullable is True


# --- delete-orphan: removing from the relationship, not deleting the parent -


def test_removing_a_chunk_from_documents_chunks_collection_deletes_its_row(db_session) -> None:
    document = Document(
        file_name="doc.txt", mime_type="text/plain", size_bytes=10, storage_key="doc.txt"
    )
    chunk = Chunk(document=document, content="text", chunk_index=0)
    db_session.add(document)
    db_session.commit()
    chunk_id = chunk.id

    document.chunks.remove(chunk)
    db_session.commit()

    assert db_session.get(Chunk, chunk_id) is None
    # The document itself survives -- only the orphaned chunk is gone.
    assert db_session.get(Document, document.id) is not None


def test_removing_a_message_from_threads_messages_collection_deletes_its_row(db_session) -> None:
    thread = Thread()
    message = Message(thread=thread, role="user", content="hello")
    db_session.add(thread)
    db_session.commit()
    message_id = message.id

    thread.messages.remove(message)
    db_session.commit()

    assert db_session.get(Message, message_id) is None
    assert db_session.get(Thread, thread.id) is not None


def test_removing_a_citation_from_messages_citations_collection_deletes_its_row(db_session) -> None:
    thread = Thread()
    message = Message(thread=thread, role="assistant", content="answer")
    citation = Citation(
        message=message,
        document_name="handbook.pdf",
        source_location="p.1",
        excerpt="some excerpt",
    )
    db_session.add(thread)
    db_session.commit()
    citation_id = citation.id

    message.citations.remove(citation)
    db_session.commit()

    assert db_session.get(Citation, citation_id) is None
    assert db_session.get(Message, message.id) is not None


# --- nullify: deleting just a chunk, not its document, orphans its citation -


def test_deleting_a_chunk_directly_nulls_its_citations_chunk_id_without_deleting_them(
    db_session,
) -> None:
    """`Chunk.citations` carries no delete cascade, so deleting a `Chunk` on
    its own (as opposed to deleting its whole `Document`, which removes the
    chunk via `Document.chunks`'s delete-orphan cascade first) leaves the
    `Citation` row in place with its `chunk_id` nulled out -- exactly the
    `ondelete="SET NULL"` the foreign key declares, and exactly what
    `CitationOut.from_citation`'s `document_available = chunk_id is not None`
    depends on."""
    document = Document(
        file_name="doc.txt", mime_type="text/plain", size_bytes=10, storage_key="doc.txt"
    )
    chunk = Chunk(document=document, content="exact text", chunk_index=0)
    thread = Thread()
    message = Message(thread=thread, role="assistant", content="answer")
    citation = Citation(
        message=message,
        chunk=chunk,
        document_name="doc.txt",
        source_location=None,
        excerpt="exact text",
    )
    db_session.add_all([document, thread, citation])
    db_session.commit()
    citation_id = citation.id

    db_session.delete(chunk)
    db_session.commit()

    reloaded = db_session.get(Citation, citation_id)
    assert reloaded is not None
    assert reloaded.chunk_id is None
    assert reloaded.excerpt == "exact text"
    # The document that owned the chunk is untouched by deleting the chunk alone.
    assert db_session.get(Document, document.id) is not None
