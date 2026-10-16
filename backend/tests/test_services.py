"""Unit tests for `app.services`.

This ticket carries no acceptance criteria -- it is a direct unit-test pass
over `app/services.py` itself, reaching past what the integration-style
suites already prove through the API:

- `backend/tests/test_chat_streaming.py` drives `request_answer` end to end
  through `POST /threads/{id}/messages` for the happy paths (multiple
  tokens, deduplicated citations, a mid-stream interruption, follow-up
  history, cross-thread isolation, history trimming under a long thread).
- `backend/tests/test_threads.py` drives `derive_title` end to end through
  the same endpoint for the default title, first-question derivation and
  the 60-character truncation case.
- `backend/tests/test_health.py` drives `configured_services` end to end
  through `GET /health`.

What none of those reach, because driving it through the API would need an
HTTP round trip this module's own logic does not: `request_answer`'s other
branches (retrieval itself failing, the no-ready-documents canned reply
never being persisted, a ready library with nothing above threshold still
persisting a real answer, a mid-generation config/service error persisting
an incomplete turn with the right detail text, and the not-found/empty-
answer paths dropping citations even though context had chunks) -- and
`derive_title`'s / `trim_history`'s edge cases in isolation, independent of
any thread or endpoint.

Calls `app.services.request_answer` directly against a `Thread` row and a
hand-built `RetrievedContext` / fake `stream_answer`, the same way
`backend/app/tests/test_generation.py` already isolates `generate_answer`
and `stream_answer` from retrieval with a hand-built context. No live
Gemini, MinIO, or network access anywhere in this file: `db_session` is the
shared in-memory SQLite fixture from `conftest.py`, and every Gemini call
site (`retrieve_context`, `stream_answer`) is monkeypatched out.
"""

import json
import uuid

from app import generation, services
from app.models import Document, Message, Thread
from app.retrieval import RetrievedChunk, RetrievedContext


def _chunk(
    document_name: str = "handbook.pdf",
    source_location: str | None = "handbook.pdf, page 1",
    content: str = "Employees get 25 days of annual leave.",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        source_location=source_location,
        content=content,
        similarity=0.9,
    )


def _make_thread(db_session) -> Thread:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)
    return thread


def _make_document(db_session, status: str) -> Document:
    document = Document(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_key=f"{uuid.uuid4()}.pdf",
        status=status,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _sse_events(chunks: list[str]) -> list[tuple[str, str]]:
    """Parses the raw SSE strings `request_answer` yields into
    `(event, data)` pairs, in send order -- same wire format
    `backend/tests/test_chat_streaming.py` parses, reimplemented locally
    since this file exercises the generator directly rather than an HTTP
    response body."""
    events: list[tuple[str, str]] = []
    for raw in chunks:
        event = "message"
        data = ""
        for line in raw.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        events.append((event, data))
    return events


def _fake_retrieve(context: RetrievedContext):
    def _fn(db, query):
        return context

    return _fn


def _raising_stream(exc: Exception):
    def _fn(question, context, history):
        raise exc

    return _fn


def _partial_then_raising_stream(pieces: list[str], exc: Exception):
    def _fn(question, context, history):
        def _gen():
            yield from pieces
            raise exc

        return _gen()

    return _fn


def _scripted_stream(pieces: list[str]):
    def _fn(question, context, history):
        return iter(pieces)

    return _fn


# --- configured_services ----------------------------------------------------


def test_configured_services_reports_false_for_every_service_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert services.configured_services() == {"minio": False, "gemini": False}


def test_configured_services_reports_true_once_each_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")

    assert services.configured_services() == {"minio": True, "gemini": True}


# --- derive_title ------------------------------------------------------------


def test_derive_title_collapses_internal_whitespace() -> None:
    assert services.derive_title("What   is\tthe\n policy?") == "What is the policy?"


def test_derive_title_on_blank_question_returns_new_conversation() -> None:
    assert services.derive_title("   ") == "New conversation"
    assert services.derive_title("") == "New conversation"


def test_derive_title_at_exactly_the_max_length_is_returned_verbatim() -> None:
    text = "x" * 60
    assert services.derive_title(text) == text


def test_derive_title_truncates_at_the_last_whole_word_and_appends_ellipsis() -> None:
    question = "supercalifragilisticexpialidocious " * 10
    title = services.derive_title(question.strip())

    assert len(title) <= 60
    assert title.endswith("…")
    assert not title[:-1].endswith(" ")  # trimmed, not left with trailing space
    assert "supercalifragilisticexpialidocious" in title


def test_derive_title_hard_cuts_a_single_word_with_no_space_in_the_limit() -> None:
    question = "x" * 100  # one unbroken word, far past the limit, no space anywhere

    title = services.derive_title(question)

    assert len(title) == 60
    assert title == "x" * 59 + "…"


def test_derive_title_respects_a_custom_max_length() -> None:
    title = services.derive_title("one two three four five six seven", max_length=10)

    assert len(title) <= 10
    assert title.endswith("…")


# --- history_char_budget / trim_history --------------------------------------


def test_history_char_budget_defaults_to_the_documented_constant(monkeypatch) -> None:
    monkeypatch.delenv("HISTORY_CHAR_BUDGET", raising=False)

    assert services.history_char_budget() == services.HISTORY_CHAR_BUDGET_DEFAULT


def test_history_char_budget_is_read_from_its_own_env_var(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "42")

    assert services.history_char_budget() == 42


def test_trim_history_keeps_every_turn_once_the_total_is_under_budget(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "1000")
    history = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
    ]

    assert services.trim_history(history) == history


def test_trim_history_drops_oldest_turns_once_the_running_total_would_exceed_budget(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "20")
    oldest = {"role": "user", "content": "a" * 15}
    kept_one = {"role": "assistant", "content": "b" * 8}
    kept_two = {"role": "user", "content": "c" * 8}
    history = [oldest, kept_one, kept_two]

    trimmed = services.trim_history(history)

    assert oldest not in trimmed
    assert trimmed == [kept_one, kept_two]  # chronological order preserved


def test_trim_history_always_keeps_at_least_the_single_most_recent_turn(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "5")
    history = [
        {"role": "user", "content": "short"},
        {"role": "assistant", "content": "x" * 500},
    ]

    trimmed = services.trim_history(history)

    assert trimmed == [history[-1]]


def test_trim_history_of_empty_history_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "100")

    assert services.trim_history([]) == []


# --- has_ready_documents ------------------------------------------------------


def test_has_ready_documents_is_false_when_the_library_is_empty(db_session) -> None:
    assert services.has_ready_documents(db_session) is False


def test_has_ready_documents_is_false_when_only_a_processing_document_exists(db_session) -> None:
    _make_document(db_session, "processing")

    assert services.has_ready_documents(db_session) is False


def test_has_ready_documents_is_true_once_a_ready_document_exists(db_session) -> None:
    _make_document(db_session, "processing")
    _make_document(db_session, "ready")

    assert services.has_ready_documents(db_session) is True


def test_has_ready_documents_never_calls_embed_texts(db_session, monkeypatch) -> None:
    from app import retrieval

    def _fail_if_called(texts):
        raise AssertionError("has_ready_documents must not call embed_texts")

    monkeypatch.setattr(retrieval, "embed_texts", _fail_if_called)
    _make_document(db_session, "ready")

    assert services.has_ready_documents(db_session) is True


# --- request_answer: retrieval itself fails -----------------------------


def test_request_answer_emits_error_event_and_persists_nothing_when_retrieval_raises(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)

    def _raise(db, query):
        raise RuntimeError("embedding call failed")

    monkeypatch.setattr(services, "retrieve_context", _raise)

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    assert events == [
        ("error", json.dumps({"detail": "Could not retrieve context for this question."}))
    ]
    assert db_session.query(Message).count() == 0


# --- request_answer: no ready document anywhere --------------------------


def test_request_answer_streams_canned_reply_and_persists_no_message_with_no_ready_documents(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[], has_ready_documents=False)
    monkeypatch.setattr(services, "retrieve_context", _fake_retrieve(context))

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    assert [name for name, _ in events] == ["token", "final"]
    token_data = json.loads(events[0][1])
    assert token_data["text"] == generation.NO_DOCUMENTS_MESSAGE
    final_data = json.loads(events[1][1])
    assert final_data == {"message_id": None, "citations": []}
    assert db_session.query(Message).count() == 0


# --- request_answer: ready library, nothing scores above threshold -------


def test_request_answer_persists_a_real_message_when_ready_but_no_chunks_score_above_threshold(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", _fake_retrieve(context))

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    assert [name for name, _ in events] == ["token", "final"]
    final_data = json.loads(events[1][1])
    assert final_data["message_id"] is not None
    assert final_data["citations"] == []

    message = db_session.query(Message).filter(Message.role == "assistant").one()
    assert message.status == "complete"
    assert message.content == generation.NO_DOCUMENTS_MESSAGE


# --- request_answer: Gemini not configured, discovered mid-generation ----


def test_request_answer_persists_nothing_and_emits_error_when_gemini_not_configured(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", _fake_retrieve(context))
    monkeypatch.setattr(
        services,
        "stream_answer",
        _raising_stream(generation.GeminiNotConfiguredError("GEMINI_API_KEY is not configured")),
    )

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    assert events == [("error", json.dumps({"detail": "Gemini is not configured."}))]
    assert db_session.query(Message).count() == 0


# --- request_answer: GenerationServiceError after partial output --------


def test_request_answer_persists_incomplete_message_when_generation_service_errors_mid_stream(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", _fake_retrieve(context))
    monkeypatch.setattr(
        services,
        "stream_answer",
        _partial_then_raising_stream(
            ["Here is a part", "ial answer"],
            generation.GenerationServiceError("exhausted"),
        ),
    )

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    event_names = [name for name, _ in events]
    assert event_names.count("token") == 2
    assert event_names[-1] == "error"
    detail = json.loads(events[-1][1])
    assert detail == {"detail": "The answer generation service is unavailable."}

    message = db_session.query(Message).filter(Message.role == "assistant").one()
    assert message.status == "incomplete"
    assert message.content == "Here is a partial answer"


# --- request_answer: not-found phrase drops citations despite context ----


def test_request_answer_persists_complete_message_with_no_citations_for_a_not_found_answer(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", _fake_retrieve(context))
    monkeypatch.setattr(
        services, "stream_answer", _scripted_stream([generation.NOT_FOUND_MESSAGE])
    )

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    assert [name for name, _ in events][-1] == "final"
    final_data = json.loads(events[-1][1])
    assert final_data["citations"] == []  # dropped even though context had a chunk

    message = db_session.query(Message).filter(Message.role == "assistant").one()
    assert message.status == "complete"
    assert message.content == generation.NOT_FOUND_MESSAGE


# --- request_answer: an empty generated answer is treated the same way --


def test_request_answer_persists_the_not_found_message_when_gemini_returns_nothing(
    db_session, monkeypatch
) -> None:
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", _fake_retrieve(context))
    monkeypatch.setattr(services, "stream_answer", _scripted_stream([]))

    events = _sse_events(list(services.request_answer(db_session, thread, "question?", [])))

    assert [name for name, _ in events][-1] == "final"
    final_data = json.loads(events[-1][1])
    assert final_data["citations"] == []

    message = db_session.query(Message).filter(Message.role == "assistant").one()
    assert message.status == "complete"
    assert message.content == generation.NOT_FOUND_MESSAGE
