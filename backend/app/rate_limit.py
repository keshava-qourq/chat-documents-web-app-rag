"""Per-IP rate limiting, shared by every endpoint the API spec marks as
rate limited.

The architecture requires uploads and chat to reject with 429 *before* any
Gemini call or file store -- that is a property of the endpoint contract
itself, not behaviour a handler opts into later, so the limiter is wired up
here and attached to the app in `main.py` rather than left for the
development sprint to discover. The actual limit values come from
`app.config`, which reads them from the environment with documented
defaults.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
