"""Gemini embedding calls, retried a configured number of times.

`gemini_api_key()` is read at call time, not at import, so this module stays
importable -- and the whole ingestion pipeline with it -- whether or not the
product owner has set `GEMINI_API_KEY` yet. A missing key raises
`GeminiNotConfiguredError` immediately, without spending a retry on a call
that cannot possibly succeed; a key that is set but whose calls keep failing
(quota, network, a bad response) raises `EmbeddingServiceError` only after
`embedding_max_retries()` attempts are exhausted.
"""

from google import genai

from app.config import embedding_max_retries, gemini_api_key

EMBEDDING_MODEL = "text-embedding-004"


class GeminiNotConfiguredError(Exception):
    """Raised when `GEMINI_API_KEY` is unset at the moment embeddings are needed."""


class EmbeddingServiceError(Exception):
    """Raised once every retry attempt against Gemini has failed."""


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
            last_error = exc

    raise EmbeddingServiceError("embedding service error") from last_error
