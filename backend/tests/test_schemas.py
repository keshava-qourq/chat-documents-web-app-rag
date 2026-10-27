"""Unit tests for `app/schemas.py` itself.

This ticket carries no acceptance criteria of its own -- `schemas.py` is
pure Pydantic shape with no endpoint attached. These tests follow the
contract documented in the module's own docstrings and comments instead,
the same approach `test_config.py` and `test_models.py` take for their own
plain-schema modules: defaults, required fields, `from_attributes`
conversion from an ORM-shaped object, the `CitationOut.from_citation`
helper the docstring says routes must use instead of plain
`from_attributes`, and the request models' field validation
(`min_length=1`) that keeps an empty title or question from ever reaching a
route handler.

Other suites (`test_documents.py`, `test_threads.py`, `test_chat_streaming.py`,
...) already exercise several of these shapes indirectly through the
endpoints that return them; this file instead constructs and validates the
models directly, so a regression in a schema's defaults or validation fails
here even if every endpoint happens to pass compatible data through
untouched.

Assumption: since the ticket names no acceptance criteria, tests are named
for the behaviour they cover rather than `test_ac###_...`, matching the
convention already used in `test_config.py` and `test_models.py` for
tickets in the same position.
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


# --- StubResponse -------------------------------------------------------------


def test_stub_response_defaults_status_and_detail() -> None:
    stub = StubResponse(endpoint="GET /widgets")

    assert stub.endpoint == "GET /widgets"
    assert stub.status == "not_implemented"
    assert stub.detail == "Scaffolded from the approved API spec; no behaviour yet."


def test_stub_response_requires_endpoint() -> None:
    with pytest.raises(ValidationError):
        StubResponse()


# --- documents ------------------------------------------------------------


def test_document_accepted_builds_from_an_orm_shaped_object() -> None:
    """`from_attributes=True` is what lets a route hand back a `Document`
    row directly instead of unpacking it into keyword arguments by hand."""
    row = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        size_bytes=100,
        mime_type="application/pdf",
        status="processing",
        uploaded_at=datetime.now(UTC),
    )

    accepted = DocumentAccepted.model_validate(row)

    assert accepted.id == row.id
    assert accepted.file_name == "handbook.pdf"
    assert accepted.status == "processing"


def test_document_rejected_carries_file_name_and_reason() -> None:
    rejected = DocumentRejected(file_name="budget.xlsx", reason="Unsupported file type")

    assert rejected.file_name == "budget.xlsx"
    assert rejected.reason == "Unsupported file type"


def test_upload_response_accepts_empty_lists_on_either_side() -> None:
    response = UploadResponse(accepted=[], rejected=[])

    assert response.accepted == []
    assert response.rejected == []


def test_document_out_progress_and_failure_reason_default() -> None:
    """A document still `processing` has no `failure_reason` and may not
    have had its `progress` set explicitly yet -- both must default rather
    than make every caller pass them."""
    document = DocumentOut(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        size_bytes=100,
        uploaded_at=datetime.now(UTC),
        status="processing",
        chunk_count=0,
    )

    assert document.progress == 0
    assert document.failure_reason is None


def test_document_out_requires_chunk_count() -> None:
    """Unlike `progress`, the docstring gives `chunk_count` no default --
    every caller is expected to supply the real count, not let it default
    to zero silently on a document that has chunks."""
    with pytest.raises(ValidationError):
        DocumentOut(
            id=uuid.uuid4(),
            file_name="handbook.pdf",
            size_bytes=100,
            uploaded_at=datetime.now(UTC),
            status="processing",
        )


def test_document_status_out_requires_progress_with_no_default() -> None:
    with pytest.raises(ValidationError):
        DocumentStatusOut(id=uuid.uuid4(), status="processing")


def test_document_status_out_failure_reason_defaults_to_none() -> None:
    out = DocumentStatusOut(id=uuid.uuid4(), status="ready", progress=100)

    assert out.failure_reason is None


# --- threads and messages -----------------------------------------------------


def test_thread_summary_builds_from_an_orm_shaped_object() -> None:
    row = SimpleNamespace(id=uuid.uuid4(), title="Onboarding", last_active_at=datetime.now(UTC))

    summary = ThreadSummary.model_validate(row)

    assert summary.title == "Onboarding"


def test_thread_created_builds_from_an_orm_shaped_object() -> None:
    row = SimpleNamespace(id=uuid.uuid4(), title="New conversation", created_at=datetime.now(UTC))

    created = ThreadCreated.model_validate(row)

    assert created.title == "New conversation"


def test_thread_rename_request_rejects_an_empty_title() -> None:
    """`Field(min_length=1)` is what keeps an empty-string rename from ever
    reaching `rename_thread` -- distinct from the route's own
    whitespace-only check, which runs after this validation already let the
    string through."""
    with pytest.raises(ValidationError):
        ThreadRenameRequest(title="")


def test_thread_rename_request_accepts_a_non_empty_title() -> None:
    request = ThreadRenameRequest(title="Renamed thread")

    assert request.title == "Renamed thread"


def test_thread_rename_response_round_trips_id_and_title() -> None:
    thread_id = uuid.uuid4()

    response = ThreadRenameResponse(id=thread_id, title="Renamed thread")

    assert response.id == thread_id
    assert response.title == "Renamed thread"


# --- CitationOut and its from_citation helper --------------------------------


def test_citation_out_document_available_defaults_true_on_direct_construction() -> None:
    citation = CitationOut(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="p.1",
        excerpt="an excerpt",
    )

    assert citation.document_available is True


def test_from_citation_reports_available_when_chunk_id_is_set() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="p.1",
        excerpt="an excerpt",
        chunk_id=uuid.uuid4(),
    )

    out = CitationOut.from_citation(row)

    assert out.document_available is True


def test_from_citation_reports_unavailable_when_chunk_id_is_none() -> None:
    """The module comment explains this is the whole reason the helper
    exists: `chunk_id` goes `NULL` once the backing chunk (or its document)
    has been deleted, and that must surface as `document_available=False`
    rather than silently defaulting to `True` the way plain
    `from_attributes` construction would (there is no `document_available`
    column for it to find)."""
    row = SimpleNamespace(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="p.1",
        excerpt="an excerpt",
        chunk_id=None,
    )

    out = CitationOut.from_citation(row)

    assert out.document_available is False


def test_message_out_citations_default_to_an_empty_list() -> None:
    message = MessageOut(id=uuid.uuid4(), role="assistant", content="hello", status="complete")

    assert message.citations == []


def test_thread_detail_messages_default_to_an_empty_list() -> None:
    detail = ThreadDetail(id=uuid.uuid4(), title="Empty thread")

    assert detail.messages == []


def test_message_create_request_rejects_an_empty_question() -> None:
    with pytest.raises(ValidationError):
        MessageCreateRequest(question="")


def test_message_create_request_accepts_a_non_empty_question() -> None:
    request = MessageCreateRequest(question="What is the refund policy?")

    assert request.question == "What is the refund policy?"


def test_message_stream_final_citations_default_to_an_empty_list() -> None:
    final = MessageStreamFinal(message_id=uuid.uuid4())

    assert final.citations == []


def test_message_stream_final_requires_message_id() -> None:
    with pytest.raises(ValidationError):
        MessageStreamFinal()
