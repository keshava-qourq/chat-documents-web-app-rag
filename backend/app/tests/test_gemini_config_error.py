"""Tests for AC-067/AC-068: a missing or Gemini-rejected `GEMINI_API_KEY`
fails with a structured, named configuration error rather than a generic
one, and the key value is never surfaced anywhere.

Module-level behaviour (`app.embeddings`, `app.generation`) is exercised
directly; the chat endpoint's pre-flight check is exercised through its own
self-contained `TestClient`, independent of `backend/tests/conftest.py`, so
this file needs nothing outside `backend/app/`.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import embeddings, generation
from app.database import Base, get_db
from app.main import app
from app.models import Chunk, Document
from app.retrieval import RetrievedChunk, RetrievedContext

# --- shared fixtures -------------------------------------------------------


@pytest.fixture()
def client_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client, session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _seed_ready_document_with_chunk(db_session):
    document = Document(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_key="handbook.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content="Employees get 25 days of annual leave.",
        source_location="handbook.pdf, page 1",
        chunk_index=0,
        embedding=[1.0, 0.0],
    )
    db_session.add(chunk)
    db_session.commit()
    return document


class _RejectingModels:
    """Raises an exception shaped like google-genai's auth rejection."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        self.calls = 0

    def _raise(self):
        self.calls += 1
        error = RuntimeError(f"Gemini rejected the request (status {self.status_code})")
        error.status_code = self.status_code
        raise error

    def embed_content(self, model, contents):
        self._raise()

    def generate_content(self, model, contents):
        self._raise()

    def generate_content_stream(self, model, contents):
        self._raise()


def _install_fake_client(monkeypatch, module, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(module.genai, "Client", Factory())


def _chunk(content="text"):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="handbook.pdf, page 1",
        content=content,
        similarity=0.9,
    )


# --- AC-067: not configured --------------------------------------------------


def test_embed_texts_not_configured_names_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(embeddings.GeminiNotConfiguredError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert exc_info.value.code == "gemini_not_configured"


def test_generate_answer_not_configured_names_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError) as exc_info:
        generation.generate_answer("question", context)

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert exc_info.value.code == "gemini_not_configured"


# --- AC-067: Gemini rejects the key ------------------------------------------


def test_embed_texts_rejected_key_names_gemini_api_key_and_status(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    models = _RejectingModels(status_code=401)
    _install_fake_client(monkeypatch, embeddings, models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert "rejected" in str(exc_info.value).lower()
    assert "401" in str(exc_info.value)
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "gemini_key_rejected"
    assert models.calls == 1  # no retry spent on a key that cannot succeed


def test_generate_answer_rejected_key_names_gemini_api_key_and_status(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    models = _RejectingModels(status_code=403)
    _install_fake_client(monkeypatch, generation, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        generation.generate_answer("question", context)

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert "rejected" in str(exc_info.value).lower()
    assert "403" in str(exc_info.value)
    assert exc_info.value.status_code == 403


def test_stream_answer_rejected_key_raises_immediately(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    models = _RejectingModels(status_code=401)
    _install_fake_client(monkeypatch, generation, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError):
        list(generation.stream_answer("question", context))


# --- AC-068: key value never surfaces -----------------------------------


def test_rejected_key_error_never_includes_the_key_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    models = _RejectingModels(status_code=401)
    _install_fake_client(monkeypatch, embeddings, models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "super-secret-value" not in str(exc_info.value)


# --- chat endpoint pre-flight (contract 503 shape) --------------------------


def test_chat_endpoint_returns_structured_503_when_gemini_not_configured_and_docs_ready(
    client_db, monkeypatch
):
    client, db_session = client_db
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _seed_ready_document_with_chunk(db_session)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Gemini must not be called when GEMINI_API_KEY is unset")

    monkeypatch.setattr(embeddings, "embed_texts", fail_if_called)

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "gemini_not_configured"
    assert "GEMINI_API_KEY" in body["detail"]["message"]

    # No user turn was persisted either -- the check runs before any write.
    detail = client.get(f"/threads/{thread_id}").json()
    assert detail["messages"] == []


def test_chat_endpoint_answers_normally_without_key_when_no_ready_documents(client_db, monkeypatch):
    client, _db_session = client_db
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "Anything?"})

    # No ready documents yet -> request_answer's own canned, Gemini-free
    # reply applies; a missing key must not block this case.
    assert response.status_code == 200
