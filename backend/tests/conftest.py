"""Shared fixtures for the documents test suite.

Every test gets its own in-memory SQLite database (via a StaticPool so the
single in-memory connection is reused across the request-scoped sessions
FastAPI opens) and a fake object store in place of MinIO/boto3, so the suite
needs no live database server and no network access.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import storage
from app.database import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def _generous_rate_limits(monkeypatch):
    """The upload/chat limiters key on remote address, and TestClient always
    reports the same address, so without this every test shares one bucket
    and later tests start failing with 429s that have nothing to do with
    what they are checking."""
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1000000")
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "1000000")


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_sessionmaker(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def fake_object_store(monkeypatch):
    """Replaces the boto3-backed put/delete with an in-memory dict so no
    MinIO connection is ever attempted."""
    stored: dict[str, tuple[bytes, str]] = {}

    def fake_put_object(key: str, data: bytes, content_type: str) -> None:
        stored[key] = (data, content_type)

    def fake_delete_object(key: str) -> None:
        stored.pop(key, None)

    monkeypatch.setattr(storage, "put_object", fake_put_object)
    monkeypatch.setattr(storage, "delete_object", fake_delete_object)
    return stored


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
    """A session on the same in-memory database the `client` fixture serves,
    for tests that need to set up state (e.g. a failed document) the API
    itself has no route to create."""
    session = db_sessionmaker()
    try:
        yield session
    finally:
        session.close()
