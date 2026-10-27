"""Unit tests for `backend/app/embeddings.py`.

This ticket ("Unit tests for backend/app/embeddings.py") carries no
acceptance criteria of its own, so tests are named for the behaviour they
pin down rather than an AC id.

Complements, rather than restates, what the embeddings module is already
exercised by elsewhere: the clean not-configured / key-rejected / retry-then-
succeed / exhausted-retries paths are covered through `app.ingestion` in
`backend/tests/test_ingestion.py`, and the key-never-leaks and chat-endpoint
503 contract are covered in `backend/tests/test_gemini_config_error.py`.
What's new here and only here: a no-retry success path that would actually
notice a mis-ordered result (distinct vectors per text, not one value
repeated), the exact request shape sent to Gemini, the floor of at least one
attempt when `EMBEDDING_MAX_RETRIES` is configured to zero or less, an empty
`GEMINI_API_KEY` treated the same as an unset one, the `code`-attribute and
message-based fallbacks `_rejected_status` uses when an error doesn't carry
a plain integer `status_code`, that a non-auth-shaped failure is retried
rather than treated as a rejection, and that the key value never leaks into
the *generic* retries-exhausted error either (only the rejected-key error
was checked for that elsewhere).

No live Gemini: every test installs a fake `genai.Client` factory so the
suite needs no network access and no real API key.
"""

import pytest

from app import embeddings


class FakeEmbedding:
    def __init__(self, values):
        self.values = values


class FakeResult:
    def __init__(self, vectors):
        self.embeddings = [FakeEmbedding(v) for v in vectors]


class RecordingModels:
    """Records every `embed_content` call and returns a fixed result, so a
    test can assert exactly what was sent to Gemini."""

    def __init__(self, vectors):
        self._vectors = vectors
        self.calls: list[dict] = []

    def embed_content(self, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return FakeResult(self._vectors)


class AlwaysFailingModels:
    def __init__(self, make_error):
        self._make_error = make_error
        self.calls = 0

    def embed_content(self, model, contents, config=None):
        self.calls += 1
        raise self._make_error()


def _install_client(monkeypatch, models):
    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.models = models

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)


# --- success on the first attempt -------------------------------------------


def test_embed_texts_returns_one_distinct_vector_per_text_in_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    models = RecordingModels([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
    _install_client(monkeypatch, models)

    result = embeddings.embed_texts(["first", "second", "third"])

    assert result == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    assert len(models.calls) == 1  # no retry spent on a call that succeeded


def test_embed_texts_sends_the_model_the_texts_and_the_configured_dimension(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    models = RecordingModels([[0.0], [0.0]])
    _install_client(monkeypatch, models)

    embeddings.embed_texts(["alpha", "beta"])

    call = models.calls[0]
    assert call["model"] == embeddings.EMBEDDING_MODEL
    assert call["contents"] == ["alpha", "beta"]
    assert call["config"].output_dimensionality == embeddings.EMBEDDING_DIM


# --- not configured ----------------------------------------------------------


def test_embed_texts_treats_empty_string_api_key_as_unset(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")

    with pytest.raises(embeddings.GeminiNotConfiguredError):
        embeddings.embed_texts(["hello"])


def test_embed_texts_not_configured_never_constructs_a_client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class ExplodingFactory:
        def __call__(self, api_key):
            raise AssertionError("must not construct a client without an API key")

    monkeypatch.setattr(embeddings.genai, "Client", ExplodingFactory())

    with pytest.raises(embeddings.GeminiNotConfiguredError):
        embeddings.embed_texts(["hello"])


# --- retry floor --------------------------------------------------------------


@pytest.mark.parametrize("configured_retries", ["0", "-5"])
def test_embed_texts_always_attempts_at_least_once_even_when_retries_configured_non_positive(
    monkeypatch, configured_retries
):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", configured_retries)
    models = AlwaysFailingModels(lambda: RuntimeError("down"))
    _install_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["hello"])

    assert models.calls == 1


# --- generic exhausted-retries error ------------------------------------------


def test_embed_texts_exhausted_retries_error_never_includes_the_key_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "top-secret-value")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = AlwaysFailingModels(lambda: RuntimeError("network blip"))
    _install_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "top-secret-value" not in str(exc_info.value)
    assert models.calls == 2


def test_embed_texts_exhausted_retries_error_chains_the_last_underlying_exception(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = AlwaysFailingModels(lambda: RuntimeError("network blip"))
    _install_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert str(exc_info.value.__cause__) == "network blip"


# --- key-rejection detection fallbacks ----------------------------------------


def test_rejected_key_detected_via_code_attribute_when_no_status_code_attribute(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")

    def make_error():
        error = RuntimeError("blocked")
        error.code = 403
        return error

    models = AlwaysFailingModels(make_error)
    _install_client(monkeypatch, models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.status_code == 403
    assert models.calls == 1  # no retry spent on a key that cannot succeed


@pytest.mark.parametrize(
    "message,expected_status",
    [
        ("401 Unauthorized", 401),
        ("request failed: UNAUTHENTICATED", 401),
        ("403 Forbidden", 403),
        ("PERMISSION_DENIED: no access", 403),
        ("API_KEY_INVALID: bad key", 403),
    ],
)
def test_rejected_key_detected_from_message_when_no_status_attribute_present(
    monkeypatch, message, expected_status
):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    models = AlwaysFailingModels(lambda: RuntimeError(message))
    _install_client(monkeypatch, models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.status_code == expected_status
    assert models.calls == 1


def test_non_auth_shaped_errors_are_retried_rather_than_treated_as_a_rejection(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")
    models = AlwaysFailingModels(lambda: RuntimeError("503 Service Unavailable"))
    _install_client(monkeypatch, models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["hello"])

    assert models.calls == 3
