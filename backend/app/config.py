"""Centralised reads of the environment this application is configured from.

Every value here is read through a function, not a module-level constant, so
a caller gets the current environment at the point it actually needs it --
in particular `gemini_api_key()`, which the product owner has not set yet.
Routes and background jobs that call Gemini must check it at call time and
turn their feature off with a clear message instead of failing at import or
startup; nothing here calls Gemini itself.
"""

import os

DOCUMENT_CAP_DEFAULT = 200
MAX_UPLOAD_FILE_BYTES = 25 * 1024 * 1024
RATE_LIMIT_CHAT_PER_MIN_DEFAULT = 20
RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT = 10

# Ingestion pipeline defaults. Chunk size and overlap are measured in
# characters (not tokens) to keep the splitter dependency-free; 1000/200 is a
# conservative middle ground that keeps chunks well under Gemini's embedding
# input limit while still giving retrieval enough overlap to not lose context
# at a chunk boundary.
CHUNK_SIZE_DEFAULT = 1000
CHUNK_OVERLAP_DEFAULT = 200
EMBEDDING_MAX_RETRIES_DEFAULT = 3
EMBEDDING_BATCH_SIZE_DEFAULT = 16


def gemini_api_key() -> str | None:
    """`None` when Gemini has not been configured yet.

    Empty string counts as unset: a callable that reads `GEMINI_API_KEY` and
    gets "" back should disable its feature exactly as it would for a
    missing variable, not pass an empty key to the SDK.
    """
    return os.getenv("GEMINI_API_KEY") or None


def document_cap() -> int:
    """Total documents the shared library accepts before uploads are refused."""
    return int(os.getenv("DOCUMENT_CAP", str(DOCUMENT_CAP_DEFAULT)))


def rate_limit_chat_per_minute() -> int:
    """Questions answered per IP per minute before the chat endpoint returns 429."""
    return int(os.getenv("RATE_LIMIT_CHAT_PER_MIN", str(RATE_LIMIT_CHAT_PER_MIN_DEFAULT)))


def rate_limit_uploads_per_hour() -> int:
    """Uploads accepted per IP per hour before the upload endpoint returns 429."""
    return int(os.getenv("RATE_LIMIT_UPLOADS_PER_HOUR", str(RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT)))


def chunk_size() -> int:
    """Characters per chunk the ingestion pipeline splits extracted text into."""
    return int(os.getenv("CHUNK_SIZE", str(CHUNK_SIZE_DEFAULT)))


def chunk_overlap() -> int:
    """Characters of overlap kept between consecutive chunks of the same fragment."""
    return int(os.getenv("CHUNK_OVERLAP", str(CHUNK_OVERLAP_DEFAULT)))


def embedding_max_retries() -> int:
    """Attempts made to embed a batch of chunks before the document is failed."""
    return int(os.getenv("EMBEDDING_MAX_RETRIES", str(EMBEDDING_MAX_RETRIES_DEFAULT)))


def embedding_batch_size() -> int:
    """Chunks embedded per Gemini call, and the unit the progress field advances by."""
    return int(os.getenv("EMBEDDING_BATCH_SIZE", str(EMBEDDING_BATCH_SIZE_DEFAULT)))
