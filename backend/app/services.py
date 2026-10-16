"""The backing services this application is configured to reach.

Each entry maps a service to the environment variable that addresses it. The
MinIO value comes from docker-compose.yml through .env.example; GEMINI_API_KEY
is set by the product owner before deployment, not by the scaffold, so this
reports `false` until then rather than failing anything. Either way, the
health check reports what the running deployment can actually reach -- it
never calls Gemini itself.
"""

import os

SERVICES = {
    "minio": "MINIO_ENDPOINT",
    "gemini": "GEMINI_API_KEY",
}


def configured_services() -> dict[str, bool]:
    """Each service mapped to whether its connection variable is set."""
    return {name: bool(os.getenv(var)) for name, var in SERVICES.items()}


# --- thread auto-titling -------------------------------------------------

TITLE_MAX_LENGTH = 60
_ELLIPSIS = "…"


def derive_title(question: str, max_length: int = TITLE_MAX_LENGTH) -> str:
    """A short, sidebar-safe title derived from a thread's first question.

    Collapses internal whitespace, then truncates at the last whole word
    that still fits so the result never breaks mid-word, appending an
    ellipsis when it was shortened. The result is always at most
    `max_length` characters -- the sidebar this is rendered in cannot be
    overflowed by it.
    """
    text = " ".join(question.split())
    if not text:
        return "New conversation"
    if len(text) <= max_length:
        return text

    limit = max_length - len(_ELLIPSIS)
    truncated = text[:limit]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    truncated = truncated.rstrip()
    if not truncated:
        # A single word longer than the limit -- there is no word boundary
        # to cut at, so a hard cut is the only option.
        truncated = text[:limit]
    return truncated + _ELLIPSIS


def request_answer(question: str, context: list[dict[str, str]]) -> None:
    """Seam the message endpoint hands the persisted question (and the
    thread's earlier turns as `context`) to.

    Grounded answer generation -- retrieval, the Gemini call, and persisting
    an assistant message with de-duplicated citations -- is its own story;
    this seam exists so that story only has to fill in a function body, not
    change where or how it is called from.
    """
    return None
