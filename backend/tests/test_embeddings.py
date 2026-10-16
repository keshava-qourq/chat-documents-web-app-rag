"""Unit tests for `app.embeddings.embed_texts`.

`backend/app/tests/test_ingestion.py` already proves the missing-key
immediate failure and a flaky-then-succeeds retry sequence, and
`backend/app/tests/test_gemini_config_error.py` already proves a 401
rejection is raised immediately (no retry spent), names `GEMINI_API_KEY`,
and never echoes the key value. This file reaches what those two leave
uncovered:

- the shape of a successful multi-text call: vectors come back in the same
  order as the input texts, the configured model name and api key are the
  ones actually forwarded to the Gemini client;
- the second rejection status (403), and the two other shapes
  `_rejected_status` is documented to recognise a rejection from -- a
  `code` attribute instead of `status_code`, and a bare message with no
  numeric attribute at all;
- `GeminiNotConfiguredError` never even constructing a Gemini client, let
  alone calling it;
- `embedding_max_retries()` configured at zero or below still making
  exactly one attempt rather than looping zero times or raising something
  else;
- the exhausted-retries `EmbeddingServiceError` keeping the last underlying
  exception as its `__cause__`, for anyone who inspects the chain rather
  than just the message.

No live Gemini: every test installs a fake `genai.Client` the same way the
sibling suites do.
"""

import pytest

from app import embeddings


class _FakeEmbedding:
    def __init__(self, values):
        self.values = values


class _FakeResult:
    def __init__(self, vectors):
        self.embeddings = [_FakeEmbedding(v) for v in vectors]


def _install_fake_client(monkeypatch, models_factory):
    """Installs a fake `genai.Client` whose `.models` is `models_factory()`,
    and returns the list of api keys the client was constructed with."""
    constructed_with = []

    class FakeClient:
        def __init__(self, api_key):
            constructed_with.append(api_key)
            self.models = models_factory()

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)
    return constructed_with


# --- successful call: order, model, key forwarded ---------------------------


def test_embed_texts_returns_one_vector_per_input_in_the_same_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    captured = {}

    class FakeModels:
        def embed_content(self, model, contents):
            captured["model"] = model
            captured["contents"] = list(contents)
            return _FakeResult([[1.0, 1.1], [2.0, 2.2], [3.0, 3.3]])

    _install_fake_client(monkeypatch, lambda: FakeModels())

    result = embeddings.embed_texts(["first", "second", "third"])

    assert result == [[1.0, 1.1], [2.0, 2.2], [3.0, 3.3]]
    assert captured["contents"] == ["first", "second", "third"]
    assert captured["model"] == embeddings.EMBEDDING_MODEL


def test_embed_texts_passes_the_configured_api_key_to_the_gemini_client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "the-configured-key")

    class FakeModels:
        def embed_content(self, model, contents):
            return _FakeResult([[0.0, 0.0] for _ in contents])

    constructed_with = _install_fake_client(monkeypatch, lambda: FakeModels())

    embeddings.embed_texts(["only text"])

    assert constructed_with == ["the-configured-key"]


# --- not configured: no client is ever constructed --------------------------


def test_embed_texts_not_configured_never_constructs_a_gemini_client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    constructed_with = []

    class FakeClient:
        def __init__(self, api_key):
            constructed_with.append(api_key)

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)

    with pytest.raises(embeddings.GeminiNotConfiguredError):
        embeddings.embed_texts(["hello"])

    assert constructed_with == []


# --- rejected key: the other status, and the other detection shapes ---------


class _RejectingModels:
    def __init__(self, raise_fn):
        self.calls = 0
        self._raise_fn = raise_fn

    def embed_content(self, model, contents):
        self.calls += 1
        raise self._raise_fn()


def test_embed_texts_rejected_key_via_403_status_code_attribute_raises_immediately(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")

    def make_error():
        error = RuntimeError("Gemini rejected the request (status 403)")
        error.status_code = 403
        return error

    models = _RejectingModels(make_error)
    _install_fake_client(monkeypatch, lambda: models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.status_code == 403
    assert "403" in str(exc_info.value)
    assert models.calls == 1  # no retry spent on a key that cannot succeed


def test_embed_texts_rejected_key_detected_via_code_attribute_not_status_code(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")

    def make_error():
        # Some SDK versions surface the auth failure as `code` rather than
        # `status_code`; `_rejected_status` is documented to read either.
        error = RuntimeError("auth failure")
        error.code = 401
        return error

    models = _RejectingModels(make_error)
    _install_fake_client(monkeypatch, lambda: models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.status_code == 401
    assert models.calls == 1


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
def test_embed_texts_rejected_key_detected_from_message_alone(
    monkeypatch, message, expected_status
):
    # No status_code/code attribute at all -- only the exception message
    # carries the signal, which is one of the shapes the module's own
    # docstring says `_rejected_status` must still recognise.
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")

    def make_error():
        return RuntimeError(message)

    models = _RejectingModels(make_error)
    _install_fake_client(monkeypatch, lambda: models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.status_code == expected_status
    assert models.calls == 1


def test_embed_texts_rejected_key_message_never_includes_the_key_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")

    def make_error():
        error = RuntimeError("rejected")
        error.status_code = 403
        return error

    models = _RejectingModels(make_error)
    _install_fake_client(monkeypatch, lambda: models)

    with pytest.raises(embeddings.GeminiKeyRejectedError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert "super-secret-value" not in str(exc_info.value)


# --- retry count edge cases --------------------------------------------------


@pytest.mark.parametrize("configured_retries", [0, -5])
def test_embed_texts_makes_at_least_one_attempt_even_when_retries_configured_at_zero_or_below(
    monkeypatch, configured_retries
):
    # `attempts = max(1, embedding_max_retries())`: a misconfigured value of
    # zero or below must not skip the call entirely.
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", str(configured_retries))

    class FakeModels:
        def __init__(self):
            self.calls = 0

        def embed_content(self, model, contents):
            self.calls += 1
            raise RuntimeError("fails every time")

    models = FakeModels()
    _install_fake_client(monkeypatch, lambda: models)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["hello"])

    assert models.calls == 1


def test_embedding_service_error_keeps_the_last_underlying_exception_as_its_cause(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")

    errors = [RuntimeError("first failure"), RuntimeError("second failure")]

    class FakeModels:
        def __init__(self):
            self.calls = 0

        def embed_content(self, model, contents):
            error = errors[self.calls]
            self.calls += 1
            raise error

    models = FakeModels()
    _install_fake_client(monkeypatch, lambda: models)

    with pytest.raises(embeddings.EmbeddingServiceError) as exc_info:
        embeddings.embed_texts(["hello"])

    assert exc_info.value.__cause__ is errors[-1]
