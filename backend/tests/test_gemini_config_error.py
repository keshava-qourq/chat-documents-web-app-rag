"""Integration tests for AC-067/AC-068: a Gemini-rejected `GEMINI_API_KEY`
(as opposed to a missing one) is handled as a structured, contained failure
through the *whole* chat pipeline -- not a crash, not a key leak -- and the
thread stays usable afterwards.

`backend/app/tests/test_gemini_config_error.py` (the dev's own unit suite)
already drives `app.embeddings.embed_texts` / `app.generation.generate_answer`
/ `stream_answer` directly, proving each typed error names `GEMINI_API_KEY`
and never the key value, and drives the chat endpoint's own pre-flight
check (missing key, checked before anything is persisted) with its own
self-contained client. What it cannot show from there is what a *set but
rejected* key does once it is past that pre-flight check -- it is detected
deep inside `app.services.request_answer`, at two different call sites
(retrieval's embedding call, and the generation call itself), each already
mid-stream with the user's own turn already persisted, and the router layer
never sees a `GeminiKeyRejectedError` at all (`request_answer` catches it
itself and emits an SSE 'error' event -- so `app.main`'s registered 503
handler for that class, which `test_main.py` already proves correct in
isolation, is never reached through this path).

Runs through the real router, the real `request_answer` seam and the real
SQLite-backed session via the shared `client` / `db_session` /
`fake_object_store` fixtures from `conftest.py` -- only the Gemini SDK
client itself is faked, the same way `test_chat_streaming.py` fakes it.
"""

import uuid

from app import embeddings, generation, retrieval
from app.models import Chunk, Document


def _seed_ready_document_with_chunk(
    db_session,
    content: str = "Employees get 25 days of annual leave.",
):
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
        content=content,
        source_location="handbook.pdf, page 1",
        chunk_index=0,
        embedding=[1.0, 0.0],
    )
    db_session.add(chunk)
    db_session.commit()
    return document


def _enable_retrieval(monkeypatch):
    """Makes retrieval deterministic and Gemini-free, the same way
    `test_chat_streaming._enable_retrieval` does -- used by the tests below
    that want the *generation* call site, not the embedding one, to be the
    one that rejects the key."""
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)


class _RejectingModels:
    """Raises an exception shaped like google-genai's auth rejection -- the
    same shape `app.embeddings._rejected_status` /
    `app.generation._rejected_status` detect (an int `status_code`
    attribute of 401 or 403)."""

    def __init__(self, status_code: int):
        self.status_code = status_code

    def _raise(self, *args, **kwargs):
        error = RuntimeError(f"Gemini rejected the request (status {self.status_code})")
        error.status_code = self.status_code
        raise error

    def embed_content(self, model, contents, config=None):
        self._raise()

    def generate_content_stream(self, model, contents):
        self._raise()


class _FakeStreamChunk:
    def __init__(self, text):
        self.text = text


class _WorkingModels:
    """A Gemini client that answers successfully -- used to prove a thread
    recovers after a rejected-key failure once the key (or the fake
    standing in for it) is good again."""

    def __init__(self, text):
        self._text = text

    def generate_content_stream(self, model, contents):
        return iter([_FakeStreamChunk(self._text)])


def _install_fake_client(monkeypatch, module, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(module.genai, "Client", Factory())


def _sse_events(text: str) -> list[tuple[str, str]]:
    """Parses a raw SSE body into `(event, data)` pairs, in send order --
    the same parser `test_chat_streaming.py` uses."""
    events: list[tuple[str, str]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        events.append((event, data))
    return events


# --- AC-067: a key Gemini rejects at the embedding (retrieval) call site --


def test_rejected_key_at_embedding_call_site_ends_in_sse_error_not_a_crash(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    _install_fake_client(monkeypatch, embeddings, _RejectingModels(status_code=401))

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    # Unlike the missing-key pre-flight (checked and rejected with a 503
    # before anything streams), a key Gemini actually rejects is only
    # discovered once streaming is already under way -- a status code can
    # no longer change, so this is a 200 SSE response carrying an error
    # event, not a 503.
    assert response.status_code == 200
    event_names = [name for name, _ in _sse_events(response.text)]
    assert "error" in event_names
    assert "final" not in event_names

    # The user's own turn was already persisted before retrieval ran, so it
    # survives the failure; no assistant turn was ever created for it.
    detail = client.get(f"/threads/{thread_id}").json()
    assert any(
        m["role"] == "user" and m["content"] == "How many days?" for m in detail["messages"]
    )
    assert not any(m["role"] == "assistant" for m in detail["messages"])


# --- AC-067: a key Gemini rejects at the generation call site -------------


def test_rejected_key_at_generation_call_site_ends_in_sse_error_not_a_crash(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    _enable_retrieval(monkeypatch)
    _install_fake_client(monkeypatch, generation, _RejectingModels(status_code=403))

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    assert response.status_code == 200
    event_names = [name for name, _ in _sse_events(response.text)]
    assert "error" in event_names
    assert "final" not in event_names

    detail = client.get(f"/threads/{thread_id}").json()
    assert any(m["role"] == "user" for m in detail["messages"])
    assert not any(m["role"] == "assistant" for m in detail["messages"])


# --- a rejected-key failure does not strand the thread --------------------


def test_thread_still_answers_a_later_question_after_a_rejected_key_error(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    _enable_retrieval(monkeypatch)
    _install_fake_client(monkeypatch, generation, _RejectingModels(status_code=401))

    thread_id = client.post("/threads").json()["id"]
    first = client.post(f"/threads/{thread_id}/messages", json={"question": "First question"})
    assert "error" in [name for name, _ in _sse_events(first.text)]

    _install_fake_client(
        monkeypatch, generation, _WorkingModels("Employees get 25 days of annual leave.")
    )
    second = client.post(f"/threads/{thread_id}/messages", json={"question": "Second question"})

    second_event_names = [name for name, _ in _sse_events(second.text)]
    assert "final" in second_event_names

    detail = client.get(f"/threads/{thread_id}").json()
    assistants = [m for m in detail["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 1  # only the recovered answer, none from the earlier failure
    assert assistants[-1]["status"] == "complete"
    assert assistants[-1]["content"] == "Employees get 25 days of annual leave."


# --- AC-068: the key value never reaches the client, through this path ----


def test_rejected_key_value_never_appears_in_the_full_sse_response_body(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    _install_fake_client(monkeypatch, embeddings, _RejectingModels(status_code=401))

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    assert "super-secret-value" not in response.text
