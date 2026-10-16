"""Gemini embedding calls, retried a configured number of times.

`gemini_api_key()` is read at call time, not at import, so this module stays
importable -- and the whole ingestion pipeline with it -- whether or not the
product owner has set `GEMINI_API_KEY` yet. A missing key raises
`GeminiNotConfiguredError` immediately, without spending a retry on a call
that cannot possibly succeed; a key that is set but whose calls keep failing
(quota, network, a bad response) raises `EmbeddingServiceError` only after
`embedding_max_retries()` attempts are exhausted.

A key that Gemini itself rejects (401/403 -- revoked, malformed, wrong
project) is a different, terminal failure: retrying it cannot possibly help,
so it is detected up front and raised immediately as
`GeminiKeyRejectedError` rather than being retried to exhaustion and
reported as a generic `EmbeddingServiceError`. Neither typed error, nor the
message on either, ever includes the key value itself -- only the fact that
`GEMINI_API_KEY` is the problem, and (for a rejection) the upstream status
code.
"""

from google import genai

from app.config import embedding_max_retries, gemini_api_key

EMBEDDING_MODEL = "text-embedding-004"


class GeminiNotConfiguredError(Exception):
    """Raised when `GEMINI_API_KEY` is unset at the moment embeddings are needed."""

    code = "gemini_not_configured"


class GeminiKeyRejectedError(Exception):
    """Raised when Gemini itself rejects `GEMINI_API_KEY` (HTTP 401/403)."""

    code = "gemini_key_rejected"

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class EmbeddingServiceError(Exception):
    """Raised once every retry attempt against Gemini has failed."""


def _rejected_status(exc: Exception) -> int | None:
    """The upstream HTTP status if `exc` looks like Gemini rejecting the
    API key, else `None`. google-genai surfaces an auth failure as an
    error carrying a 401/403 status (as `status_code` or `code`, depending
    on SDK version) or a recognisable message; this reads either shape
    without taking on a second Gemini client.
    """
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and value in (401, 403):
            return value
    message = str(exc).upper()
    if "401" in message or "UNAUTHENTICATED" in message:
        return 401
    if "403" in message or "PERMISSION_DENIED" in message or "API_KEY_INVALID" in message:
        return 403
    return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds `texts` in one Gemini call, retrying transient failures.

    Returns one vector per input text, in the same order.
    """
    api_key = gemini_api_key()
    if not api_key:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    attempts = max(1, embedding_max_retries())
    last_error: Exception | None = None

    for _ in range(attempts):
        try:
            result = client.models.embed_content(model=EMBEDDING_MODEL, contents=texts)
            return [list(item.values) for item in result.embeddings]
        except Exception as exc:  # noqa: BLE001 -- any Gemini/network failure is retried
            status = _rejected_status(exc)
            if status is not None:
                raise GeminiKeyRejectedError(
                    f"GEMINI_API_KEY was rejected by Gemini (status {status})",
                    status_code=status,
                ) from exc
            last_error = exc

    raise EmbeddingServiceError("embedding service error") from last_error
