"""Unit tests for `app.schemas`.

Every other suite in `backend/tests/` exercises these models only
indirectly, through a route's `response_model` or request body -- which
proves a route wires a schema in correctly, but never pins down what the
schema itself does on its own: what a bare validation error looks like with
nothing supplied, what a field defaults to when a caller or the ORM leaves
it out, and what `CitationOut.from_citation` computes from a `chunk_id` that
is `None` versus one that isn't. Those are this module's job, built
directly against pydantic with no FastAPI app, no database and no HTTP
client involved.

`from_attributes` mapping is proven against a plain `SimpleNamespace` rather
than a real ORM row: these models are agnostic to where their data comes
from, and `app.models` already has its own suite proving the ORM side of
that contract.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas import (
    CitationOut,
    DocumentAccepted,
    DocumentOut,
    DocumentRejected,
    DocumentStatusOut,
    MessageCreateRequest,
    MessageOut,
    MessageStreamFinal,
    StubResponse,
    ThreadCreated,
    ThreadDetail,
    ThreadRenameRequest,
    ThreadRenameResponse,
    ThreadSummary,
    UploadResponse,
)

# --- StubResponse -------------------------------------------------------


def test_stub_response_requires_endpoint_and_defaults_status_and_detail() -> None:
    stub = StubResponse(endpoint="/example")

    assert stub.endpoint == "/example"
    assert stub.status == "not_implemented"
    assert stub.detail == "Scaffolded from the approved API spec; no behaviour yet."


def test_stub_response_without_an_endpoint_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StubResponse()


# --- documents ------------------------------------------------------------


def test_document_accepted_builds_from_an_orm_like_object_via_from_attributes() -> None:
    orm_like = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        size_bytes=100,
        mime_type="application/pdf",
        status="processing",
        uploaded_at=datetime.now(UTC),
    )

    accepted = DocumentAccepted.model_validate(orm_like)

    assert accepted.file_name == "handbook.pdf"
    assert accepted.status == "processing"


def test_document_rejected_carries_file_name_and_reason() -> None:
    rejected = DocumentRejected(file_name="budget.xlsx", reason="Unsupported file type.")

    assert rejected.file_name == "budget.xlsx"
    assert rejected.reason == "Unsupported file type."


def test_upload_response_bundles_accepted_and_rejected_lists_independently() -> None:
    response = UploadResponse(
        accepted=[
            DocumentAccepted(
                id=uuid.uuid4(),
                file_name="a.txt",
                size_bytes=1,
                mime_type="text/plain",
                status="processing",
                uploaded_at=datetime.now(UTC),
            )
        ],
        rejected=[DocumentRejected(file_name="b.xlsx", reason="nope")],
    )

    assert len(response.accepted) == 1
    assert len(response.rejected) == 1
    assert response.accepted[0].file_name == "a.txt"
    assert response.rejected[0].file_name == "b.xlsx"


def test_upload_response_requires_both_lists_even_if_one_would_be_empty() -> None:
    # Unlike `MessageOut.citations` below, neither list here has a default --
    # a caller constructing this model must supply both explicitly.
    with pytest.raises(ValidationError):
        UploadResponse(accepted=[])


def test_document_out_defaults_progress_to_zero_and_failure_reason_to_none() -> None:
    document = DocumentOut(
        id=uuid.uuid4(),
        file_name="a.txt",
        size_bytes=1,
        uploaded_at=datetime.now(UTC),
        status="processing",
        chunk_count=0,
    )

    assert document.progress == 0
    assert document.failure_reason is None


def test_document_out_accepts_an_explicit_progress_and_failure_reason() -> None:
    document = DocumentOut(
        id=uuid.uuid4(),
        file_name="a.txt",
        size_bytes=1,
        uploaded_at=datetime.now(UTC),
        status="failed",
        progress=100,
        failure_reason="Could not extract text.",
        chunk_count=0,
    )

    assert document.progress == 100
    assert document.failure_reason == "Could not extract text."


def test_document_out_builds_from_an_orm_like_object_including_the_live_progress_field() -> None:
    orm_like = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="a.txt",
        size_bytes=1,
        uploaded_at=datetime.now(UTC),
        status="processing",
        progress=40,
        failure_reason=None,
        chunk_count=3,
    )

    document = DocumentOut.model_validate(orm_like)

    assert document.progress == 40
    assert document.chunk_count == 3


def test_document_status_out_failure_reason_defaults_to_none() -> None:
    status_out = DocumentStatusOut(id=uuid.uuid4(), status="processing", progress=40)

    assert status_out.failure_reason is None


def test_document_status_out_builds_from_an_orm_like_object() -> None:
    orm_like = SimpleNamespace(id=uuid.uuid4(), status="failed", progress=100, failure_reason="boom")

    status_out = DocumentStatusOut.model_validate(orm_like)

    assert status_out.status == "failed"
    assert status_out.failure_reason == "boom"


# --- threads and messages -------------------------------------------------


def test_thread_summary_builds_from_an_orm_like_object() -> None:
    orm_like = SimpleNamespace(id=uuid.uuid4(), title="My thread", last_active_at=datetime.now(UTC))

    summary = ThreadSummary.model_validate(orm_like)

    assert summary.title == "My thread"


def test_thread_created_builds_from_an_orm_like_object() -> None:
    orm_like = SimpleNamespace(
        id=uuid.uuid4(), title="New conversation", created_at=datetime.now(UTC)
    )

    created = ThreadCreated.model_validate(orm_like)

    assert created.title == "New conversation"


def test_thread_rename_request_rejects_an_empty_title() -> None:
    with pytest.raises(ValidationError):
        ThreadRenameRequest(title="")


def test_thread_rename_request_accepts_a_non_empty_title() -> None:
    request = ThreadRenameRequest(title="Renamed thread")

    assert request.title == "Renamed thread"


def test_thread_rename_response_carries_id_and_title() -> None:
    thread_id = uuid.uuid4()
    response = ThreadRenameResponse(id=thread_id, title="Renamed")

    assert response.id == thread_id
    assert response.title == "Renamed"


def test_citation_out_from_citation_marks_document_available_when_chunk_id_is_set() -> None:
    citation = SimpleNamespace(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="p.3",
        excerpt="Expenses must be submitted within 30 days.",
        chunk_id=uuid.uuid4(),
    )

    out = CitationOut.from_citation(citation)

    assert out.document_available is True


def test_citation_out_from_citation_marks_document_unavailable_when_chunk_id_is_none() -> None:
    """The exact case the docstring on `CitationOut.document_available` calls
    out: a chunk (or its whole document) deleted after the citation was
    created leaves `chunk_id` `NULL`, and `from_citation` is what turns that
    into the flag the frontend uses to grey the citation out."""
    citation = SimpleNamespace(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location=None,
        excerpt="Expenses must be submitted within 30 days.",
        chunk_id=None,
    )

    out = CitationOut.from_citation(citation)

    assert out.document_available is False


def test_citation_out_constructed_directly_defaults_document_available_to_true() -> None:
    citation = CitationOut(id=uuid.uuid4(), document_name="a.txt", excerpt="an excerpt")

    assert citation.document_available is True


def test_message_out_citations_default_to_an_empty_list() -> None:
    message = MessageOut(id=uuid.uuid4(), role="assistant", content="an answer", status="complete")

    assert message.citations == []


def test_message_out_carries_explicit_citations() -> None:
    citation = CitationOut(id=uuid.uuid4(), document_name="a.txt", excerpt="an excerpt")
    message = MessageOut(
        id=uuid.uuid4(),
        role="assistant",
        content="an answer",
        status="complete",
        citations=[citation],
    )

    assert len(message.citations) == 1
    assert message.citations[0].document_name == "a.txt"


def test_thread_detail_messages_default_to_an_empty_list() -> None:
    detail = ThreadDetail(id=uuid.uuid4(), title="New conversation")

    assert detail.messages == []


def test_message_create_request_rejects_an_empty_question() -> None:
    with pytest.raises(ValidationError):
        MessageCreateRequest(question="")


def test_message_create_request_accepts_a_non_empty_question() -> None:
    request = MessageCreateRequest(question="Where is the expenses policy?")

    assert request.question == "Where is the expenses policy?"


def test_message_stream_final_citations_default_to_an_empty_list() -> None:
    final = MessageStreamFinal(message_id=uuid.uuid4())

    assert final.citations == []


def test_message_stream_final_requires_a_message_id() -> None:
    with pytest.raises(ValidationError):
        MessageStreamFinal()
