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
def db_session(db_sessionmaker):
    """A session on the same in-memory database the `client` fixture serves,
    for tests that need to set up state (e.g. a failed document) the API
    itself has no route to create.

    `client` reuses this exact session (rather than opening a second one of
    its own) for every request it makes during the test. With
    `expire_on_commit=False`, a second, independent session would keep
    serving a test's own earlier reads straight out of its identity map even
    after `client` committed a delete on a different session -- the delete
    would be real in the database but invisible to the test's assertions
    against `db_session`. Sharing one session removes that seam: a commit
    made through `client` is a commit made through this very session, so the
    next read from it reflects that commit immediately.
    """
    session = db_sessionmaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session, fake_object_store):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
