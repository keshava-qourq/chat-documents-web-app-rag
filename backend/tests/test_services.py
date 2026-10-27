"""Unit tests for `app.services`: title derivation, the history-trimming
budget, the ready-documents existence check, and `request_answer`'s own
branching -- the no-ready-documents canned reply, a retrieval failure, the
ready-but-nothing-above-threshold reply, the not-found-phrase reply, and a
mid-stream failure from each of Gemini's typed errors -- independently of
the router that calls it and independently of `app.generation` /
`app.retrieval`'s own internals (already covered by their own test
modules).

`request_answer` is exercised by calling it directly against its own
in-memory SQLite engine (the same pattern `test_retrieval.py` and
`test_gemini_config_error.py` use for module-level calls rather than the
shared `conftest.py` `client` fixture), with `app.services.retrieve_context`
and `app.services.stream_answer` monkeypatched at the names `services`
itself calls them by -- so these are unit tests of the orchestration this
module adds (what gets persisted, what gets streamed, when the thread's
`last_active_at` moves), not a second copy of `test_chat_streaming.py`'s
end-to-end, Gemini-client-level coverage of the same seam.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import services
from app.database import Base
from app.generation import (
    NO_DOCUMENTS_MESSAGE,
    NOT_FOUND_MESSAGE,
    GeminiNotConfiguredError,
    GenerationServiceError,
)
from app.models import Document, Message, Thread
from app.retrieval import RetrievedChunk, RetrievedContext

# --- fixtures and small helpers --------------------------------------------


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


_SENTINEL_PAST = datetime(2020, 1, 1, tzinfo=UTC)


def _make_thread(db_session) -> Thread:
    thread = Thread(id=uuid.uuid4(), last_active_at=_SENTINEL_PAST)
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)
    return thread


def _make_document(db_session, status: str, file_name: str = "handbook.pdf") -> Document:
    document = Document(
        id=uuid.uuid4(),
        file_name=file_name,
        mime_type="application/pdf",
        size_bytes=10,
        storage_key=f"{uuid.uuid4()}.pdf",
        status=status,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _chunk(document_name="handbook.pdf", source_location="handbook.pdf, page 1", content="text"):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        source_location=source_location,
        content=content,
        similarity=0.9,
    )


def _parse_events(pieces: list[str]) -> list[tuple[str, dict | None]]:
    """Parses the raw SSE strings `request_answer` yields -- one `_sse(...)`
    call produces exactly one such string -- into `(event, data)` pairs."""
    events = []
    for piece in pieces:
        event = "message"
        data_line = ""
        for line in piece.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_line = line[len("data:") :].strip()
        events.append((event, json.loads(data_line) if data_line else None))
    return events


def _fake_stream(pieces, error=None):
    def _stream(question, context, history):
        yield from pieces
        if error is not None:
            raise error

    return _stream


# --- derive_title ------------------------------------------------------


def test_derive_title_blank_or_whitespace_only_question_yields_new_conversation():
    assert services.derive_title("") == "New conversation"
    assert services.derive_title("   \n\t  ") == "New conversation"


def test_derive_title_collapses_internal_whitespace():
    assert services.derive_title("What   is\tthe   policy?\n") == "What is the policy?"


def test_derive_title_short_question_is_returned_unchanged():
    question = "How many vacation days do I get?"
    assert services.derive_title(question) == question


def test_derive_title_exactly_at_max_length_is_unchanged():
    question = "x" * services.TITLE_MAX_LENGTH
    title = services.derive_title(question)
    assert title == question
    assert len(title) == services.TITLE_MAX_LENGTH


def test_derive_title_truncates_at_the_last_whole_word_and_appends_ellipsis():
    question = "What is the per diem for staff travelling to the Berlin office this quarter?"
    title = services.derive_title(question)

    assert len(title) <= services.TITLE_MAX_LENGTH
    assert title.endswith("…")
    assert not title[:-1].endswith(" ")  # trailing space trimmed before the ellipsis
    # Truncated at a word boundary: the body (without ellipsis) is a prefix
    # of the original question made only of whole words.
    body = title[:-1]
    assert question.startswith(body)
    assert question[len(body)] == " " or len(body) == len(question)


def test_derive_title_hard_cuts_a_single_word_with_no_boundary_to_break_at():
    question = "supercalifragilisticexpialidocious" * 5  # one giant word, no spaces
    title = services.derive_title(question)

    assert len(title) == services.TITLE_MAX_LENGTH
    assert title.endswith("…")


@pytest.mark.parametrize(
    "length", [1, 10, services.TITLE_MAX_LENGTH - 1, services.TITLE_MAX_LENGTH, 61, 200, 1000]
)
def test_derive_title_result_never_exceeds_max_length(length):
    question = " ".join(["word"] * (length // 5 + 1))[:length] or "x"
    assert len(services.derive_title(question)) <= services.TITLE_MAX_LENGTH


# --- history_char_budget -------------------------------------------------


def test_history_char_budget_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("HISTORY_CHAR_BUDGET", raising=False)
    assert services.history_char_budget() == services.HISTORY_CHAR_BUDGET_DEFAULT


def test_history_char_budget_reads_the_environment_override(monkeypatch):
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "250")
    assert services.history_char_budget() == 250


# --- trim_history ----------------------------------------------------------


def test_trim_history_of_an_empty_list_returns_an_empty_list(monkeypatch):
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "1000")
    assert services.trim_history([]) == []


def test_trim_history_keeps_every_turn_when_all_fit_under_budget(monkeypatch):
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "1000")
    history = [
        {"role": "user", "content": "short question"},
        {"role": "assistant", "content": "short answer"},
    ]
    assert services.trim_history(history) == history


def test_trim_history_always_keeps_the_single_most_recent_turn_even_if_it_alone_exceeds_budget(
    monkeypatch,
):
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "10")
    history = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "x" * 500},
    ]
    kept = services.trim_history(history)
    assert kept == [history[-1]]


def test_trim_history_drops_the_oldest_turns_once_the_running_total_would_exceed_budget(
    monkeypatch,
):
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "25")
    oldest = {"role": "user", "content": "x" * 20}
    middle = {"role": "assistant", "content": "y" * 10}
    newest = {"role": "user", "content": "z" * 10}
    kept = services.trim_history([oldest, middle, newest])

    # Newest-first filling means `oldest` cannot fit once `middle` + `newest`
    # are already in, and the result preserves chronological order.
    assert oldest not in kept
    assert kept == [middle, newest]


# --- has_ready_documents ---------------------------------------------------


def test_has_ready_documents_is_false_with_no_documents_at_all(db_session):
    assert services.has_ready_documents(db_session) is False


def test_has_ready_documents_is_false_when_only_processing_or_failed_documents_exist(db_session):
    _make_document(db_session, status="processing")
    _make_document(db_session, status="failed", file_name="other.pdf")
    assert services.has_ready_documents(db_session) is False


def test_has_ready_documents_is_true_once_a_ready_document_exists(db_session):
    _make_document(db_session, status="processing")
    _make_document(db_session, status="ready", file_name="handbook.pdf")
    assert services.has_ready_documents(db_session) is True


# --- configured_services ----------------------------------------------------


def test_configured_services_tracks_each_variable_independently(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = services.configured_services()

    assert result == {"minio": True, "gemini": False}


# --- request_answer: no ready documents at all -----------------------------


def test_request_answer_with_no_ready_documents_streams_canned_message_and_persists_nothing(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)
    monkeypatch.setattr(
        services,
        "retrieve_context",
        lambda db, question: RetrievedContext(chunks=[], has_ready_documents=False),
    )

    def fail_stream(*args, **kwargs):
        raise AssertionError("Gemini must not be called with no ready documents")

    monkeypatch.setattr(services, "stream_answer", fail_stream)

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    assert [name for name, _ in events] == ["token", "final"]
    assert events[0][1]["text"] == NO_DOCUMENTS_MESSAGE
    assert events[1][1] == {"message_id": None, "citations": []}

    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0
    db_session.refresh(thread)
    assert thread.last_active_at == _SENTINEL_PAST  # left untouched


# --- request_answer: retrieval itself fails --------------------------------


def test_request_answer_when_retrieval_raises_emits_only_an_error_event_and_persists_nothing(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)

    def fail_retrieve(db, question):
        raise RuntimeError("embedding service unreachable")

    monkeypatch.setattr(services, "retrieve_context", fail_retrieve)

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    assert [name for name, _ in events] == ["error"]
    assert "detail" in events[0][1]
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0


# --- request_answer: ready documents but nothing above threshold ----------


def test_request_answer_with_ready_documents_but_zero_chunks_persists_complete_ungrounded_message(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)
    monkeypatch.setattr(
        services,
        "retrieve_context",
        lambda db, question: RetrievedContext(chunks=[], has_ready_documents=True),
    )

    def fail_stream(*args, **kwargs):
        raise AssertionError("Gemini must not be called with no chunks above threshold")

    monkeypatch.setattr(services, "stream_answer", fail_stream)

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    assert [name for name, _ in events] == ["token", "final"]
    assert events[0][1]["text"] == NO_DOCUMENTS_MESSAGE
    final_data = events[1][1]
    assert final_data["message_id"] is not None
    assert final_data["citations"] == []

    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.role == "assistant"
    assert message.status == "complete"
    assert message.content == NO_DOCUMENTS_MESSAGE
    db_session.refresh(thread)
    assert thread.last_active_at > _SENTINEL_PAST


# --- request_answer: the not-found phrase is treated as ungrounded --------


def test_request_answer_not_found_phrase_persists_complete_message_with_no_citations(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", lambda db, question: context)
    monkeypatch.setattr(services, "stream_answer", _fake_stream([NOT_FOUND_MESSAGE]))

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    event_names = [name for name, _ in events]
    assert "token" in event_names
    assert event_names[-1] == "final"
    final_data = events[-1][1]
    assert final_data["citations"] == []

    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.status == "complete"
    assert message.content == NOT_FOUND_MESSAGE
    assert len(message.citations) == 0


# --- request_answer: a grounded answer persists message + citations -------


def test_request_answer_grounded_answer_persists_message_and_citation_and_advances_thread(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)
    context = RetrievedContext(
        chunks=[_chunk(content="Employees get 25 days.")], has_ready_documents=True
    )
    monkeypatch.setattr(services, "retrieve_context", lambda db, question: context)
    monkeypatch.setattr(services, "stream_answer", _fake_stream(["Employees ", "get 25 days."]))

    events = _parse_events(
        list(services.request_answer(db_session, thread, "How many leave days?", []))
    )

    event_names = [name for name, _ in events]
    assert event_names.count("token") == 2
    assert event_names[-1] == "final"
    final_data = events[-1][1]
    assert final_data["message_id"] is not None
    assert len(final_data["citations"]) == 1
    assert final_data["citations"][0]["document_available"] is True

    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.status == "complete"
    assert message.content == "Employees get 25 days."
    db_session.refresh(thread)
    assert thread.last_active_at > _SENTINEL_PAST


# --- request_answer: a failure part-way through the stream ----------------


def test_request_answer_gemini_not_configured_mid_stream_persists_incomplete_and_emits_error(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", lambda db, question: context)
    monkeypatch.setattr(
        services,
        "stream_answer",
        _fake_stream(["Partial answer"], error=GeminiNotConfiguredError("no key")),
    )

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    event_names = [name for name, _ in events]
    assert "token" in event_names
    assert event_names[-1] == "error"
    assert "final" not in event_names

    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.status == "incomplete"
    assert message.content == "Partial answer"


def test_request_answer_generation_service_error_mid_stream_persists_incomplete_and_emits_error(
    db_session, monkeypatch
):
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", lambda db, question: context)
    monkeypatch.setattr(
        services,
        "stream_answer",
        _fake_stream(["Partial"], error=GenerationServiceError("boom")),
    )

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    assert [name for name, _ in events][-1] == "error"
    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.status == "incomplete"
    assert message.content == "Partial"


def test_request_answer_failure_before_any_token_persists_nothing(db_session, monkeypatch):
    thread = _make_thread(db_session)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    monkeypatch.setattr(services, "retrieve_context", lambda db, question: context)
    monkeypatch.setattr(
        services, "stream_answer", _fake_stream([], error=RuntimeError("never started"))
    )

    events = _parse_events(list(services.request_answer(db_session, thread, "Anything?", [])))

    assert [name for name, _ in events] == ["error"]
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0
