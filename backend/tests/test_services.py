"""Unit tests for `app.services`: service configuration reporting, thread
auto-titling, history trimming, the ready-documents existence check, and
`request_answer`'s own branches -- exercised directly against the function
with a bare `db` / `Thread` / `history`, not through
`POST /threads/{id}/messages`.

`backend/tests/test_chat_streaming.py` and `backend/app/tests/test_threads.py`
already exercise `request_answer` thoroughly end-to-end through the chat
endpoint (multiple token events before `final`, citation deduplication,
cross-thread isolation, long-history trimming, interrupted streams); this
file does not re-litigate those. Instead it covers what calling the HTTP
endpoint cannot reach directly -- `request_answer` called with no router
pre-flight check in front of it (so a missing `GEMINI_API_KEY` reaches the
function itself even with 'ready' documents present), branches that
endpoint-level coverage happens not to exercise (zero chunks above
threshold, a retrieval-layer exception, the streamed "not found" answer,
`GenerationServiceError`), and the pure helper functions (`derive_title`,
`trim_history`, `history_char_budget`, `has_ready_documents`,
`configured_services`) tested directly rather than only through the
behaviour they produce at the API.

Every Gemini call in this file either never happens (no `GEMINI_API_KEY`
set) or goes through a small fake installed on `app.generation.genai.Client`,
the same pattern `test_chat_streaming.py` and `test_generation.py` use.
Retrieval's own Gemini call (`embed_texts`) is monkeypatched on
`app.retrieval`, exactly as `test_retrieval.py` does. No live Gemini,
database, or MinIO call happens anywhere in this file.
"""

import json
import uuid

from app import generation, retrieval, services
from app.models import Chunk, Document, Message, Thread

# --- shared fixtures / helpers ---------------------------------------------


def _make_thread(db_session) -> Thread:
    thread = Thread()
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)
    return thread


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


def _sse_events(events_iterable) -> list[tuple[str, str]]:
    """Consumes `request_answer`'s generator into `(event, data)` pairs, in
    send order. Each item it yields is already one complete SSE block."""
    parsed: list[tuple[str, str]] = []
    for raw in events_iterable:
        event = "message"
        data = ""
        for line in raw.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        parsed.append((event, data))
    return parsed


class _FakeStreamChunk:
    def __init__(self, text):
        self.text = text


class _FakeStreamModels:
    """Records every prompt it is called to open a stream with (`calls`).
    Streams back `pieces` as plain-text deltas when `open_error` is `None`;
    otherwise raises `open_error` synchronously on every call, simulating
    every attempt to *open* the stream failing -- what exhausts
    `stream_answer`'s retries into a `GenerationServiceError`."""

    def __init__(self, pieces=None, open_error=None):
        self.pieces = pieces or []
        self.open_error = open_error
        self.calls: list[str] = []

    def generate_content_stream(self, model, contents):
        self.calls.append(contents)
        if self.open_error is not None:
            raise self.open_error
        return (_FakeStreamChunk(piece) for piece in self.pieces)


def _install_fake_stream_client(monkeypatch, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


# --- configured_services ----------------------------------------------------


def test_configured_services_reports_both_as_false_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert services.configured_services() == {"minio": False, "gemini": False}


def test_configured_services_reports_each_as_true_once_its_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert services.configured_services() == {"minio": True, "gemini": True}


# --- derive_title ------------------------------------------------------------


def test_derive_title_collapses_internal_whitespace() -> None:
    title = services.derive_title("What   is\tthe\n\nrefund policy?")

    assert title == "What is the refund policy?"


def test_derive_title_blank_or_whitespace_only_question_falls_back_to_new_conversation() -> None:
    assert services.derive_title("") == "New conversation"
    assert services.derive_title("   \n\t  ") == "New conversation"


def test_derive_title_exactly_at_max_length_is_returned_unchanged_with_no_ellipsis() -> None:
    text = "x" * 60

    title = services.derive_title(text)

    assert title == text
    assert "…" not in title


def test_derive_title_over_max_length_is_truncated_at_a_word_boundary_with_ellipsis() -> None:
    text = "word " * 13  # 65 chars, well past the limit, with word boundaries to cut at

    title = services.derive_title(text)

    assert len(title) <= 60
    assert title.endswith("…")
    assert not title.endswith(" …")  # the trailing space before the cut was trimmed


def test_derive_title_single_word_longer_than_the_limit_is_hard_cut() -> None:
    text = "x" * 100  # no word boundary at all to cut at

    title = services.derive_title(text)

    assert title == "x" * 59 + "…"
    assert len(title) == 60


def test_derive_title_respects_a_custom_max_length() -> None:
    title = services.derive_title("one two three four five", max_length=10)

    assert len(title) <= 10


# --- history_char_budget -----------------------------------------------------


def test_history_char_budget_reads_env_var_and_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("HISTORY_CHAR_BUDGET", raising=False)
    assert services.history_char_budget() == services.HISTORY_CHAR_BUDGET_DEFAULT

    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "500")
    assert services.history_char_budget() == 500


# --- trim_history -------------------------------------------------------------


def test_trim_history_of_an_empty_list_returns_an_empty_list(monkeypatch) -> None:
    monkeypatch.delenv("HISTORY_CHAR_BUDGET", raising=False)

    assert services.trim_history([]) == []


def test_trim_history_keeps_everything_under_budget_in_original_order(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "1000")
    history = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]

    assert services.trim_history(history) == history


def test_trim_history_keeps_the_single_most_recent_turn_even_if_it_alone_exceeds_budget(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "5")
    history = [
        {"role": "user", "content": "short"},
        {"role": "assistant", "content": "x" * 50},
    ]

    trimmed = services.trim_history(history)

    assert trimmed == [{"role": "assistant", "content": "x" * 50}]


def test_trim_history_drops_oldest_turns_once_the_budget_would_be_exceeded(monkeypatch) -> None:
    monkeypatch.setenv("HISTORY_CHAR_BUDGET", "12")
    history = [
        {"role": "user", "content": "oldest-marker"},  # 13 chars -- dropped
        {"role": "assistant", "content": "kept"},  # 4 chars
        {"role": "user", "content": "newest"},  # 6 chars
    ]

    trimmed = services.trim_history(history)

    assert trimmed == [
        {"role": "assistant", "content": "kept"},
        {"role": "user", "content": "newest"},
    ]


# --- has_ready_documents -------------------------------------------------------


def test_has_ready_documents_is_false_when_the_library_is_empty(db_session) -> None:
    assert services.has_ready_documents(db_session) is False


def test_has_ready_documents_is_false_when_only_processing_or_failed_documents_exist(
    db_session,
) -> None:
    db_session.add(
        Document(
            id=uuid.uuid4(),
            file_name="a.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            storage_key="a.pdf",
            status="processing",
        )
    )
    db_session.add(
        Document(
            id=uuid.uuid4(),
            file_name="b.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            storage_key="b.pdf",
            status="failed",
        )
    )
    db_session.commit()

    assert services.has_ready_documents(db_session) is False


def test_has_ready_documents_is_true_once_one_document_is_ready(db_session) -> None:
    db_session.add(
        Document(
            id=uuid.uuid4(),
            file_name="c.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            storage_key="c.pdf",
            status="ready",
        )
    )
    db_session.commit()

    assert services.has_ready_documents(db_session) is True


# --- request_answer: no ready documents at all --------------------------------


def test_request_answer_with_no_ready_documents_streams_canned_message_and_persists_nothing(
    db_session,
) -> None:
    thread = _make_thread(db_session)

    events = _sse_events(services.request_answer(db_session, thread, "Anything?", []))

    assert [name for name, _ in events] == ["token", "final"]
    token_data = json.loads(events[0][1])
    assert token_data["text"] == generation.NO_DOCUMENTS_MESSAGE
    final_data = json.loads(events[1][1])
    assert final_data == {"message_id": None, "citations": []}
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0


# --- request_answer: ready documents, nothing above threshold -----------------


def test_request_answer_with_ready_documents_but_nothing_above_threshold_persists_a_complete_canned_answer(  # noqa: E501
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: 2.0)  # nothing qualifies
    thread = _make_thread(db_session)

    events = _sse_events(services.request_answer(db_session, thread, "Anything?", []))

    assert [name for name, _ in events] == ["token", "final"]
    final_data = json.loads(events[1][1])
    assert final_data["citations"] == []
    assert final_data["message_id"] is not None

    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.status == "complete"
    assert message.content == generation.NO_DOCUMENTS_MESSAGE


# --- request_answer: retrieval itself fails ------------------------------------


def test_request_answer_when_retrieval_raises_yields_an_error_event_and_persists_nothing(
    db_session, monkeypatch
) -> None:
    def boom(db, question):
        raise RuntimeError("retrieval backend unreachable")

    monkeypatch.setattr(services, "retrieve_context", boom)
    thread = _make_thread(db_session)

    events = _sse_events(services.request_answer(db_session, thread, "Anything?", []))

    assert [name for name, _ in events] == ["error"]
    data = json.loads(events[0][1])
    assert data["detail"] == "Could not retrieve context for this question."
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0


# --- request_answer: Gemini not configured, called directly -------------------
#
# `routers.threads.post_message` checks `gemini_api_key()` before ever calling
# `request_answer`, so an HTTP-level test can never reach this branch.
# Calling the service function directly, with no router in front of it, is
# the only way to prove it holds on its own.


def test_request_answer_without_gemini_api_key_yields_configuration_error_and_persists_nothing(
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    thread = _make_thread(db_session)

    events = _sse_events(
        services.request_answer(db_session, thread, "How many leave days?", [])
    )

    assert [name for name, _ in events] == ["error"]
    data = json.loads(events[0][1])
    assert data["detail"] == "Gemini is not configured."
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0


# --- request_answer: generation service unavailable ----------------------------


def test_request_answer_when_generation_service_is_unavailable_yields_service_error_and_persists_nothing(  # noqa: E501
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _FakeStreamModels(open_error=RuntimeError("boom"))
    _install_fake_stream_client(monkeypatch, models)
    thread = _make_thread(db_session)

    events = _sse_events(
        services.request_answer(db_session, thread, "How many leave days?", [])
    )

    assert [name for name, _ in events] == ["error"]
    data = json.loads(events[0][1])
    assert data["detail"] == "The answer generation service is unavailable."
    assert len(models.calls) == 2  # exactly the configured attempt count, no more
    assert db_session.query(Message).filter(Message.thread_id == thread.id).count() == 0


# --- request_answer: the streamed "not found" answer ---------------------------


def test_request_answer_not_found_answer_is_persisted_complete_with_no_citations(
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels(pieces=[generation.NOT_FOUND_MESSAGE])
    _install_fake_stream_client(monkeypatch, models)
    thread = _make_thread(db_session)

    events = _sse_events(
        services.request_answer(db_session, thread, "Unrelated question", [])
    )

    names = [name for name, _ in events]
    assert "token" in names
    assert names[-1] == "final"
    final_data = json.loads(next(data for name, data in events if name == "final"))
    assert final_data["citations"] == []

    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.status == "complete"
    assert generation.NOT_FOUND_PHRASE in message.content.lower()


def test_request_answer_empty_generated_text_persists_the_not_found_message(
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session)
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels(pieces=["   "])  # strips to nothing
    _install_fake_stream_client(monkeypatch, models)
    thread = _make_thread(db_session)

    events = _sse_events(
        services.request_answer(db_session, thread, "Unrelated question", [])
    )

    final_data = json.loads(next(data for name, data in events if name == "final"))
    assert final_data["citations"] == []
    message = db_session.query(Message).filter(Message.thread_id == thread.id).one()
    assert message.content == generation.NOT_FOUND_MESSAGE


# --- request_answer: the retrieval query is augmented with recent history -----


def test_request_answer_augments_the_retrieval_query_with_recent_history(
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session, content="Employees get 25 days of annual leave.")
    seen_queries: list[list[str]] = []

    def record_embed(texts):
        seen_queries.append(texts)
        return [[1.0, 0.0]]

    monkeypatch.setattr(retrieval, "embed_texts", record_embed)
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels(pieces=["Employees get 25 days of annual leave."])
    _install_fake_stream_client(monkeypatch, models)
    thread = _make_thread(db_session)
    history = [
        {"role": "user", "content": "How much annual leave is there?"},
        {"role": "assistant", "content": "Employees get 25 days of annual leave."},
    ]

    list(
        services.request_answer(
            db_session, thread, "And what about the Berlin office?", history
        )
    )

    assert len(seen_queries) == 1
    [augmented_query] = seen_queries[0]
    assert "How much annual leave is there?" in augmented_query
    assert "Employees get 25 days of annual leave." in augmented_query
    assert "And what about the Berlin office?" in augmented_query


def test_request_answer_uses_the_bare_question_as_the_retrieval_query_when_there_is_no_history(
    db_session, monkeypatch
) -> None:
    _seed_ready_document_with_chunk(db_session)
    seen_queries: list[list[str]] = []

    def record_embed(texts):
        seen_queries.append(texts)
        return [[1.0, 0.0]]

    monkeypatch.setattr(retrieval, "embed_texts", record_embed)
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels(pieces=["An answer."])
    _install_fake_stream_client(monkeypatch, models)
    thread = _make_thread(db_session)

    list(services.request_answer(db_session, thread, "A fresh question", []))

    assert seen_queries == [["A fresh question"]]
