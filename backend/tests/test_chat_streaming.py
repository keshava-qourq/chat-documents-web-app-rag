"""Streamed answers, thread-context follow-ups, history trimming and
citation serialisation (CHAT8EED1A-15-3 / AC-034..040).

Every Gemini call in this module goes through a fake installed on
`app.generation.genai.Client` -- `_FakeStreamModels`, via
`_install_fake_stream_client` -- which records the exact prompt string
handed to `generate_content_stream` so follow-up / cross-thread / history-
trimming assertions can be made directly against it. Retrieval's own
Gemini call (`embed_texts`) is monkeypatched on `app.retrieval` the same
way `test_retrieval.py` already does. Combined with the shared `client` /
`db_session` / `fake_object_store` fixtures from `conftest.py`, no live
Gemini, database, or MinIO call happens anywhere in this file.
"""

import json
import uuid

from app import generation, retrieval
from app.models import Chunk, Document


def _seed_ready_document_with_chunk(
    db_session,
    content: str = "Employees get 25 days of annual leave.",
    source_location: str = "handbook.pdf, page 1",
    file_name: str = "handbook.pdf",
):
    document = Document(
        id=uuid.uuid4(),
        file_name=file_name,
        mime_type="text/plain",
        size_bytes=10,
        storage_key=file_name,
        status="ready",
        chunk_count=1,
    )
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content=content,
        source_location=source_location,
        chunk_index=0,
        embedding=[1.0, 0.0],
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(document)
    db_session.refresh(chunk)
    return document, chunk


def _enable_retrieval(monkeypatch):
    """Makes retrieval deterministic and Gemini-free: a fixed query vector
    and a threshold low enough that every seeded chunk qualifies."""
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)


class _FakeStreamChunk:
    def __init__(self, text):
        self.text = text


class _FakeStreamModels:
    """Records every prompt it is called with (`calls`) and streams back
    `pieces` as plain-text deltas, optionally raising `error` once they are
    exhausted to simulate a mid-stream interruption. `pieces` can be
    mutated between calls to script a different answer for a later
    request on the same fake."""

    def __init__(self, pieces, error=None):
        self.pieces = pieces
        self.error = error
        self.calls: list[str] = []

    def generate_content_stream(self, model, contents):
        self.calls.append(contents)
        return self._gen()

    def _gen(self):
        for piece in self.pieces:
            yield _FakeStreamChunk(piece)
        if self.error is not None:
            raise self.error


def _install_fake_stream_client(monkeypatch, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


def _setup_chat(client, monkeypatch, pieces=None, error=None):
    _enable_retrieval(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels(
        pieces or ["Employees get ", "25 days of annual leave."], error=error
    )
    _install_fake_stream_client(monkeypatch, models)
    return models


def _sse_events(text: str) -> list[tuple[str, str]]:
    """Parses a raw SSE body into `(event, data)` pairs, in send order."""
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


# --- AC-035: multiple token events before final ----------------------------


def test_post_message_streams_multiple_token_events_before_final(client, db_session, monkeypatch):
    _seed_ready_document_with_chunk(db_session)
    _setup_chat(client, monkeypatch, pieces=["Employees get ", "25 days ", "of annual leave."])
    thread_id = client.post("/threads").json()["id"]

    response = client.post(
        f"/threads/{thread_id}/messages", json={"question": "How many leave days?"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(response.text)
    event_names = [name for name, _ in events]
    assert event_names.count("token") >= 2
    assert event_names[-1] == "final"
    assert event_names.index("final") > event_names.index("token")


# --- AC-036: completed stream persists complete message + deduped citations


def test_completed_stream_persists_complete_message_and_deduplicated_citations(
    client, db_session, monkeypatch
):
    document, chunk = _seed_ready_document_with_chunk(
        db_session, content="Employees get 25 days of annual leave."
    )
    duplicate_chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content="Employees get 25 days of annual leave.",
        source_location=chunk.source_location,  # same (doc, location) as `chunk`
        chunk_index=1,
        embedding=[1.0, 0.0],
    )
    db_session.add(duplicate_chunk)
    db_session.commit()
    monkeypatch.setattr(retrieval, "retrieval_top_k", lambda: 10)
    _setup_chat(client, monkeypatch, pieces=["Employees get 25 days of annual leave."])
    thread_id = client.post("/threads").json()["id"]

    response = client.post(
        f"/threads/{thread_id}/messages", json={"question": "How many leave days?"}
    )

    assert response.status_code == 200
    events = _sse_events(response.text)
    final_data = json.loads(next(data for name, data in events if name == "final"))
    assert len(final_data["citations"]) == 1  # the duplicate (doc, location) collapsed

    detail = client.get(f"/threads/{thread_id}").json()
    assistant = next(m for m in detail["messages"] if m["role"] == "assistant")
    assert assistant["status"] == "complete"
    assert assistant["content"] == "Employees get 25 days of annual leave."
    assert len(assistant["citations"]) == 1
    citation = assistant["citations"][0]
    assert citation["document_name"] == document.file_name
    assert citation["excerpt"] == chunk.content


# --- AC-037: interrupted stream leaves thread readable, answer incomplete --


def test_interrupted_stream_persists_incomplete_message_and_thread_accepts_another_question(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    _setup_chat(
        client,
        monkeypatch,
        pieces=["Here is a partial answer"],
        error=RuntimeError("stream broke"),
    )
    thread_id = client.post("/threads").json()["id"]

    response = client.post(
        f"/threads/{thread_id}/messages", json={"question": "How many leave days?"}
    )

    assert response.status_code == 200
    event_names = [name for name, _ in _sse_events(response.text)]
    assert "token" in event_names
    assert "error" in event_names
    assert "final" not in event_names

    detail = client.get(f"/threads/{thread_id}")
    assert detail.status_code == 200
    assistant = next(m for m in detail.json()["messages"] if m["role"] == "assistant")
    assert assistant["status"] == "incomplete"
    assert assistant["content"] == "Here is a partial answer"

    # A subsequent question on the same thread still succeeds.
    models = _FakeStreamModels(["A fresh, complete answer."])
    _install_fake_stream_client(monkeypatch, models)
    second_response = client.post(f"/threads/{thread_id}/messages", json={"question": "Ask again"})

    assert second_response.status_code == 200
    second_event_names = [name for name, _ in _sse_events(second_response.text)]
    assert "final" in second_event_names
    detail_after = client.get(f"/threads/{thread_id}").json()
    assistants_after = [m for m in detail_after["messages"] if m["role"] == "assistant"]
    assert assistants_after[-1]["status"] == "complete"


# --- AC-038: a follow-up passes prior turns to retrieval and generation ----


def test_follow_up_question_passes_prior_turns_to_generation_prompt(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    models = _setup_chat(client, monkeypatch, pieces=["Employees get 25 days of annual leave."])
    thread_id = client.post("/threads").json()["id"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "How many leave days?"})

    models.pieces = ["And the Berlin office closes for 2 weeks."]
    client.post(
        f"/threads/{thread_id}/messages",
        json={"question": "What about the Berlin office closure?"},
    )

    assert len(models.calls) == 2
    second_prompt = models.calls[1]
    assert "How many leave days?" in second_prompt
    assert "Employees get 25 days of annual leave." in second_prompt
    assert "What about the Berlin office closure?" in second_prompt


# --- AC-039: a brand-new thread carries no turns from any other thread ----


def test_new_thread_question_carries_no_turns_from_another_thread(client, db_session, monkeypatch):
    _seed_ready_document_with_chunk(db_session)
    models = _setup_chat(client, monkeypatch, pieces=["Thread A's answer about leave."])
    thread_a = client.post("/threads").json()["id"]
    client.post(f"/threads/{thread_a}/messages", json={"question": "Thread A's secret question"})

    models.pieces = ["Thread B's answer."]
    thread_b = client.post("/threads").json()["id"]
    client.post(f"/threads/{thread_b}/messages", json={"question": "Thread B's question"})

    second_prompt = models.calls[-1]
    assert "Thread A's secret question" not in second_prompt
    assert "Thread A's answer about leave." not in second_prompt
    assert "Thread B's question" in second_prompt


# --- AC-040: a long thread is trimmed to a bounded history, still answers --


def test_long_thread_history_is_trimmed_before_the_generation_call_and_still_answers(
    client, db_session, monkeypatch
):
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "200")
    models = _setup_chat(client, monkeypatch, pieces=["First answer."])
    thread_id = client.post("/threads").json()["id"]

    oldest_marker = "OLDEST-TURN-MARKER-" + "x" * 100
    client.post(f"/threads/{thread_id}/messages", json={"question": oldest_marker})

    for i in range(3):
        models.pieces = [f"Answer {i}."]
        client.post(
            f"/threads/{thread_id}/messages",
            json={"question": f"Padding question number {i} " + "y" * 60},
        )

    newest_question = "What is the newest, most recent question here?"
    models.pieces = ["Final answer."]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": newest_question})

    assert response.status_code == 200
    assert "final" in [name for name, _ in _sse_events(response.text)]
    final_prompt = models.calls[-1]
    assert oldest_marker not in final_prompt
    assert newest_question in final_prompt


# --- AC-034 (backend half): exact excerpt text, deleted-doc citation -------


def test_citation_keeps_exact_chunk_text_and_deleted_document_serialises_unavailable(
    client, db_session, monkeypatch
):
    document, chunk = _seed_ready_document_with_chunk(
        db_session, content="Exact chunk text preserved verbatim."
    )
    _setup_chat(client, monkeypatch, pieces=["Exact chunk text preserved verbatim."])
    thread_id = client.post("/threads").json()["id"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "What's the exact text?"})

    before_delete = client.get(f"/threads/{thread_id}").json()
    assistant = next(m for m in before_delete["messages"] if m["role"] == "assistant")
    citation = assistant["citations"][0]
    assert citation["excerpt"] == "Exact chunk text preserved verbatim."
    assert citation["document_available"] is True

    delete_response = client.delete(f"/documents/{document.id}")
    assert delete_response.status_code == 204

    after_delete = client.get(f"/threads/{thread_id}")
    assert after_delete.status_code == 200
    assistant_after = next(m for m in after_delete.json()["messages"] if m["role"] == "assistant")
    citation_after = assistant_after["citations"][0]
    assert citation_after["excerpt"] == "Exact chunk text preserved verbatim."
    assert citation_after["document_available"] is False
