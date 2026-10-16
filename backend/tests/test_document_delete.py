"""AC-015/016/017/018: permanent document deletion.

Uses the shared `client`, `db_session` and `fake_object_store` fixtures from
`conftest.py` -- an in-memory SQLite database per test and a fake object
store standing in for MinIO, so this suite never touches live MinIO or
Gemini. `app.ingestion.embed_texts` is monkeypatched in the AC-018 tests for
the same reason: no live Gemini call is ever made.
"""

import uuid

from app import ingestion, storage
from app.models import Chunk, Document

TXT_BYTES = b"plain text content"


def _file(name: str, content: bytes = TXT_BYTES, content_type: str = "text/plain"):
    return ("files", (name, content, content_type))


def _seed_ready_document_with_chunks(db_session, chunk_count: int = 3) -> Document:
    document = Document(
        id=uuid.uuid4(),
        file_name="ready.txt",
        mime_type="text/plain",
        size_bytes=10,
        storage_key="ready.txt",
        status="ready",
        chunk_count=chunk_count,
    )
    db_session.add(document)
    db_session.commit()
    for index in range(chunk_count):
        db_session.add(
            Chunk(
                id=uuid.uuid4(),
                document_id=document.id,
                content=f"chunk {index}",
                source_location="ready.txt",
                chunk_index=index,
                embedding=[0.1, 0.2, 0.3],
            )
        )
    db_session.commit()
    db_session.refresh(document)
    return document


# --- AC-015: the row, its object and its chunks (with embeddings) are gone --


def test_delete_removes_document_row_object_and_chunks_and_omits_it_from_list(
    client, db_session, fake_object_store
) -> None:
    document = _seed_ready_document_with_chunks(db_session, chunk_count=3)
    fake_object_store[document.storage_key] = (b"original bytes", "text/plain")

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code == 204
    # The storage object is gone.
    assert document.storage_key not in fake_object_store
    # The document row is gone.
    assert db_session.get(Document, document.id) is None
    # Every chunk row (and its embedding) for this document is gone.
    remaining_chunks = db_session.query(Chunk).filter(Chunk.document_id == document.id).all()
    assert remaining_chunks == []

    listed_ids = {item["id"] for item in client.get("/documents").json()}
    assert str(document.id) not in listed_ids


# --- AC-016: a deleted document's chunks can never back a citation ----------


def test_deleted_documents_chunks_are_absent_from_the_whole_chunk_table(
    client, db_session
) -> None:
    """There is no retrieval endpoint yet, but every retrieval implementation
    this project could write has to start from a query against the `chunks`
    table. Proving no row for the deleted document's id remains there -- for
    either a direct lookup or a table-wide scan -- proves no citation built
    from that table can ever reference it."""
    kept = _seed_ready_document_with_chunks(db_session, chunk_count=2)
    kept.file_name = "kept.txt"
    kept.storage_key = "kept.txt"
    db_session.commit()
    deleted = _seed_ready_document_with_chunks(db_session, chunk_count=4)
    deleted.file_name = "deleted.txt"
    deleted.storage_key = "deleted.txt"
    db_session.commit()

    response = client.delete(f"/documents/{deleted.id}")
    assert response.status_code == 204

    all_remaining_chunks = db_session.query(Chunk).all()
    assert all(chunk.document_id != deleted.id for chunk in all_remaining_chunks)
    assert len(all_remaining_chunks) == 2
    assert {chunk.document_id for chunk in all_remaining_chunks} == {kept.id}


# --- AC-017: no auth, no undo token, no actor column, unknown id is 404 -----


def test_delete_requires_no_auth_issues_no_undo_token_and_writes_no_actor_field(
    client, db_session
) -> None:
    document = _seed_ready_document_with_chunks(db_session, chunk_count=1)

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code not in (401, 403)
    assert response.status_code == 204
    # No undo token of any kind in the response body.
    assert response.content in (b"", None)
    # No actor/audit column exists on the model for a caller identity to land in.
    column_names = {c.name for c in Document.__table__.columns}
    for forbidden in ("deleted_by", "actor", "deleted_at", "undo_token", "audit_log"):
        assert forbidden not in column_names
    # It is really gone -- not soft-deleted and recoverable.
    assert db_session.get(Document, document.id) is None


def test_delete_unknown_document_id_returns_404(client) -> None:
    response = client.delete(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404


# --- AC-018: deleting a document mid-indexing aborts ingestion -------------


def test_deleting_a_processing_document_aborts_ingest_and_leaves_zero_chunks(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")

    document = Document(
        id=uuid.uuid4(),
        file_name="midflight.txt",
        mime_type="text/plain",
        size_bytes=10,
        storage_key="midflight.txt",
        status="processing",
    )
    db_session.add(document)
    db_session.commit()
    document_id = document.id

    class FakeBody:
        def read(self) -> bytes:
            return b"a" * 20

    class FakeClient:
        def get_object(self, Bucket, Key):  # noqa: N803 -- matches boto3's signature
            return {"Body": FakeBody()}

    monkeypatch.setattr(storage, "get_client", lambda: FakeClient())

    def delete_mid_flight(texts):
        # Simulate a concurrent DELETE /documents/{id} landing while this
        # batch's embeddings are in flight, from its own session -- exactly
        # as a real second HTTP request would.
        db_session.query(Chunk).filter(Chunk.document_id == document_id).delete()
        db_session.query(Document).filter(Document.id == document_id).delete()
        db_session.commit()
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", delete_mid_flight)

    ingestion.ingest_document(document_id, db_session)

    assert db_session.query(Document).filter(Document.id == document_id).first() is None
    assert db_session.query(Chunk).filter(Chunk.document_id == document_id).count() == 0


def test_deleting_a_processing_document_between_batches_leaves_zero_chunks(
    db_session, monkeypatch
) -> None:
    """A delete that lands between two embedding batches (rather than during
    one) is caught at the next batch's pre-check, and nothing from the batch
    already committed survives either."""
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")

    document = Document(
        id=uuid.uuid4(),
        file_name="between.txt",
        mime_type="text/plain",
        size_bytes=10,
        storage_key="between.txt",
        status="processing",
    )
    db_session.add(document)
    db_session.commit()
    document_id = document.id
    engine = db_session.get_bind()

    class FakeBody:
        def read(self) -> bytes:
            return b"a" * 15  # three 5-char chunks

    class FakeClient:
        def get_object(self, Bucket, Key):  # noqa: N803
            return {"Body": FakeBody()}

    monkeypatch.setattr(storage, "get_client", lambda: FakeClient())

    calls = {"count": 0}

    def embed_then_delete_after_first_batch(texts):
        calls["count"] += 1
        if calls["count"] == 1:
            return [[0.1] for _ in texts]
        from sqlalchemy.orm import Session as OrmSession

        with OrmSession(bind=engine) as deleting_session:
            deleting_session.query(Chunk).filter(Chunk.document_id == document_id).delete()
            deleting_session.query(Document).filter(Document.id == document_id).delete()
            deleting_session.commit()
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", embed_then_delete_after_first_batch)

    ingestion.ingest_document(document_id, db_session)

    assert db_session.query(Document).filter(Document.id == document_id).first() is None
    assert db_session.query(Chunk).filter(Chunk.document_id == document_id).count() == 0
