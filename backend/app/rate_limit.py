"""Per-IP rate limiting, shared by every endpoint the API spec marks as
rate limited.

The architecture requires uploads and chat to reject with 429 *before* any
Gemini call or file store -- that is a property of the endpoint contract
itself, not behaviour a handler opts into later, so the limiter is wired up
here and attached to the app in `main.py` rather than left for the
development sprint to discover. The actual limit values come from
`app.config`, which reads them from the environment with documented
defaults.

Limits are applied via `@limiter.limit(lambda: f"{...}/minute")` -- a
*callable*, not a literal string -- in `threads.py` and `documents.py`.
slowapi resolves a callable limit value on every request (it is stored
inside a `LimitGroup` and only called when the limit is actually checked,
not once at decoration time), so `RATE_LIMIT_CHAT_PER_MIN` and
`RATE_LIMIT_UPLOADS_PER_HOUR` are genuinely read from the environment at
request time -- AC-064's requirement -- and not frozen into the limit at
import time. Nothing further is needed here to make that true; this module
only adds the one thing slowapi does not provide out of the box: a JSON
error body in the exact shape the frontend parses.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

RATE_LIMIT_MESSAGE = "Too many requests, try again shortly."


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Replaces slowapi's default handler, which returns its own
    `{"error": "..."}` (or plain text) body. The frontend already parses
    `{"detail": "..."}` for every other error response in this API, so a
    breached rate limit must use that same shape rather than a one-off.
    """
    return JSONResponse(status_code=429, content={"detail": RATE_LIMIT_MESSAGE})
