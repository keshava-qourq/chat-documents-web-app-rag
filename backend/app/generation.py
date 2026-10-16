"""Grounded answer generation: turns retrieved chunks into a Gemini answer
that speaks only from what it was given.

`GEMINI_API_KEY` is read through `app.config.gemini_api_key()` at call
time, exactly once per call, and never placed in any returned payload. A
missing key, a Gemini error, or a timeout all raise one of the typed errors
below rather than a bare `Exception` -- the router layer maps these to a
response; retries follow the same bounded-attempts pattern
`app.embeddings.embed_texts` already uses, reusing its retry count so the
two Gemini call sites stay consistent without a second configuration knob.
"""

from dataclasses import dataclass, field
from uuid import UUID

from google import genai

from app.config import embedding_max_retries, gemini_api_key
from app.retrieval import RetrievedContext

GENERATION_MODEL = "gemini-1.5-flash"

NO_DOCUMENTS_MESSAGE = (
    "There are no indexed documents yet. Upload a document on the Documents "
    "screen to start asking questions."
)
NOT_FOUND_PHRASE = "not found in the uploaded documents"
NOT_FOUND_MESSAGE = "This is not found in the uploaded documents."


class GeminiNotConfiguredError(Exception):
    """Raised when `GEMINI_API_KEY` is unset at the moment generation is needed."""


class GenerationServiceError(Exception):
    """Raised once every retry attempt against Gemini has failed, including timeouts."""


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
            last_error = exc

    if text is None:
        raise GenerationServiceError("generation service error") from last_error

    if NOT_FOUND_PHRASE in text.lower():
        return GeneratedAnswer(content=text or NOT_FOUND_MESSAGE, citations=[], grounded=False)

    citations = _citations_for(context)
    return GeneratedAnswer(content=text, citations=citations, grounded=True)


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
    "GenerationServiceError",
    "generate_answer",
    "NO_DOCUMENTS_MESSAGE",
    "NOT_FOUND_MESSAGE",
]
