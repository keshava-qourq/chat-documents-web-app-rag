"""Unit tests for `app.generation`: both `generate_answer` and its
streaming counterpart `stream_answer`, exercised directly against the
module rather than through `POST /threads/{id}/messages` (which
`backend/tests/test_chat_streaming.py` already covers end-to-end, and which
this file does not re-litigate).

Every test here replaces `generation.genai.Client` with a small fake that
scripts a response or failure and records what it was called with, so no
test in this file makes a live Gemini call. There is already a hand-written
unit suite for this module under `backend/app/tests/` (`test_generation.py`,
`test_gemini_config_error.py`), but `backend/pytest.ini` sets
`testpaths = tests`, so that directory is never collected by the project's
own test run -- this file exists under `backend/tests/` precisely so
`app.generation` actually gets exercised by the suite that runs.
"""

import uuid

import pytest

from app import generation
from app.retrieval import RetrievedChunk, RetrievedContext


def _chunk(document_name="handbook.pdf", source_location="handbook.pdf, page 1", content="text"):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        source_location=source_location,
        content=content,
        similarity=0.9,
    )


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    """Scripts `generate_content`: each entry in `script` is either an
    exception to raise for that attempt, or response text to return.
    `calls` records the prompt passed on every attempt actually made, so a
    test can assert how many attempts were spent."""

    def __init__(self, script):
        self._script = list(script)
        self.calls: list[str] = []

    def generate_content(self, model, contents):
        self.calls.append(contents)
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class _FakeChunk:
    def __init__(self, text):
        self.text = text


class _FakeStreamModels:
    """Scripts `generate_content_stream`. Each entry in `script` is either
    an exception raised synchronously by the call itself (simulating a
    failure before the stream was ever opened, which `stream_answer`
    retries), or a list of plain-text pieces streamed back one at a time,
    optionally followed by `mid_stream_error` once exhausted (simulating an
    interruption after output has already begun, which is never retried).
    `calls` records the prompt passed on every attempt actually made to
    *open* the stream.
    """

    def __init__(self, script, mid_stream_error=None):
        self._script = list(script)
        self.mid_stream_error = mid_stream_error
        self.calls: list[str] = []

    def generate_content_stream(self, model, contents):
        self.calls.append(contents)
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return self._gen(item)

    def _gen(self, pieces):
        for piece in pieces:
            yield _FakeChunk(piece)
        if self.mid_stream_error is not None:
            raise self.mid_stream_error


def _install_fake_client(monkeypatch, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


# --- generate_answer: no context, never calls Gemini ------------------------


def test_generate_answer_with_no_ready_documents_returns_canned_message_without_calling_gemini(
    monkeypatch,
):
    def fail_client(api_key):
        raise AssertionError("Gemini must not be called with no ready documents")

    monkeypatch.setattr(generation.genai, "Client", fail_client)
    context = RetrievedContext(chunks=[], has_ready_documents=False)

    answer = generation.generate_answer("What is the policy?", context)

    assert answer.grounded is False
    assert answer.citations == []
    assert answer.content == generation.NO_DOCUMENTS_MESSAGE


def test_generate_answer_with_zero_chunks_above_threshold_also_skips_gemini(monkeypatch):
    def fail_client(api_key):
        raise AssertionError("Gemini must not be called")

    monkeypatch.setattr(generation.genai, "Client", fail_client)
    context = RetrievedContext(chunks=[], has_ready_documents=True)

    answer = generation.generate_answer("What is the policy?", context)

    assert answer.grounded is False
    assert answer.citations == []
    assert answer.content == generation.NO_DOCUMENTS_MESSAGE


# --- generate_answer: configuration and transient failures ------------------


def test_generate_answer_without_api_key_raises_typed_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError):
        generation.generate_answer("question", context)


def test_generate_answer_retries_a_transient_failure_and_succeeds(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _FakeModels(
        [RuntimeError("transient"), "Employees get 25 days of annual leave. [1]"]
    )
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert len(models.calls) == 2  # failed once, succeeded on retry
    assert answer.grounded is True
    assert answer.content == "Employees get 25 days of annual leave. [1]"


def test_generate_answer_exhausts_configured_retries_then_raises_typed_service_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _FakeModels([RuntimeError("boom"), RuntimeError("boom again")])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        generation.generate_answer("question", context)

    assert len(models.calls) == 2  # exactly the configured attempt count, no more


def test_generate_answer_rejected_key_raises_immediately_without_retrying(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    error = RuntimeError("Gemini rejected the request")
    error.status_code = 401
    models = _FakeModels([error, "should never be reached"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        generation.generate_answer("question", context)

    assert exc_info.value.status_code == 401
    assert len(models.calls) == 1  # no retry spent on a key that cannot succeed


# --- generate_answer: grounded output ---------------------------------------


def test_generate_answer_not_found_phrase_returns_ungrounded_answer_with_no_citations(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels([generation.NOT_FOUND_MESSAGE])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("unrelated question", context)

    assert answer.grounded is False
    assert answer.citations == []
    assert generation.NOT_FOUND_PHRASE in answer.content.lower()


def test_generate_answer_deduplicates_citations_by_document_and_location(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    chunk_one = _chunk(source_location="handbook.pdf, page 1")
    chunk_two = _chunk(source_location="handbook.pdf, page 1")  # same (doc, location)
    chunk_three = _chunk(source_location="handbook.pdf, page 2")
    context = RetrievedContext(
        chunks=[chunk_one, chunk_two, chunk_three], has_ready_documents=True
    )

    answer = generation.generate_answer("How many leave days?", context)

    assert answer.grounded is True
    locations = {(c.document_name, c.source_location) for c in answer.citations}
    assert locations == {
        ("handbook.pdf", "handbook.pdf, page 1"),
        ("handbook.pdf", "handbook.pdf, page 2"),
    }
    retrieved_ids = {c.chunk_id for c in context.chunks}
    for citation in answer.citations:
        assert citation.chunk_id in retrieved_ids


def test_generate_answer_citation_excerpt_is_capped_at_300_characters(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Answer. [1]"])
    _install_fake_client(monkeypatch, models)
    long_content = "x" * 500
    context = RetrievedContext(chunks=[_chunk(content=long_content)], has_ready_documents=True)

    answer = generation.generate_answer("question", context)

    assert len(answer.citations[0].excerpt) == 300


def test_generate_answer_partial_coverage_answer_is_returned_grounded_with_citations(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    text = (
        "Employees get 25 days of annual leave [1]. "
        "The documents do not cover remote-work stipends for contractors."
    )
    models = _FakeModels([text])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer(
        "How many leave days, and what is the contractor remote-work stipend?", context
    )

    assert answer.grounded is True
    assert len(answer.citations) == 1
    assert "do not cover" in answer.content.lower()


def test_generate_answer_api_key_never_appears_in_the_returned_answer(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert "super-secret-key" not in answer.content
    assert all("super-secret-key" not in (c.excerpt or "") for c in answer.citations)


def test_generate_answer_includes_prior_turns_in_the_prompt_sent_to_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["An answer. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    history = [
        {"role": "user", "content": "Earlier question about leave"},
        {"role": "assistant", "content": "Earlier answer about leave"},
    ]

    generation.generate_answer("Follow-up question", context, history=history)

    prompt = models.calls[0]
    assert "Earlier question about leave" in prompt
    assert "Earlier answer about leave" in prompt
    assert "Follow-up question" in prompt


# --- stream_answer: configuration and open-stream retries -------------------


def test_stream_answer_without_api_key_raises_typed_error_before_any_token(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError):
        list(generation.stream_answer("question", context))


def test_stream_answer_retries_a_failure_before_the_first_token_and_then_succeeds(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _FakeStreamModels([RuntimeError("transient"), ["Employees get ", "25 days."]])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    pieces = list(generation.stream_answer("How many leave days?", context))

    assert len(models.calls) == 2  # failed opening the stream once, succeeded on retry
    assert pieces == ["Employees get ", "25 days."]


def test_stream_answer_exhausts_configured_retries_then_raises_typed_service_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _FakeStreamModels([RuntimeError("boom"), RuntimeError("boom again")])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        list(generation.stream_answer("question", context))

    assert len(models.calls) == 2


def test_stream_answer_rejected_key_raises_immediately_without_retrying(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    error = RuntimeError("Gemini rejected the request")
    error.status_code = 403
    models = _FakeStreamModels([error, ["should never be reached"]])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        list(generation.stream_answer("question", context))

    assert exc_info.value.status_code == 403
    assert len(models.calls) == 1


# --- stream_answer: successful streaming and mid-stream interruption -------


def test_stream_answer_yields_plain_text_deltas_in_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels([["Employees get ", "25 days ", "of annual leave."]])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    pieces = list(generation.stream_answer("How many leave days?", context))

    assert pieces == ["Employees get ", "25 days ", "of annual leave."]


def test_stream_answer_failure_after_first_token_propagates_without_a_retry(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _FakeStreamModels(
        [["Here is a partial answer"]], mid_stream_error=RuntimeError("stream broke")
    )
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    generator = generation.stream_answer("question", context)
    first = next(generator)
    assert first == "Here is a partial answer"

    with pytest.raises(RuntimeError, match="stream broke"):
        next(generator)

    assert len(models.calls) == 1  # the interruption was never retried


def test_stream_answer_includes_prior_turns_in_the_prompt_sent_to_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeStreamModels([["An answer."]])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    history = [
        {"role": "user", "content": "Earlier question about leave"},
        {"role": "assistant", "content": "Earlier answer about leave"},
    ]

    list(generation.stream_answer("Follow-up question", context, history=history))

    prompt = models.calls[0]
    assert "Earlier question about leave" in prompt
    assert "Earlier answer about leave" in prompt
    assert "Follow-up question" in prompt
