"""Integration coverage for AC-067/AC-068 across the seam between
`app.embeddings` / `app.generation` (the subject of
`backend/app/tests/test_gemini_config_error.py`) and the chat endpoint's own
SSE flow (`app.services.request_answer`, `routers.threads.post_message`).

That sibling file already proves the typed errors are raised correctly at
the module level and that the chat endpoint's own pre-flight check turns a
*missing* `GEMINI_API_KEY` into a structured 503, before any Gemini call and
before the user's turn is persisted.
`backend/tests/test_gemini_error_handlers.py` separately proves the FastAPI
exception handlers registered for these errors turn into the same 503 shape
when raised directly from a dependency.

Neither proves what happens once `GEMINI_API_KEY` is *set* but Gemini itself
rejects it mid-conversation: the pre-flight check only asks whether the key
is configured at all (checking its validity would need a real Gemini call
on every message just to find out), so a rejected key can only ever be
discovered once `request_answer` actually tries to use it -- during
retrieval's embedding call, or during generation's streaming call -- deep
inside the SSE stream, where a structured JSON error can no longer be
returned and `app.services.request_answer`'s existing exception handling
(already proved generically, against a plain `RuntimeError`, in
`test_chat_streaming.py`) is the only thing standing between a rejected key
and a crashed response or a leaked key value.

This file proves that handling actually holds for `GeminiKeyRejectedError`
specifically, from both of the two call sites that can raise it during a
real chat turn: the stream still completes with a 200 and a graceful
`error` SSE event rather than a 500 or an unhandled exception, the
configured key value never appears anywhere in the response or in the
persisted thread, and the thread is left usable for a subsequent question
once the key works again.
"""

import json
import uuid

from app import generation
from app.embeddings import GeminiKeyRejectedError
from app.models import Chunk, Document

SECRET_KEY_VALUE = "super-secret-gemini-key-value"


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


def _sse_events(text: str) -> list[tuple[str, str]]:
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


class _RejectingStreamModels:
    """A fake Gemini `models` surface whose streaming call always fails the
    way google-genai surfaces an auth rejection (a `status_code` attribute
    on the raised exception), before yielding anything -- mirrors
    `_RejectingModels` in `app/tests/test_gemini_config_error.py`, kept
    local here so this file needs nothing outside `backend/tests/`."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        self.calls = 0

    def generate_content_stream(self, model, contents):
        self.calls += 1
        error = RuntimeError(f"Gemini rejected the request (status {self.status_code})")
        error.status_code = self.status_code
        raise error


def _install_fake_generation_client(monkeypatch, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


def _install_working_generation_client(monkeypatch, pieces):
    """A plain, successful fake stream client, for the "thread remains
    usable afterwards" half of each test below."""

    class _Chunk:
        def __init__(self, text):
            self.text = text

    class _WorkingModels:
        def generate_content_stream(self, model, contents):
            return (_Chunk(p) for p in pieces)

    _install_fake_generation_client(monkeypatch, _WorkingModels())


# --- rejected key discovered during retrieval's embedding call -------------


def test_rejected_key_during_retrieval_embedding_yields_graceful_sse_error_not_a_crash(
    client, db_session, monkeypatch
):
    from app import retrieval

    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("GEMINI_API_KEY", SECRET_KEY_VALUE)

    def fake_embed_texts(texts):
        # Mirrors the message `app.embeddings.embed_texts` itself builds --
        # it never includes the key value, only the fact of the rejection.
        raise GeminiKeyRejectedError(
            "GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401
        )

    # Simulates Gemini rejecting the configured key the moment retrieval
    # tries to embed the question -- after the endpoint's own pre-flight
    # check (which only checks the key is *set*, not that it is valid) has
    # already let the request through.
    monkeypatch.setattr(retrieval, "embed_texts", fake_embed_texts)

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    assert response.status_code == 200
    assert SECRET_KEY_VALUE not in response.text
    event_names = [name for name, _ in _sse_events(response.text)]
    assert "error" in event_names
    assert "final" not in event_names

    # The user's own question is still there; no assistant turn was
    # fabricated for a context that could not actually be retrieved.
    detail = client.get(f"/threads/{thread_id}").json()
    assert [m["role"] for m in detail["messages"]] == ["user"]
    assert SECRET_KEY_VALUE not in json.dumps(detail)

    # The thread still accepts another question once the key works again.
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    _install_working_generation_client(monkeypatch, ["It works now."])

    second_response = client.post(f"/threads/{thread_id}/messages", json={"question": "Again?"})

    assert second_response.status_code == 200
    second_event_names = [name for name, _ in _sse_events(second_response.text)]
    assert "final" in second_event_names


# --- rejected key discovered during generation's streaming call ------------


def test_rejected_key_during_generation_streaming_yields_graceful_sse_error_not_a_crash(
    client, db_session, monkeypatch
):
    from app import retrieval

    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("GEMINI_API_KEY", SECRET_KEY_VALUE)
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    models = _RejectingStreamModels(status_code=401)
    _install_fake_generation_client(monkeypatch, models)

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    assert response.status_code == 200
    assert SECRET_KEY_VALUE not in response.text
    event_names = [name for name, _ in _sse_events(response.text)]
    assert "error" in event_names
    assert "final" not in event_names
    assert models.calls == 1  # no retry spent on a key that cannot succeed

    # No partial tokens were ever produced (the rejection happens before the
    # stream opens), so no incomplete assistant turn was persisted either --
    # only the user's own question is there.
    detail = client.get(f"/threads/{thread_id}").json()
    assert [m["role"] for m in detail["messages"]] == ["user"]
    assert SECRET_KEY_VALUE not in json.dumps(detail)

    # The thread still accepts another question once the key works again.
    _install_working_generation_client(monkeypatch, ["It works now."])
    second_response = client.post(f"/threads/{thread_id}/messages", json={"question": "Again?"})

    assert second_response.status_code == 200
    second_event_names = [name for name, _ in _sse_events(second_response.text)]
    assert "final" in second_event_names
    final_detail = client.get(f"/threads/{thread_id}").json()
    assistants = [m for m in final_detail["messages"] if m["role"] == "assistant"]
    assert assistants[-1]["status"] == "complete"
