"""Tests for `app.generation.generate_answer`: no-context behaviour,
not-found grounding, partial coverage, de-duplicated citations, and typed
errors for a missing key or a Gemini failure.

No live Gemini call anywhere in this module -- `genai.Client` is
monkeypatched to a fake that records the prompt it was given and returns a
scripted response.
"""

import uuid

import pytest

from app import generation
from app.retrieval import RetrievedChunk, RetrievedContext


def _chunk(document_name="handbook.pdf", source_location="handbook.pdf, page 1", content="text"):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        source_location=source_location,
        content=content,
        similarity=0.9,
    )


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, texts_or_exc):
        self._texts_or_exc = texts_or_exc
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append(contents)
        item = (
            self._texts_or_exc.pop(0)
            if isinstance(self._texts_or_exc, list)
            else self._texts_or_exc
        )
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


def _install_fake_client(monkeypatch, models: _FakeModels):
    class Factory:
        def __call__(self, api_key):
            return type("C", (), {"models": models})()

    monkeypatch.setattr(generation.genai, "Client", Factory())


def test_no_ready_documents_returns_no_context_without_calling_gemini(monkeypatch) -> None:
    def fail_client(api_key):
        raise AssertionError("Gemini must not be called with no context")

    monkeypatch.setattr(generation.genai, "Client", fail_client)

    context = RetrievedContext(chunks=[], has_ready_documents=False)
    answer = generation.generate_answer("What is the policy?", context)

    assert answer.grounded is False
    assert answer.citations == []
    assert "no indexed documents" in answer.content.lower()
    assert "documents" in answer.content.lower()


def test_zero_chunks_above_threshold_also_returns_no_context(monkeypatch) -> None:
    def fail_client(api_key):
        raise AssertionError("Gemini must not be called")

    monkeypatch.setattr(generation.genai, "Client", fail_client)

    context = RetrievedContext(chunks=[], has_ready_documents=True)
    answer = generation.generate_answer("What is the policy?", context)

    assert answer.grounded is False
    assert answer.citations == []


def test_missing_api_key_raises_typed_error(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GeminiNotConfiguredError):
        generation.generate_answer("question", context)


def test_gemini_failure_after_retries_raises_typed_service_error(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")
    models = _FakeModels(RuntimeError("boom"))
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    with pytest.raises(generation.GenerationServiceError):
        generation.generate_answer("question", context)


def test_question_not_covered_by_chunks_returns_not_found_with_no_citations(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels([generation.NOT_FOUND_MESSAGE])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("unrelated question", context)

    assert answer.grounded is False
    assert answer.citations == []
    assert "not found in the uploaded documents" in answer.content.lower()


def test_grounded_answer_returns_deduplicated_citations_from_retrieved_chunks_only(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    chunk_one = _chunk(source_location="handbook.pdf, page 1")
    chunk_two = _chunk(source_location="handbook.pdf, page 1")  # same (doc, location)
    chunk_three = _chunk(source_location="handbook.pdf, page 2")
    context = RetrievedContext(
        chunks=[chunk_one, chunk_two, chunk_three], has_ready_documents=True
    )

    answer = generation.generate_answer("How many leave days?", context)

    assert answer.grounded is True
    assert len(answer.citations) == 2
    locations = {(c.document_name, c.source_location) for c in answer.citations}
    assert locations == {
        ("handbook.pdf", "handbook.pdf, page 1"),
        ("handbook.pdf", "handbook.pdf, page 2"),
    }
    retrieved_ids = {c.chunk_id for c in context.chunks}
    for citation in answer.citations:
        assert citation.chunk_id in retrieved_ids


def test_partial_coverage_answer_is_returned_grounded_with_citations(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    text = (
        "Employees get 25 days of annual leave [1]. "
        "The documents do not cover remote-work stipends for contractors."
    )
    models = _FakeModels([text])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer(
        "How many leave days, and what is the contractor remote-work stipend?", context
    )

    assert answer.grounded is True
    assert len(answer.citations) == 1
    assert "do not cover" in answer.content.lower()


def test_api_key_never_appears_in_the_returned_answer(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    models = _FakeModels(["Employees get 25 days of annual leave. [1]"])
    _install_fake_client(monkeypatch, models)
    context = RetrievedContext(chunks=[_chunk()], has_ready_documents=True)

    answer = generation.generate_answer("How many leave days?", context)

    assert "super-secret-key" not in answer.content
    assert all("super-secret-key" not in (c.excerpt or "") for c in answer.citations)
