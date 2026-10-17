"""Grounded answer generation: turns retrieved chunks into a Gemini answer
that speaks only from what it was given.

`GEMINI_API_KEY` is read through `app.config.gemini_api_key()` at call
time, exactly once per call, and never placed in any returned payload. A
missing key, a Gemini error, or a timeout all raise one of the typed errors
below rather than a bare `Exception` -- the router layer maps these to a
response; retries follow the same bounded-attempts pattern
`app.embeddings.embed_texts` already uses, reusing its retry count so the
two Gemini call sites stay consistent without a second configuration knob.

A key Gemini itself rejects (401/403) is detected the same way
`app.embeddings` detects it -- it cannot possibly succeed on retry, so it is
raised immediately as `GeminiKeyRejectedError` naming the upstream status,
rather than exhausted through every retry attempt and reported as a generic
`GenerationServiceError`.

`stream_answer` is the streaming counterpart `app.services.request_answer`
calls for `POST /threads/{id}/messages`: it yields plain-text deltas as
Gemini produces them instead of returning one complete `GeneratedAnswer`.
Retrying before any text has reached the caller makes sense (nothing has
been sent yet); retrying *after* a token has already been streamed out does
not, since the caller cannot un-send it -- so `stream_answer` retries a
failure that happens before the first token, and simply lets a failure
after the first token propagate as an interruption for the caller to handle.
"""

from dataclasses import dataclass, field
from uuid import UUID

from google import genai

from app.config import embedding_max_retries, gemini_api_key
from app.retrieval import RetrievedContext

GENERATION_MODEL = "gemini-1.5-flash"

NO_DOCUMENTS_MESSAGE = (
    "There are no documents indexed yet. Upload a document on the Documents "
    "screen to start asking questions."
)
NOT_FOUND_PHRASE = "not found in the uploaded documents"
NOT_FOUND_MESSAGE = "This is not found in the uploaded documents."


class GeminiNotConfiguredError(Exception):
    """Raised when `GEMINI_API_KEY` is unset at the moment generation is needed."""

    code = "gemini_not_configured"


class GeminiKeyRejectedError(Exception):
    """Raised when Gemini itself rejects `GEMINI_API_KEY` (HTTP 401/403)."""

    code = "gemini_key_rejected"

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GenerationServiceError(Exception):
    """Raised once every retry attempt against Gemini has failed, including timeouts."""


def _rejected_status(exc: Exception) -> int | None:
    """The upstream HTTP status if `exc` looks like Gemini rejecting the API
    key, else `None`. Same detection `app.embeddings._rejected_status` uses,
    kept local here rather than imported so this module's only Gemini
    dependency stays `google-genai` itself.
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


@dataclass
class Citation:
    """One source a generated answer points back to."""

    document_name: str
    source_location: str | None
    excerpt: str
    chunk_id: UUID


@dataclass
class GeneratedAnswer:
    """What `generate_answer` returns."""

    content: str
    citations: list[Citation] = field(default_factory=list)
    grounded: bool = True


def generate_answer(
    question: str,
    context: RetrievedContext,
    history: list[dict[str, str]] | None = None,
) -> GeneratedAnswer:
    """Generates an answer from `context` only, or a no-context/not-found
    result without ever calling Gemini when there is nothing to ground on.
    """
    history = history or []

    if not context.chunks:
        # Covers both "no 'ready' documents exist" and "retrieval yielded
        # zero chunks above threshold" -- both are the same user-facing
        # situation and neither should spend a Gemini call.
        return GeneratedAnswer(content=NO_DOCUMENTS_MESSAGE, citations=[], grounded=False)

    api_key = gemini_api_key()
    if not api_key:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not configured")

    prompt = _build_prompt(question, context, history)
    client = genai.Client(api_key=api_key)
    attempts = max(1, embedding_max_retries())
    last_error: Exception | None = None
    text: str | None = None

    for _ in range(attempts):
        try:
            result = client.models.generate_content(model=GENERATION_MODEL, contents=prompt)
            text = (getattr(result, "text", None) or "").strip()
            break
        except Exception as exc:  # noqa: BLE001 -- any Gemini/network failure is retried
            status = _rejected_status(exc)
            if status is not None:
                raise GeminiKeyRejectedError(
                    f"GEMINI_API_KEY was rejected by Gemini (status {status})",
                    status_code=status,
                ) from exc
            last_error = exc

    if text is None:
        raise GenerationServiceError("generation service error") from last_error

    if NOT_FOUND_PHRASE in text.lower():
        return GeneratedAnswer(content=text or NOT_FOUND_MESSAGE, citations=[], grounded=False)

    citations = _citations_for(context)
    return GeneratedAnswer(content=text, citations=citations, grounded=True)


def stream_answer(
    question: str,
    context: RetrievedContext,
    history: list[dict[str, str]] | None = None,
):
    """Streams an answer from `context` token-by-token via Gemini's
    streaming `generate_content` call, yielding plain-text deltas as they
    arrive.

    Never called with an empty `context.chunks` -- the caller (`app.services
    .request_answer`) short-circuits that case itself, the same way
    `generate_answer` does, without spending a Gemini call. Raises
    `GeminiNotConfiguredError` immediately if the key is unset, and retries
    opening the stream itself (same bounded-attempts count as every other
    Gemini call site here) before any text has been yielded; once the first
    chunk has been yielded to the caller, any further failure propagates
    as-is so the caller can treat it as a mid-stream interruption rather
    than silently retrying a request the caller may have already shown
    partial output for. A rejected key is detected the same way as
    `generate_answer` and raised immediately, before any retry, whether it
    is the first attempt or a retried one.
    """
    history = history or []
    api_key = gemini_api_key()
    if not api_key:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not configured")

    prompt = _build_prompt(question, context, history)
    client = genai.Client(api_key=api_key)
    attempts = max(1, embedding_max_retries())
    last_error: Exception | None = None
    stream = None

    for _ in range(attempts):
        try:
            stream = client.models.generate_content_stream(model=GENERATION_MODEL, contents=prompt)
            break
        except Exception as exc:  # noqa: BLE001 -- retried while nothing has streamed yet
            status = _rejected_status(exc)
            if status is not None:
                raise GeminiKeyRejectedError(
                    f"GEMINI_API_KEY was rejected by Gemini (status {status})",
                    status_code=status,
                ) from exc
            last_error = exc

    if stream is None:
        raise GenerationServiceError("generation service error") from last_error

    for chunk in stream:
        text = getattr(chunk, "text", None)
        if text:
            yield text


def _build_prompt(
    question: str,
    context: RetrievedContext,
    history: list[dict[str, str]],
) -> str:
    chunks_block = "\n\n".join(
        f"[{i + 1}] (Source: {chunk.document_name}, {chunk.source_location or 'n/a'})\n"
        f"{chunk.content}"
        for i, chunk in enumerate(context.chunks)
    )
    history_block = (
        "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history)
        or "(none)"
    )
    return (
        "You are a documents-only assistant answering questions about a shared "
        "document library. Answer the QUESTION using ONLY the CONTEXT chunks "
        "below. Never use outside knowledge and never guess.\n\n"
        f"CONVERSATION HISTORY:\n{history_block}\n\n"
        f"CONTEXT:\n{chunks_block}\n\n"
        f"QUESTION:\n{question}\n\n"
        "Rules:\n"
        f"- If the context does not cover the question at all, respond with exactly: "
        f'"{NOT_FOUND_MESSAGE}" and nothing else.\n'
        "- If the context covers only part of the question, answer the "
        "supported part using the context, citing it, and then explicitly "
        "state which part of the question is not covered by the documents.\n"
        "- Never invent a citation to a source that is not in CONTEXT."
    )


def _citations_for(context: RetrievedContext) -> list[Citation]:
    """De-duplicated per `(document_name, source_location)`, containing only
    chunks that were actually retrieved for this answer -- never a chunk
    generation merely mentions by name."""
    seen: set[tuple[str, str | None]] = set()
    citations: list[Citation] = []
    for chunk in context.chunks:
        key = (chunk.document_name, chunk.source_location)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document_name=chunk.document_name,
                source_location=chunk.source_location,
                excerpt=chunk.content[:300],
                chunk_id=chunk.chunk_id,
            )
        )
    return citations


__all__ = [
    "Citation",
    "GeneratedAnswer",
    "GeminiNotConfiguredError",
    "GeminiKeyRejectedError",
    "GenerationServiceError",
    "generate_answer",
    "stream_answer",
    "NO_DOCUMENTS_MESSAGE",
    "NOT_FOUND_MESSAGE",
]
