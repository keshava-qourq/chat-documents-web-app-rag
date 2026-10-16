"""Behavioural tests for the documents API: upload validation, batch
isolation, shared listing and open access.

Uses the `client` fixture from conftest.py, which gives each test a private
in-memory SQLite database and a fake object store -- no live MinIO, no
sleeps, no network.
"""

import uuid

from app.config import MAX_UPLOAD_FILE_BYTES
from app.models import Document

PDF_BYTES = b"%PDF-1.4\n%fake pdf content\n"
DOCX_BYTES = b"PK\x03\x04fake docx content"
TXT_BYTES = b"plain text content"
MD_BYTES = b"# Markdown heading\n\nsome content"


def _file(name: str, content: bytes, content_type: str) -> tuple[str, tuple]:
    return ("files", (name, content, content_type))


# --- AC-001: multi-file upload of the four supported formats ------------------


def test_upload_accepts_all_four_supported_formats_and_they_appear_in_list(client) -> None:
    files = [
        _file("report.pdf", PDF_BYTES, "application/pdf"),
        _file(
            "notes.docx",
            DOCX_BYTES,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        _file("readme.txt", TXT_BYTES, "text/plain"),
        _file("summary.md", MD_BYTES, "text/markdown"),
    ]

    response = client.post("/documents", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == []
    assert len(body["accepted"]) == 4
    accepted_names = {item["file_name"] for item in body["accepted"]}
    assert accepted_names == {"report.pdf", "notes.docx", "readme.txt", "summary.md"}
    for item in body["accepted"]:
        assert item["status"] == "processing"

    listed = client.get("/documents").json()
    listed_names = {item["file_name"] for item in listed}
    assert listed_names == accepted_names
    for item in listed:
        assert item["status"] == "processing"


# --- AC-002: unsupported formats are rejected and persist nothing ------------


def test_upload_rejects_unsupported_formats_and_creates_no_document_row(client) -> None:
    files = [
        _file(
            "budget.xlsx",
            b"fake xlsx content",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        _file(
            "deck.pptx",
            b"fake pptx content",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ]

    response = client.post("/documents", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == []
    assert len(body["rejected"]) == 2
    rejected_names = {item["file_name"] for item in body["rejected"]}
    assert rejected_names == {"budget.xlsx", "deck.pptx"}
    for item in body["rejected"]:
        message = item["reason"].lower()
        assert "pdf" in message
        assert "docx" in message
        assert "txt" in message
        assert "markdown" in message or "md" in message

    assert client.get("/documents").json() == []


# --- AC-003: an over-25MB file is rejected alongside a valid, stored file ----


def test_oversized_file_rejected_while_valid_file_in_same_request_is_stored(
    client, fake_object_store
) -> None:
    oversized = b"0" * (MAX_UPLOAD_FILE_BYTES + 1)
    files = [
        _file("huge.txt", oversized, "text/plain"),
        _file("small.txt", TXT_BYTES, "text/plain"),
    ]

    response = client.post("/documents", files=files)

    assert response.status_code == 200
    body = response.json()
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["file_name"] == "huge.txt"
    assert "25" in body["rejected"][0]["reason"]

    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["file_name"] == "small.txt"

    listed_names = {item["file_name"] for item in client.get("/documents").json()}
    assert listed_names == {"small.txt"}
    # Only the valid file's bytes made it to the (fake) object store.
    assert len(fake_object_store) == 1


# --- AC-004: one failing file among several valid ones is attributed correctly ---


def test_mixed_batch_attributes_failure_to_its_own_file_and_keeps_valid_ones(client) -> None:
    files = [
        _file("ok1.txt", TXT_BYTES, "text/plain"),
        _file("bad.xlsx", b"fake", "application/vnd.ms-excel"),
        _file("ok2.md", MD_BYTES, "text/markdown"),
    ]

    response = client.post("/documents", files=files)

    assert response.status_code in (200, 207)
    body = response.json()
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["file_name"] == "bad.xlsx"

    accepted_names = {item["file_name"] for item in body["accepted"]}
    assert accepted_names == {"ok1.txt", "ok2.md"}

    listed_names = {item["file_name"] for item in client.get("/documents").json()}
    assert listed_names == {"ok1.txt", "ok2.md"}


# --- AC-012 / AC-014 / AC-056: shared listing, identical for every caller ----


def test_list_documents_exposes_required_fields_and_is_identical_for_every_client(client) -> None:
    client.post("/documents", files=[_file("shared.txt", TXT_BYTES, "text/plain")])

    response_from_client_a = client.get("/documents", headers={"User-Agent": "client-a"})
    response_from_client_b = client.get("/documents", headers={"User-Agent": "client-b"})

    assert response_from_client_a.status_code == 200
    assert response_from_client_b.status_code == 200
    body_a = response_from_client_a.json()
    body_b = response_from_client_b.json()
    assert body_a == body_b

    assert len(body_a) == 1
    item = body_a[0]
    for field in ("file_name", "size_bytes", "uploaded_at", "status"):
        assert field in item


# --- AC-055 / AC-057: no authentication anywhere on this surface ------------


def test_every_documents_route_succeeds_with_no_authentication(client) -> None:
    upload_response = client.post(
        "/documents", files=[_file("open.txt", TXT_BYTES, "text/plain")]
    )
    assert upload_response.status_code not in (401, 403)
    document_id = upload_response.json()["accepted"][0]["id"]

    list_response = client.get("/documents")
    assert list_response.status_code not in (401, 403)

    status_response = client.get(f"/documents/{document_id}/status")
    assert status_response.status_code not in (401, 403)

    delete_response = client.delete(f"/documents/{document_id}")
    assert delete_response.status_code not in (401, 403)


# --- status endpoint: failure_reason surfaced, 404 for unknown id -----------


def test_status_endpoint_returns_failure_reason_for_a_failed_document(client, db_session) -> None:
    document = Document(
        id=uuid.uuid4(),
        file_name="broken.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_key="broken.pdf",
        status="failed",
        failure_reason="Could not extract text from this PDF.",
    )
    db_session.add(document)
    db_session.commit()

    response = client.get(f"/documents/{document.id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "Could not extract text from this PDF."


def test_status_endpoint_returns_404_for_an_unknown_document(client) -> None:
    response = client.get(f"/documents/{uuid.uuid4()}/status")

    assert response.status_code == 404


# --- delete removes the document from the shared list for every client ------


def test_delete_removes_document_from_the_shared_list_for_all_clients(client) -> None:
    upload = client.post("/documents", files=[_file("gone.txt", TXT_BYTES, "text/plain")])
    document_id = upload.json()["accepted"][0]["id"]

    assert any(item["id"] == document_id for item in client.get("/documents").json())

    delete_response = client.delete(f"/documents/{document_id}")
    assert delete_response.status_code == 204

    for user_agent in ("client-a", "client-b"):
        listed = client.get("/documents", headers={"User-Agent": user_agent}).json()
        assert all(item["id"] != document_id for item in listed)
