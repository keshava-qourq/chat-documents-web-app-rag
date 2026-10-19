"""Unit tests for `app.schemas`: the Pydantic shapes themselves, not the
routes that happen to return them.

`backend/tests/test_documents.py` and `test_threads.py` already prove these
shapes end-to-end through the HTTP surface; this file instead targets what
only a direct, schema-level test can reach cheaply and precisely: the
documented defaults each model falls back to with no input, `from_attributes`
validating straight off a plain object with matching attributes (standing in
for an ORM row, without needing a database at all), the one field
(`CitationOut.document_available`) that is *not* an ORM attribute and is
built explicitly by `CitationOut.from_citation`, and the `Field(min_length=1)`
validation on the two free-text request bodies (`ThreadRenameRequest`,
`MessageCreateRequest`) -- including the whitespace-only string that this
schema-level constraint does *not* reject, because stripping and rejecting
it is `app.routers.threads.rename_thread`'s job, not this field's.
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

# --- StubResponse ------------------------------------------------------------


def test_stub_response_fills_in_its_documented_defaults_from_just_an_endpoint() -> None:
    stub = StubResponse(endpoint="/some/future/route")

    assert stub.endpoint == "/some/future/route"
    assert stub.status == "not_implemented"
    assert stub.detail == "Scaffolded from the approved API spec; no behaviour yet."


# --- documents: from_attributes off a plain object, not a real ORM row ------


def test_document_accepted_validates_from_an_object_with_matching_attributes() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        size_bytes=1024,
        mime_type="application/pdf",
        status="processing",
        uploaded_at=datetime.now(UTC),
    )

    accepted = DocumentAccepted.model_validate(row)

    assert accepted.file_name == "handbook.pdf"
    assert accepted.status == "processing"


def test_document_rejected_requires_both_file_name_and_reason() -> None:
    rejected = DocumentRejected(file_name="budget.xlsx", reason="Unsupported file type.")
    assert rejected.file_name == "budget.xlsx"

    with pytest.raises(ValidationError):
        DocumentRejected(file_name="budget.xlsx")


def test_upload_response_keeps_accepted_and_rejected_as_separate_lists() -> None:
    accepted_row = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="ok.txt",
        size_bytes=10,
        mime_type="text/plain",
        status="processing",
        uploaded_at=datetime.now(UTC),
    )

    response = UploadResponse(
        accepted=[DocumentAccepted.model_validate(accepted_row)],
        rejected=[DocumentRejected(file_name="bad.xlsx", reason="Unsupported file type.")],
    )

    assert len(response.accepted) == 1
    assert len(response.rejected) == 1
    assert response.accepted[0].file_name == "ok.txt"
    assert response.rejected[0].file_name == "bad.xlsx"


def test_document_out_defaults_progress_to_zero_and_failure_reason_to_none_when_absent() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        size_bytes=1024,
        uploaded_at=datetime.now(UTC),
        status="processing",
        chunk_count=0,
        # `progress` and `failure_reason` intentionally left off the row:
        # a freshly-inserted `Document` carries `progress=0` from its own
        # column default, so this is the shape the listing must still
        # produce even from an object that omits them entirely.
    )

    document_out = DocumentOut.model_validate(row)

    assert document_out.progress == 0
    assert document_out.failure_reason is None


def test_document_out_surfaces_a_nonzero_progress_and_a_failure_reason_when_present() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        size_bytes=1024,
        uploaded_at=datetime.now(UTC),
        status="failed",
        progress=40,
        failure_reason="Could not extract text from this PDF.",
        chunk_count=0,
    )

    document_out = DocumentOut.model_validate(row)

    assert document_out.progress == 40
    assert document_out.failure_reason == "Could not extract text from this PDF."


def test_document_status_out_round_trips_all_four_fields() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        status="processing",
        progress=65,
        failure_reason=None,
    )

    status_out = DocumentStatusOut.model_validate(row)

    assert status_out.status == "processing"
    assert status_out.progress == 65
    assert status_out.failure_reason is None


# --- threads and messages ----------------------------------------------------


def test_thread_summary_validates_from_an_object_with_matching_attributes() -> None:
    row = SimpleNamespace(id=uuid.uuid4(), title="Office holidays policy", last_active_at=datetime.now(UTC))

    summary = ThreadSummary.model_validate(row)

    assert summary.title == "Office holidays policy"


def test_thread_created_validates_from_an_object_with_matching_attributes() -> None:
    row = SimpleNamespace(id=uuid.uuid4(), title="New conversation", created_at=datetime.now(UTC))

    created = ThreadCreated.model_validate(row)

    assert created.title == "New conversation"


def test_thread_rename_request_rejects_an_empty_title() -> None:
    with pytest.raises(ValidationError):
        ThreadRenameRequest(title="")


def test_thread_rename_request_accepts_a_whitespace_only_title_unstripped() -> None:
    """`Field(min_length=1)` counts characters, including spaces -- it is
    `rename_thread` itself that strips and then rejects a title that turns
    out empty (see `test_threads.py`'s `"   "` case), not this field.
    Asserting that this schema does *not* reject it pins down that division
    of responsibility so a future change that moves the stripping into the
    schema is a deliberate decision, not a silent regression."""
    request = ThreadRenameRequest(title="   ")

    assert request.title == "   "


def test_thread_rename_response_round_trips_id_and_title() -> None:
    thread_id = uuid.uuid4()
    response = ThreadRenameResponse(id=thread_id, title="Renamed")

    assert response.id == thread_id
    assert response.title == "Renamed"


def test_citation_out_from_citation_sets_document_available_true_when_chunk_id_present() -> None:
    citation = SimpleNamespace(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="p.3",
        excerpt="Expenses must be submitted within 30 days.",
        chunk_id=uuid.uuid4(),
    )

    citation_out = CitationOut.from_citation(citation)

    assert citation_out.document_available is True


def test_citation_out_from_citation_sets_document_available_false_when_chunk_id_is_none() -> None:
    """The case `from_citation` exists for: a chunk (or its whole document)
    deleted since the citation was created leaves `Citation.chunk_id` null
    via the model's `ondelete="SET NULL"`, and that must read back as
    `document_available=False` rather than the field's own `True` default."""
    citation = SimpleNamespace(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location="p.3",
        excerpt="Expenses must be submitted within 30 days.",
        chunk_id=None,
    )

    citation_out = CitationOut.from_citation(citation)

    assert citation_out.document_available is False


def test_citation_out_document_available_defaults_to_true_when_constructed_directly() -> None:
    citation_out = CitationOut(
        id=uuid.uuid4(),
        document_name="handbook.pdf",
        source_location=None,
        excerpt="some excerpt",
    )

    assert citation_out.document_available is True


def test_message_out_defaults_citations_to_an_empty_list_when_absent() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        role="assistant",
        content="The per diem is €45.",
        status="complete",
    )

    message_out = MessageOut.model_validate(row)

    assert message_out.citations == []


def test_thread_detail_defaults_messages_to_an_empty_list_for_a_brand_new_thread() -> None:
    row = SimpleNamespace(id=uuid.uuid4(), title="New conversation")

    detail = ThreadDetail.model_validate(row)

    assert detail.messages == []


def test_message_create_request_rejects_an_empty_question() -> None:
    with pytest.raises(ValidationError):
        MessageCreateRequest(question="")


def test_message_create_request_accepts_a_non_empty_question() -> None:
    request = MessageCreateRequest(question="Where is the expenses policy?")

    assert request.question == "Where is the expenses policy?"


def test_message_stream_final_defaults_citations_to_an_empty_list() -> None:
    final = MessageStreamFinal(message_id=uuid.uuid4())

    assert final.citations == []


def test_message_stream_final_requires_a_message_id() -> None:
    with pytest.raises(ValidationError):
        MessageStreamFinal()


def test_message_stream_final_rejects_a_non_uuid_message_id() -> None:
    with pytest.raises(ValidationError):
        MessageStreamFinal(message_id="not-a-uuid")
