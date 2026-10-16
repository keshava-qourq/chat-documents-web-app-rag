"""Tests hardening `DELETE /documents/{id}`: full removal (row, object,
chunks), invisibility to retrieval, no auth/audit surface, and cancellation
of a document still mid-indexing.

Lives under `backend/app/tests/` (not `backend/tests/`) because this
change's `files_in_scope` is restricted to `backend/app/`. Builds its own
fixtures rather than importing `backend/tests/conftest.py`, which this
change has no write access to.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ingestion, models, storage
from app.database import Base, get_db
from app.main import app
from app.models import Chunk, Document


@pytest.fixture(autouse=True)
def _generous_rate_limits(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1000000")
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "1000000")


@pytest.fixture()
def db_sessionmaker():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def fake_object_store(monkeypatch):
    stored: dict[str, tuple[bytes, str]] = {}
    calls = {"delete": 0}

    def fake_put_object(key: str, data: bytes, content_type: str) -> None:
        stored[key] = (data, content_type)

    def fake_delete_object(key: str) -> None:
        calls["delete"] += 1
        stored.pop(key, None)

    monkeypatch.setattr(storage, "put_object", fake_put_object)
    monkeypatch.setattr(storage, "delete_object", fake_delete_object)
    return {"objects": stored, "calls": calls}


@pytest.fixture()
def client(db_sessionmaker, fake_object_store):
    def override_get_db():
        session = db_sessionmaker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def db_session(db_sessionmaker):
    session = db_sessionmaker()
    try:
        yield session
    finally:
        session.close()


def _seed_ready_document_with_chunks(db_session, chunk_count: int = 3) -> models.Document:
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
                embedding=[0.1, 0.2],
            )
        )
    db_session.commit()
    db_session.refresh(document)
    return document


# --- AC-015: full removal ----------------------------------------------------


def test_delete_removes_document_storage_object_and_chunks(
    client, db_session, fake_object_store
) -> None:
    document = _seed_ready_document_with_chunks(db_session, chunk_count=3)
    fake_object_store["objects"][document.storage_key] = (b"data", "text/plain")

    delete_response = client.delete(f"/documents/{document.id}")

    assert delete_response.status_code == 204
    assert fake_object_store["calls"]["delete"] == 1
    assert document.storage_key not in fake_object_store["objects"]

    assert db_session.get(Document, document.id) is None
    remaining_chunks = db_session.query(Chunk).filter(Chunk.document_id == document.id).count()
    assert remaining_chunks == 0

    list_response = client.get("/documents")
    assert all(item["id"] != str(document.id) for item in list_response.json())

    status_response = client.get(f"/documents/{document.id}/status")
    assert status_response.status_code == 404


# --- AC-017: no auth, no undo, no actor/audit column ------------------------


def test_delete_requires_no_authentication_and_leaves_no_audit_columns(client, db_session) -> None:
    document = _seed_ready_document_with_chunks(db_session, chunk_count=1)

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code not in (401, 403)
    assert response.status_code == 204
    # No undo: the row is really gone, not soft-deleted.
    assert db_session.get(Document, document.id) is None
    # No actor/audit columns exist on the model to have been written.
    column_names = {c.name for c in Document.__table__.columns}
    for forbidden in ("deleted_by", "actor", "deleted_at", "audit_log"):
        assert forbidden not in column_names


# --- unknown id / double delete ---------------------------------------------


def test_delete_unknown_id_returns_404(client) -> None:
    response = client.delete(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_twice_is_404_not_500(client, db_session) -> None:
    document = _seed_ready_document_with_chunks(db_session, chunk_count=1)

    first = client.delete(f"/documents/{document.id}")
    second = client.delete(f"/documents/{document.id}")

    assert first.status_code == 204
    assert second.status_code == 404


# --- AC-018: deleting a document still 'processing' stops ingestion --------


def test_deleting_a_processing_document_aborts_ingestion_with_zero_chunks(
    db_session, fake_object_store, monkeypatch
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
    engine = db_session.get_bind()

    class FakeBody:
        def read(self) -> bytes:
            return b"a" * 30

    class FakeClient:
        def get_object(self, Bucket, Key):  # noqa: N803
            return {"Body": FakeBody()}

    monkeypatch.setattr(storage, "get_client", lambda: FakeClient())

    calls = {"count": 0}

    def embed_then_delete(texts):
        calls["count"] += 1
        if calls["count"] == 2:
            # Simulate a concurrent DELETE /documents/{id} request running on
            # its own session while this batch is mid-flight.
            with OrmSession(bind=engine) as deleting_session:
                target = deleting_session.get(Document, document_id)
                deleting_session.delete(target)
                deleting_session.commit()
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", embed_then_delete)

    ingestion.ingest_document(document_id, db_session)

    assert db_session.query(Document).filter(Document.id == document_id).first() is None
    assert db_session.query(Chunk).filter(Chunk.document_id == document_id).count() == 0


def test_ingest_document_notices_deletion_before_persisting_a_batch(
    db_session, monkeypatch
) -> None:
    """If the document is deleted while a batch's embeddings are being
    computed, that batch is discarded rather than committed for a document
    that no longer exists."""
    document = Document(
        id=uuid.uuid4(),
        file_name="vanish.txt",
        mime_type="text/plain",
        size_bytes=10,
        storage_key="vanish.txt",
        status="processing",
    )
    db_session.add(document)
    db_session.commit()
    document_id = document.id

    class FakeBody:
        def read(self) -> bytes:
            return b"some content to embed and then vanish"

    class FakeClient:
        def get_object(self, Bucket, Key):  # noqa: N803
            return {"Body": FakeBody()}

    monkeypatch.setattr(storage, "get_client", lambda: FakeClient())

    def delete_during_embed(texts):
        db_session.query(Chunk).filter(Chunk.document_id == document_id).delete()
        db_session.query(Document).filter(Document.id == document_id).delete()
        db_session.commit()
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", delete_during_embed)

    ingestion.ingest_document(document_id, db_session)

    assert db_session.query(Chunk).filter(Chunk.document_id == document_id).count() == 0
    assert db_session.query(Document).filter(Document.id == document_id).first() is None
