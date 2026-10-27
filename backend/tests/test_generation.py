"""Tests for `app.generation.generate_answer` and `app.generation.stream_answer`:
no-context behaviour, not-found grounding, partial coverage, de-duplicated
citations, typed errors for a missing key or a Gemini failure, the retry
budget actually honouring `EMBEDDING_MAX_RETRIES`, and the streaming
counterpart's own retry-before-first-token / no-retry-after-first-token
contract that `generate_answer` has no equivalent of.

No live Gemini call anywhere in this module -- `genai.Client` is
monkeypatched to a fake that records the prompt it was given and returns a
scripted response. Self-contained: builds its own `RetrievedChunk`/
`RetrievedContext` fixtures rather than needing a database, so it needs
nothing from `conftest.py`.
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
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, texts_or_exc):
        self._texts_or_exc = texts_or_exc
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append(contents)
        item = (
            self._texts_or_exc.pop(0)
            if isinstance(self._texts_or_exc, list)
            else self._texts_or_exc
        )
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


def _install_fake_client(monkeypatch, models) -> None:
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


def test_no_ready_documents_returns_no_context_without_calling_gemini(monkeypatch) -> None:
    def fail_client(api_key):
        raise AssertionError("Gemini must not be called with no context")

    monkeypatch.setattr(generation.genai, "Client", fail_client)

    context = RetrievedContext(chunks=[], has_ready_documents=False)
    answer = generation.generate_answer("What is the policy?", context)

    assert answer.grounded is False
    assert answer.citations == []
    # Matches `generation.NO_DOCUMENTS_MESSAGE` verbatim rather than a loosely
    # worded substring, so a future wording change is caught here too.
    assert answer.content == generation.NO_DOCUMENTS_MESSAGE
    assert "documents" in answer.content.lower()


def test_zero_chunks_above_threshold_also_returns_no_context(monkeypatch) -> None:
    def fail_client(api_key):
        raise AssertionError("Gemini must not be called")

    monkeypatch.setattr(generation.genai, "Client", fail_client)

    context = RetrievedContext(chunks=[], has_ready_documents=True)
    answer = generation.generate_answer("What is the policy?", context)

    assert answer.grounded is False
    assert answer.citations == []


def test_missing_api_key_raises_typed_error(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError):
        generation.generate_answer("question", context)


def test_gemini_failure_after_retries_raises_typed_service_error(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _FakeModels(RuntimeError("boom"))
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        generation.generate_answer("question", context)


def test_generate_answer_attempts_count_matches_embedding_max_retries(monkeypatch) -> None:
    """The retry budget is `app.config.embedding_max_retries()`, not a
    second, independent constant -- a change to that knob must change how
    many times `generate_answer` tries before giving up, too."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "4")
    models = _FakeModels(RuntimeError("boom"))
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        generation.generate_answer("question", context)

    assert len(models.calls) == 4


def test_generate_answer_retries_a_transient_failure_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels([RuntimeError("transient"), "Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert answer.grounded is True
    assert "25 days" in answer.content
    assert len(models.calls) == 2  # one failed attempt, one that succeeded


def test_generate_answer_includes_conversation_history_in_the_prompt(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    history = [{"role": "user", "content": "Earlier question about leave policy"}]

    generation.generate_answer("Follow-up question", context, history=history)

    prompt_sent = models.calls[0]
    assert "Earlier question about leave policy" in prompt_sent
    assert "Follow-up question" in prompt_sent


def test_question_not_covered_by_chunks_returns_not_found_with_no_citations(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels([generation.NOT_FOUND_MESSAGE])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("unrelated question", context)

    assert answer.grounded is False
    assert answer.citations == []
    assert "not found in the uploaded documents" in answer.content.lower()


def test_grounded_answer_returns_deduplicated_citations_from_retrieved_chunks_only(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    chunk_one = _chunk(source_location="handbook.pdf, page 1")
    chunk_two = _chunk(source_location="handbook.pdf, page 1")  # same (doc, location)
    chunk_three = _chunk(source_location="handbook.pdf, page 2")
    context = RetrievedContext(chunks=[chunk_one, chunk_two, chunk_three], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert answer.grounded is True
    assert len(answer.citations) == 2
    locations = {(c.document_name, c.source_location) for c in answer.citations}
    assert locations == {
        ("handbook.pdf", "handbook.pdf, page 1"),
        ("handbook.pdf", "handbook.pdf, page 2"),
    }
    retrieved_ids = {c.chunk_id for c in context.chunks}
    for citation in answer.citations:
        assert citation.chunk_id in retrieved_ids


def test_citation_excerpt_is_truncated_to_300_characters(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    long_content = "A" * 500
    context = RetrievedContext(chunks=[_chunk(content=long_content)], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert len(answer.citations[0].excerpt) == 300
    assert answer.citations[0].excerpt == long_content[:300]


def test_partial_coverage_answer_is_returned_grounded_with_citations(monkeypatch) -> None:
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


def test_api_key_never_appears_in_the_returned_answer(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert "super-secret-key" not in answer.content
    assert all("super-secret-key" not in (c.excerpt or "") for c in answer.citations)


# --- `stream_answer` -------------------------------------------------------
#
# `generate_answer`'s behaviour above (no-context short-circuit, not-found
# grounding, citation dedup/truncation, history, the `GEMINI_API_KEY`
# config/rejection errors) all flow through the same `_build_prompt` /
# `_citations_for` helpers `stream_answer` also uses, and the rejected-key
# and missing-key paths for `stream_answer` specifically are already proven
# in `test_gemini_config_error.py`. What is unique to `stream_answer` and
# untested anywhere else is its retry contract: a failure *opening* the
# stream is retried (nothing has reached the caller yet), but a failure
# *after* a token has already been yielded is not -- it propagates as-is
# for the caller to treat as a mid-stream interruption.


class _StreamResponse:
    def __init__(self, text: str):
        self.text = text


class _OpenFailsThenSucceedsModels:
    """`generate_content_stream` itself raises on its first `fail_times`
    calls (simulating a failure to open the stream, before any token could
    possibly have reached the caller), then returns a working generator."""

    def __init__(self, fail_times: int, pieces: list[str]):
        self.fail_times = fail_times
        self.pieces = pieces
        self.calls = 0

    def generate_content_stream(self, model, contents):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("could not open stream")
        return iter(_StreamResponse(piece) for piece in self.pieces)


class _MidStreamFailureModels:
    """Yields `pieces` and then raises `error` while the caller is still
    iterating -- i.e. after at least one token has already reached them."""

    def __init__(self, pieces: list[str], error: Exception):
        self.pieces = pieces
        self.error = error
        self.calls = 0

    def generate_content_stream(self, model, contents):
        self.calls += 1
        return self._gen()

    def _gen(self):
        for piece in self.pieces:
            yield _StreamResponse(piece)
        raise self.error


def test_stream_answer_yields_text_deltas_in_order(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _OpenFailsThenSucceedsModels(fail_times=0, pieces=["Employees get ", "25 days."])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    pieces = list(generation.stream_answer("How many leave days?", context))

    assert pieces == ["Employees get ", "25 days."]


def test_stream_answer_missing_api_key_raises_typed_error_without_calling_gemini(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def fail_client(api_key):
        raise AssertionError("Gemini must not be called with no configured key")

    monkeypatch.setattr(generation.genai, "Client", fail_client)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError):
        list(generation.stream_answer("question", context))


def test_stream_answer_retries_a_failure_to_open_the_stream_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _OpenFailsThenSucceedsModels(fail_times=1, pieces=["Recovered answer."])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    pieces = list(generation.stream_answer("question", context))

    assert pieces == ["Recovered answer."]
    assert models.calls == 2  # one failed attempt to open, one that succeeded


def test_stream_answer_exhausts_retries_opening_the_stream_and_raises_typed_error(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _OpenFailsThenSucceedsModels(fail_times=99, pieces=["never reached"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        list(generation.stream_answer("question", context))

    assert models.calls == 3  # the configured retry budget, not retried forever


def test_stream_answer_does_not_retry_a_failure_after_the_first_token_was_yielded(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _MidStreamFailureModels(["partial answer"], RuntimeError("connection dropped"))
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    stream = generation.stream_answer("question", context)
    first_piece = next(stream)
    assert first_piece == "partial answer"

    # The caller already received a token it cannot un-send, so the stream
    # is never reopened for a second attempt: the raw exception propagates
    # (not wrapped as `GenerationServiceError`), and the stream was only
    # ever opened once.
    with pytest.raises(RuntimeError, match="connection dropped"):
        next(stream)
    assert models.calls == 1
