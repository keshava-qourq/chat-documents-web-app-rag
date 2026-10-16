"""Tests for the configured total document cap enforced on upload.

Lives under `backend/app/tests/` (not `backend/tests/`) because this change's
`files_in_scope` is restricted to `backend/app/`. Builds its own fixtures
rather than importing `backend/tests/conftest.py`, which this change has no
write access to.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import storage
from app.database import Base, get_db
from app.main import app
from app.models import Document

TXT_BYTES = b"plain text content"


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
    calls = {"put": 0}

    def fake_put_object(key: str, data: bytes, content_type: str) -> None:
        calls["put"] += 1
        stored[key] = (data, content_type)

    def fake_delete_object(key: str) -> None:
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


def _file(name: str, content: bytes = TXT_BYTES, content_type: str = "text/plain"):
    return ("files", (name, content, content_type))


def _seed_documents(db_session, count: int) -> None:
    for i in range(count):
        db_session.add(
            Document(
                id=uuid.uuid4(),
                file_name=f"existing-{i}.txt",
                mime_type="text/plain",
                size_bytes=10,
                storage_key=f"existing-{i}.txt",
                status="ready",
            )
        )
    db_session.commit()


def test_upload_rejected_with_cap_full_reason_when_library_is_at_cap(
    client, db_session, monkeypatch, fake_object_store
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "3")
    _seed_documents(db_session, 3)

    response = client.post("/documents", files=[_file("new.txt")])

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == []
    assert len(body["rejected"]) == 1
    rejected = body["rejected"][0]
    assert rejected["file_name"] == "new.txt"
    reason = rejected["reason"].lower()
    assert "full" in reason
    assert "delete" in reason


def test_cap_rejected_file_never_written_to_storage(
    client, db_session, monkeypatch, fake_object_store
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "1")
    _seed_documents(db_session, 1)

    client.post("/documents", files=[_file("never-stored.txt")])

    assert fake_object_store["calls"]["put"] == 0
    assert len(fake_object_store["objects"]) == 0


def test_cap_applies_within_the_same_batch_once_reached(
    client, db_session, monkeypatch, fake_object_store
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "2")
    _seed_documents(db_session, 1)

    response = client.post(
        "/documents",
        files=[_file("first.txt"), _file("second.txt")],
    )

    body = response.json()
    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["file_name"] == "first.txt"
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["file_name"] == "second.txt"
    assert "full" in body["rejected"][0]["reason"].lower()


def test_upload_succeeds_after_delete_brings_count_below_cap(
    client, db_session, monkeypatch, fake_object_store
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "1")
    _seed_documents(db_session, 1)
    existing_id = db_session.query(Document).first().id

    blocked = client.post("/documents", files=[_file("blocked.txt")])
    assert blocked.json()["rejected"][0]["file_name"] == "blocked.txt"

    delete_response = client.delete(f"/documents/{existing_id}")
    assert delete_response.status_code == 204

    accepted_response = client.post("/documents", files=[_file("now-allowed.txt")])
    body = accepted_response.json()
    assert body["rejected"] == []
    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["file_name"] == "now-allowed.txt"


def test_default_cap_is_two_hundred_when_document_cap_env_unset(
    client, db_session, monkeypatch, fake_object_store
) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    _seed_documents(db_session, 200)

    response = client.post("/documents", files=[_file("over-default-cap.txt")])

    body = response.json()
    assert body["accepted"] == []
    assert "full" in body["rejected"][0]["reason"].lower()


def test_document_cap_read_from_config_at_request_time(monkeypatch) -> None:
    from app.config import document_cap

    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    assert document_cap() == 200

    monkeypatch.setenv("DOCUMENT_CAP", "5")
    assert document_cap() == 5
