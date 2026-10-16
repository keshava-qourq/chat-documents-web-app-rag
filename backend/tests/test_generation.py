"""Unit tests for `app.generation` reaching past what
`backend/app/tests/test_generation.py` and `backend/app/tests/
test_gemini_config_error.py` already cover.

Those two files already prove: no-context short-circuits without calling
Gemini; a missing key raises `GeminiNotConfiguredError`; a rejected key
(401/403, via `status_code`) raises `GeminiKeyRejectedError` immediately for
both `generate_answer` and `stream_answer`; the not-found phrase and
partial-coverage branches of `generate_answer`; de-duplicated citations; and
that the key value itself never leaks into an answer or an error message.

This file reaches what those leave uncovered:

- `generate_answer` actually *retrying* a transient failure and succeeding,
  not just exhausting every attempt and failing -- the retry loop's
  "try again" branch has no test anywhere else;
- a configured retry count of zero or negative still making exactly one
  attempt for `generate_answer`, the same edge case
  `backend/tests/test_embeddings.py` already proves for `embed_texts`;
- `GenerationServiceError` keeping the last underlying exception as its
  `__cause__`;
- a rejected key detected on a *retried* attempt (not just the first one),
  and detected from every shape `_rejected_status` is documented to
  recognise -- not just a `status_code` attribute, but a `code` attribute
  and a bare message with no numeric attribute at all, the same shapes
  `backend/tests/test_embeddings.py` already proves for its own, separately
  implemented, copy of this detection logic;
- the configured `GEMINI_API_KEY` actually being the value forwarded to
  `genai.Client`, not just read successfully;
- the citation excerpt being truncated to 300 characters rather than the
  whole chunk content;
- `history` actually reaching the prompt text sent to Gemini, for
  `generate_answer` -- no existing test passes a non-empty `history` at all;
- `stream_answer`, which has essentially no *direct* unit coverage anywhere
  (only its rejected-key path is tested, in `test_gemini_config_error.py`,
  and otherwise it is only exercised indirectly through the full chat
  endpoint in `backend/tests/test_chat_streaming.py`): a missing key raising
  before any Gemini client is ever constructed; falsy chunk text being
  skipped; opening the stream being retried before any token has reached
  the caller; a failure that happens *during* iteration -- after the stream
  was already successfully opened -- never being retried, whether or not a
  token had already been yielded; and the exhausted-retries case raising
  `GenerationServiceError`.

No live Gemini call anywhere here: `genai.Client` is monkeypatched to a
local fake in every test, the same way the sibling suites do.
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


def _rejected_error(status_code: int) -> Exception:
    error = RuntimeError(f"Gemini rejected the request (status {status_code})")
    error.status_code = status_code
    return error


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    """`generate_content` pops the next scripted item off `items` on each
    call: a string becomes a successful response, an `Exception` instance
    is raised. Records every prompt it was called with."""

    def __init__(self, items):
        self._items = list(items)
        self.calls: list[str] = []

    def generate_content(self, model, contents):
        self.calls.append(contents)
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


def _install_fake_client(monkeypatch, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


# --- generate_answer: retrying actually recovers from a transient failure --


def test_generate_answer_retries_a_transient_failure_and_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _FakeModels([RuntimeError("transient network blip"), "Employees get 25 days."])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert answer.grounded is True
    assert answer.content == "Employees get 25 days."
    assert len(models.calls) == 2  # first attempt failed, second succeeded


@pytest.mark.parametrize("configured_retries", [0, -5])
def test_generate_answer_makes_at_least_one_attempt_when_retries_configured_at_zero_or_below(
    monkeypatch, configured_retries
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", str(configured_retries))
    models = _FakeModels([RuntimeError("fails"), RuntimeError("fails"), RuntimeError("fails")])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        generation.generate_answer("question", context)

    assert len(models.calls) == 1


def test_generation_service_error_keeps_the_last_underlying_exception_as_its_cause(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    errors = [RuntimeError("first failure"), RuntimeError("second failure")]
    models = _FakeModels(list(errors))
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError) as exc_info:
        generation.generate_answer("question", context)

    assert exc_info.value.__cause__ is errors[-1]


def test_generate_answer_rejected_key_detected_on_a_retried_attempt_not_just_the_first(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _FakeModels([RuntimeError("transient"), _rejected_error(401)])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        generation.generate_answer("question", context)

    assert exc_info.value.status_code == 401
    # No third attempt spent once the key is known to be rejected.
    assert len(models.calls) == 2


# --- generate_answer: every rejection shape _rejected_status recognises ---


@pytest.mark.parametrize(
    "message, expected_status",
    [
        ("401 Unauthorized: invalid credentials", 401),
        ("UNAUTHENTICATED: request had no valid authentication", 401),
        ("403 Forbidden", 403),
        ("PERMISSION_DENIED: caller lacks permission", 403),
        ("API_KEY_INVALID: the provided key is invalid", 403),
    ],
)
def test_generate_answer_rejected_key_detected_from_message_alone(
    monkeypatch, message, expected_status
) -> None:
    # No status_code/code attribute at all -- only the exception message
    # carries the signal. `app.generation` implements its own copy of this
    # detection (not a shared helper with `app.embeddings`), so its own
    # correctness here is not covered by `test_embeddings.py` proving the
    # same shapes for `embed_texts`.
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    models = _FakeModels([RuntimeError(message)])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        generation.generate_answer("question", context)

    assert exc_info.value.status_code == expected_status
    assert len(models.calls) == 1


def test_generate_answer_rejected_key_detected_via_code_attribute_not_status_code(
    monkeypatch,
) -> None:
    # Some SDK versions surface the auth failure as `code` rather than
    # `status_code`; `_rejected_status` is documented to read either.
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    error = RuntimeError("auth failure")
    error.code = 401
    models = _FakeModels([error])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        generation.generate_answer("question", context)

    assert exc_info.value.status_code == 401
    assert len(models.calls) == 1


def test_generate_answer_passes_the_configured_api_key_to_the_gemini_client(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "the-configured-generation-key")
    constructed_with = []

    class Factory:
        def __call__(self, api_key):
            constructed_with.append(api_key)
            return type("C", (), {"models": _FakeModels(["An answer."])})()

    monkeypatch.setattr(generation.genai, "Client", Factory())
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    generation.generate_answer("question", context)

    assert constructed_with == ["the-configured-generation-key"]


# --- generate_answer: history and citation shape ---------------------------


def test_generate_answer_includes_prior_turns_in_the_prompt_sent_to_gemini(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Berlin closes for 2 weeks."])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)
    history = [
        {"role": "user", "content": "How many leave days?"},
        {"role": "assistant", "content": "Employees get 25 days of annual leave."},
    ]

    generation.generate_answer("What about the Berlin office?", context, history=history)

    assert len(models.calls) == 1
    prompt = models.calls[0]
    assert "How many leave days?" in prompt
    assert "Employees get 25 days of annual leave." in prompt
    assert "What about the Berlin office?" in prompt


def test_generate_answer_citation_excerpt_is_truncated_to_300_characters(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    long_content = "A" * 500
    models = _FakeModels(["The handbook says A repeated. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk(content=long_content)], has_ready_documents=True)

    answer = generation.generate_answer("question", context)

    assert len(answer.citations) == 1
    excerpt = answer.citations[0].excerpt
    assert len(excerpt) == 300
    assert excerpt == long_content[:300]


# --- stream_answer: fakes ---------------------------------------------------


class _FakeStreamChunk:
    def __init__(self, text):
        self.text = text


class _OpenFailsThenStreams:
    """`generate_content_stream` itself raises eagerly (as a real network
    call would) for the first `fail_times` calls, then returns a generator
    of `pieces`. Models the "opening the stream" failure `stream_answer`
    retries, as distinct from a failure that happens while iterating an
    already-opened stream."""

    def __init__(self, fail_times, pieces):
        self.fail_times = fail_times
        self.pieces = pieces
        self.calls = 0

    def generate_content_stream(self, model, contents):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("could not open the stream")
        return (_FakeStreamChunk(p) for p in self.pieces)


class _OpensThenFailsDuringIteration:
    """`generate_content_stream` always succeeds in opening (returns
    immediately), but the generator it hands back yields `pieces` and then
    raises `error` partway through, simulating a mid-stream interruption
    after the connection was already established."""

    def __init__(self, pieces, error):
        self.pieces = pieces
        self.error = error
        self.calls = 0

    def generate_content_stream(self, model, contents):
        self.calls += 1
        return self._gen()

    def _gen(self):
        for piece in self.pieces:
            yield _FakeStreamChunk(piece)
        raise self.error


def _install_fake_stream_client(monkeypatch, models):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


# --- stream_answer: missing key ---------------------------------------------


def test_stream_answer_missing_key_raises_before_any_gemini_client_is_constructed(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def fail_if_constructed(api_key):
        raise AssertionError("Gemini must not be contacted with no API key configured")

    monkeypatch.setattr(generation.genai, "Client", fail_if_constructed)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError):
        list(generation.stream_answer("question", context))


# --- stream_answer: yields only non-empty deltas ----------------------------


def test_stream_answer_yields_plain_text_deltas_and_skips_falsy_chunks(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _OpenFailsThenStreams(fail_times=0, pieces=["Employees get ", None, "", "25 days."])
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    pieces = list(generation.stream_answer("question", context))

    assert pieces == ["Employees get ", "25 days."]


# --- stream_answer: retry happens only before the first token is yielded ---


def test_stream_answer_retries_opening_the_stream_before_any_token_is_yielded(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _OpenFailsThenStreams(fail_times=2, pieces=["Recovered answer."])
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    pieces = list(generation.stream_answer("question", context))

    assert pieces == ["Recovered answer."]
    assert models.calls == 3  # two failed opens, then one that succeeded


def test_stream_answer_exhausting_retries_to_open_raises_generation_service_error(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _OpenFailsThenStreams(fail_times=99, pieces=["never reached"])
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        list(generation.stream_answer("question", context))

    assert models.calls == 2


@pytest.mark.parametrize("configured_retries", [0, -5])
def test_stream_answer_makes_at_least_one_attempt_to_open_when_retries_configured_at_zero_or_below(
    monkeypatch, configured_retries
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", str(configured_retries))
    models = _OpenFailsThenStreams(fail_times=99, pieces=["never reached"])
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        list(generation.stream_answer("question", context))

    assert models.calls == 1


def test_stream_answer_rejected_key_detected_on_a_retried_open_attempt(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")

    class OpenFailsThenRejects:
        def __init__(self):
            self.calls = 0

        def generate_content_stream(self, model, contents):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            raise _rejected_error(403)

    models = OpenFailsThenRejects()
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        list(generation.stream_answer("question", context))

    assert exc_info.value.status_code == 403
    assert models.calls == 2  # no third attempt once the key is known-rejected


def test_stream_answer_rejected_key_detected_from_message_alone(monkeypatch) -> None:
    # Same message-only detection shape proven above for `generate_answer`,
    # exercised through `stream_answer`'s own, separately implemented call
    # to the same `_rejected_status` helper.
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")

    class RejectingModels:
        def __init__(self):
            self.calls = 0

        def generate_content_stream(self, model, contents):
            self.calls += 1
            raise RuntimeError("PERMISSION_DENIED: caller lacks permission")

    models = RejectingModels()
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiKeyRejectedError) as exc_info:
        list(generation.stream_answer("question", context))

    assert exc_info.value.status_code == 403
    assert models.calls == 1


# --- stream_answer: no retry once the stream is already open ---------------


def test_stream_answer_does_not_retry_a_failure_during_iteration_before_any_token_yielded(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    error = RuntimeError("dropped immediately after opening, before any text")
    models = _OpensThenFailsDuringIteration(pieces=[], error=error)
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(RuntimeError, match="dropped immediately"):
        list(generation.stream_answer("question", context))

    # The stream was opened successfully on the first and only attempt --
    # the failure happened while iterating it, which is never retried.
    assert models.calls == 1


def test_stream_answer_does_not_retry_a_failure_after_a_token_was_already_yielded(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    error = RuntimeError("connection dropped mid-answer")
    models = _OpensThenFailsDuringIteration(pieces=["Here is a partial answer"], error=error)
    _install_fake_stream_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    generator = generation.stream_answer("question", context)
    first_piece = next(generator)

    assert first_piece == "Here is a partial answer"
    with pytest.raises(RuntimeError, match="connection dropped mid-answer"):
        next(generator)

    assert models.calls == 1  # already-sent text was never re-requested
