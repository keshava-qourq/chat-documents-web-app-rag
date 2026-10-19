"""Unit tests for `app.embeddings.embed_texts`.

Exercises the module's one public entry point directly -- no database, no
object store, no live Gemini call -- standing in for the Gemini SDK with a
fake `genai.Client` the way `backend/app/tests/test_ingestion.py` and
`backend/app/tests/test_gemini_config_error.py` already do, since those
files sit outside this suite's `testpaths` (`backend/tests`, per
`pytest.ini`) and so are never actually collected by a bare `pytest` run
from `backend/`. This file is what makes `app.embeddings` actually covered.

Three behaviours are pinned down, per the module's own docstring:

* no key configured -> `GeminiNotConfiguredError`, immediately, no Gemini
  call spent on it;
* a key Gemini itself rejects (401/403, in whatever shape the SDK surfaces
  it) -> `GeminiKeyRejectedError`, immediately, with the status code and no
  retry wasted on a call that cannot succeed;
* any other failure -> retried up to `embedding_max_retries()` times (at
  least once, however that is configured) before `EmbeddingServiceError`;

plus the success path's actual contract: one vector per input text, in the
same order, from a single call naming the configured model.
"""

import pytest

from app import embeddings
from app.config import EMBEDDING_MAX_RETRIES_DEFAULT

# --- fakes -------------------------------------------------------------


class _FakeEmbedding:
    def __init__(self, values: list[float]) -> None:
        self.values = values


class _FakeResult:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.embeddings = [_FakeEmbedding(v) for v in vectors]


class _RecordingModels:
    """Succeeds immediately, returning a distinct vector per input text, and
    records the exact arguments it was called with."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def embed_content(self, model, contents):
        self.calls.append({"model": model, "contents": contents})
        return _FakeResult([[float(i), float(i) + 0.5] for i in range(len(contents))])


class _FlakyThenSucceedsModels:
    """Fails with a plain, non-auth exception on every call before the Nth,
    then succeeds -- standing in for a transient network/quota failure."""

    def __init__(self, succeed_on_call: int) -> None:
        self.succeed_on_call = succeed_on_call
        self.calls = 0

    def embed_content(self, model, contents):
        self.calls += 1
        if self.calls < self.succeed_on_call:
            raise RuntimeError("transient failure")
        return _FakeResult([[0.1] for _ in contents])


class _AlwaysFailsModels:
    def __init__(self, exc_factory=lambda: RuntimeError("always fails")) -> None:
        self.calls = 0
        self._exc_factory = exc_factory

    def embed_content(self, model, contents):
        self.calls += 1
        raise self._exc_factory()


def _install_fake_client(monkeypatch, models) -> None:
    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            self.models = models

    monkeypatch.setattr(embeddings.genai, "Client", _FakeClient)


def _forbid_client(monkeypatch) -> None:
    """Installed when Gemini must never be reached at all."""

    def _raise_if_constructed(*args, **kwargs):
        raise AssertionError("genai.Client must not be constructed")

    monkeypatch.setattr(embeddings.genai, "Client", _raise_if_constructed)


# --- not configured ----------------------------------------------------


def test_raises_not_configured_when_key_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _forbid_client(monkeypatch)

    with pytest.raises(embeddings.GeminiNotConfiguredError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert exc_info.value.code == "gemini_not_configured"


def test_raises_not_configured_when_key_is_empty_string(monkeypatch) -> None:
    # app.config.gemini_api_key() treats "" as unset; embed_texts must honour
    # that, not pass an empty key down to the SDK.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _forbid_client(monkeypatch)

    with pytest.raises(embeddings.GeminiNotConfiguredError):
        embeddings.embed_texts(["hello"])


# --- success path --------------------------------------------------------


def test_returns_one_vector_per_text_in_the_same_order(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    models = _RecordingModels()
    _install_fake_client(monkeypatch, models)

    result = embeddings.embed_texts(["first", "second", "third"])

    assert result == [[0.0, 0.5], [1.0, 1.5], [2.0, 2.5]]


def test_calls_the_configured_embedding_model_with_every_text_in_one_call(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    models = _RecordingModels()
    _install_fake_client(monkeypatch, models)

    embeddings.embed_texts(["alpha", "beta"])

    assert len(models.calls) == 1
    assert models.calls[0]["model"] == embeddings.EMBEDDING_MODEL
    assert models.calls[0]["contents"] == ["alpha", "beta"]


# --- transient failure: retried -------------------------------------------


def test_retries_a_transient_failure_before_succeeding(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = _FlakyThenSucceedsModels(succeed_on_call=3)
    _install_fake_client(monkeypatch, models)

    result = embeddings.embed_texts(["a", "b"])

    assert models.calls == 3
    assert result == [[0.1], [0.1]]


def test_raises_embedding_service_error_once_every_retry_is_exhausted(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _AlwaysFailsModels()
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError) as exc_info:
        embeddings.embed_texts(["a"])

    assert models.calls == 2
    assert exc_info.value.__cause__ is not None  # the last underlying failure is chained


def test_uses_the_configured_number_of_retry_attempts(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "5")
    models = _AlwaysFailsModels()
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["a"])

    assert models.calls == 5


@pytest.mark.parametrize("configured_retries", ["0", "-3"])
def test_always_attempts_at_least_once_even_when_configured_retries_is_not_positive(
    monkeypatch, configured_retries
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", configured_retries)
    models = _AlwaysFailsModels()
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["a"])

    assert models.calls == 1


def test_default_retry_count_is_used_when_unset(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    monkeypatch.delenv("EMBEDDING_MAX_RETRIES", raising=False)
    models = _AlwaysFailsModels()
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["a"])

    assert models.calls == EMBEDDING_MAX_RETRIES_DEFAULT


# --- key rejected: immediate, no retry -------------------------------------


def _exc_with_status_code(code: int) -> Exception:
    exc = RuntimeError(f"rejected (status {code})")
    exc.status_code = code
    return exc


def _exc_with_code_attr(code: int) -> Exception:
    exc = RuntimeError("rejected")
    exc.code = code
    return exc


def _exc_with_message(message: str) -> Exception:
    return RuntimeError(message)


@pytest.mark.parametrize(
    ("exc_factory", "expected_status"),
    [
        (lambda: _exc_with_status_code(401), 401),
        (lambda: _exc_with_status_code(403), 403),
        (lambda: _exc_with_code_attr(401), 401),
        (lambda: _exc_with_code_attr(403), 403),
        (lambda: _exc_with_message("HTTP 401 error"), 401),
        (lambda: _exc_with_message("UNAUTHENTICATED: bad credentials"), 401),
        (lambda: _exc_with_message("HTTP 403 Forbidden"), 403),
        (lambda: _exc_with_message("PERMISSION_DENIED: no access"), 403),
        (lambda: _exc_with_message("API_KEY_INVALID"), 403),
    ],
)
def test_raises_key_rejected_immediately_for_every_recognised_rejection_shape(
    monkeypatch, exc_factory, expected_status
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    models = _AlwaysFailsModels(exc_factory=exc_factory)
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "5")  # would retry 5x if misclassified
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.code == "gemini_key_rejected"
    assert str(expected_status) in str(exc_info.value)
    assert "GEMINI_API_KEY" in str(exc_info.value)
    # The whole point of detecting a rejection up front: no retry is spent on
    # a key that cannot possibly succeed, regardless of how many were configured.
    assert models.calls == 1


def test_an_unrecognised_failure_is_retried_rather_than_treated_as_a_rejection(
    monkeypatch,
) -> None:
    # A plain failure that happens to mention neither a 401/403 status nor one
    # of the recognised phrases must still be retried as a transient error,
    # not misclassified as a key rejection.
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _AlwaysFailsModels(exc_factory=lambda: RuntimeError("503 Service Unavailable"))
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["a"])

    assert models.calls == 2


def test_rejected_key_error_message_never_includes_the_key_value(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    models = _AlwaysFailsModels(exc_factory=lambda: _exc_with_status_code(401))
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "super-secret-value" not in str(exc_info.value)


def test_service_error_message_never_includes_the_key_value(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "another-secret-value")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "1")
    models = _AlwaysFailsModels(
        exc_factory=lambda: RuntimeError("failed with key another-secret-value")
    )
    _install_fake_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "another-secret-value" not in str(exc_info.value)
