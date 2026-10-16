"""The backing services this application is configured to reach, plus the
chat generation seam `routers.threads.post_message` hands the persisted
question to.

Each entry in `SERVICES` maps a service to the environment variable that
addresses it. The MinIO value comes from docker-compose.yml through
.env.example; GEMINI_API_KEY is set by the product owner before deployment,
not by the scaffold, so this reports `false` until then rather than failing
anything. Either way, the health check reports what the running deployment
can actually reach -- it never calls Gemini itself.
"""

import json
import os
from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.generation import (
    NO_DOCUMENTS_MESSAGE,
    NOT_FOUND_MESSAGE,
    NOT_FOUND_PHRASE,
    GeminiNotConfiguredError,
    GenerationServiceError,
    stream_answer,
)
from app.models import Citation, Document, Message, Thread
from app.retrieval import retrieve_context

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


# --- grounded chat generation ---------------------------------------------

# Character budget (not token count -- consistent with the character-based
# chunk sizing `app.config.chunk_size()` already uses) the thread's prior
# turns are trimmed to before being handed to Gemini. Keeps a long thread's
# history from ever pushing the generation request over Gemini's context
# limit while still returning an answer, rather than erroring once a thread
# gets long. Documented and overridable like every other budget in this
# service, read at call time, not frozen at import.
HISTORY_CHAR_BUDGET_DEFAULT = 8000

# How many of the most recent turns are folded into the text used to query
# `retrieve_context` -- enough for a pronoun ("it", "the second one") to
# resolve against the immediately preceding turn, without inflating the
# embedding call with the whole (possibly much longer) trimmed history used
# for the generation prompt itself.
QUERY_HISTORY_MESSAGES = 6


def history_char_budget() -> int:
    """Characters of prior-turn history kept for one generation call."""
    return int(os.getenv("HISTORY_CHAR_BUDGET", str(HISTORY_CHAR_BUDGET_DEFAULT)))


def trim_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keeps the most recent turns of `history` under `history_char_budget()`.

    Walks from the newest turn backwards, always keeping at least the single
    most recent turn even if it alone exceeds the budget, and drops older
    turns once the running total would exceed it -- so a long thread is
    trimmed to its most recent relevant turns rather than failing the
    request or silently dropping the newest context.
    """
    budget = history_char_budget()
    kept: list[dict[str, str]] = []
    total = 0
    for turn in reversed(history):
        length = len(turn.get("content", ""))
        if kept and total + length > budget:
            break
        kept.append(turn)
        total += length
    kept.reverse()
    return kept


def has_ready_documents(db: Session) -> bool:
    """`True` once at least one document in the shared library is `'ready'`.

    Cheap existence query -- never embeds or calls Gemini -- so the chat
    endpoint can answer the NO_DOCUMENTS_INDEXED contract before any stream
    starts and before any Gemini call is made.
    """
    return db.query(Document.id).filter(Document.status == "ready").first() is not None


def _augmented_query(question: str, history: list[dict[str, str]]) -> str:
    """Folds the thread's most recent turns into the text handed to
    `retrieve_context`, so a follow-up question that only makes sense in
    light of the prior turn ("what about the second one?") retrieves against
    what it actually refers to, not the pronoun alone.
    """
    if not history:
        return question
    recent = history[-QUERY_HISTORY_MESSAGES:]
    recap = " ".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in recent)
    return f"{recap}\nuser: {question}"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _persist_incomplete(db: Session, thread: Thread, content: str) -> None:
    message = Message(thread_id=thread.id, role="assistant", content=content, status="incomplete")
    db.add(message)
    db.commit()


def request_answer(
    db: Session,
    thread: Thread,
    question: str,
    history: list[dict[str, str]],
) -> Generator[str, None, None]:
    """The seam `post_message` hands the persisted question and the thread's
    own prior turns to.

    `history` is always queried by the caller scoped to `thread.id` alone --
    this function never reaches across threads. Retrieval is whole-library
    (per `app.retrieval`), but the *query* used to search it is folded
    together with this thread's own recent turns via `_augmented_query`, and
    the trimmed history is passed into the generation prompt itself, so a
    follow-up question resolves against this thread's earlier turns and no
    other thread's.

    Streams the Gemini answer token-by-token as SSE 'token' events. On
    completion, persists the assistant `Message` (status='complete') and its
    de-duplicated `Citation` rows, then emits one 'final' event carrying
    `{message_id, citations[]}`. If generation errors or the stream is
    interrupted after at least one token was produced, the partial answer is
    persisted with status='incomplete' and an 'error' event is emitted
    instead -- either way, the thread accepts another question afterwards.
    """
    trimmed_history = trim_history(history)

    try:
        context = retrieve_context(db, _augmented_query(question, trimmed_history))
    except Exception:
        yield _sse("error", {"detail": "Could not retrieve context for this question."})
        return

    if not context.chunks:
        # Covers both "no ready documents" and "nothing above threshold" --
        # the same user-facing outcome as `generate_answer`'s no-context
        # branch, and neither spends a generation call.
        message = Message(
            thread_id=thread.id,
            role="assistant",
            content=NO_DOCUMENTS_MESSAGE,
            status="complete",
        )
        db.add(message)
        thread.last_active_at = datetime.now(UTC)
        db.commit()
        db.refresh(message)
        yield _sse("token", {"text": message.content})
        yield _sse("final", {"message_id": str(message.id), "citations": []})
        return

    collected = ""
    try:
        for piece in stream_answer(question, context, trimmed_history):
            if not piece:
                continue
            collected += piece
            yield _sse("token", {"text": piece})
    except GeminiNotConfiguredError:
        if collected:
            _persist_incomplete(db, thread, collected)
        yield _sse("error", {"detail": "Gemini is not configured."})
        return
    except GenerationServiceError:
        if collected:
            _persist_incomplete(db, thread, collected)
        yield _sse("error", {"detail": "The answer generation service is unavailable."})
        return
    except Exception:
        if collected:
            _persist_incomplete(db, thread, collected)
        yield _sse("error", {"detail": "The answer was interrupted."})
        return

    text = collected.strip()

    if not text or NOT_FOUND_PHRASE in text.lower():
        message = Message(
            thread_id=thread.id,
            role="assistant",
            content=text or NOT_FOUND_MESSAGE,
            status="complete",
        )
        db.add(message)
        thread.last_active_at = datetime.now(UTC)
        db.commit()
        db.refresh(message)
        yield _sse("final", {"message_id": str(message.id), "citations": []})
        return

    message = Message(thread_id=thread.id, role="assistant", content=text, status="complete")
    db.add(message)
    db.flush()

    seen: set[tuple[str, str | None]] = set()
    citations: list[Citation] = []
    for chunk in context.chunks:
        key = (chunk.document_name, chunk.source_location)
        if key in seen:
            continue
        seen.add(key)
        citation = Citation(
            message_id=message.id,
            chunk_id=chunk.chunk_id,
            document_name=chunk.document_name,
            source_location=chunk.source_location,
            excerpt=chunk.content,
        )
        db.add(citation)
        citations.append(citation)

    thread.last_active_at = datetime.now(UTC)
    db.commit()
    db.refresh(message)
    for citation in citations:
        db.refresh(citation)

    citations_payload = [
        {
            "id": str(c.id),
            "document_name": c.document_name,
            "source_location": c.source_location,
            "excerpt": c.excerpt,
            "document_available": c.chunk_id is not None,
        }
        for c in citations
    ]
    yield _sse("final", {"message_id": str(message.id), "citations": citations_payload})


__all__ = [
    "configured_services",
    "derive_title",
    "has_ready_documents",
    "history_char_budget",
    "trim_history",
    "request_answer",
]
