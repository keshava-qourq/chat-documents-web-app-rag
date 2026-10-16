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
