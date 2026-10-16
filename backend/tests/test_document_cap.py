"""Tests for the configured total document cap enforced on upload.

Uses the shared `client`, `db_session` and `fake_object_store` fixtures from
`conftest.py`: an in-memory SQLite database per test and a fake object store
in place of MinIO, so no live services are needed.
"""

import uuid

from app.config import DOCUMENT_CAP_DEFAULT, document_cap
from app.models import Chunk, Document

TXT_BYTES = b"plain text content"


def _file(name: str, content: bytes = TXT_BYTES, content_type: str = "text/plain"):
    return ("files", (name, content, content_type))


def _seed_documents(db_session, count: int) -> None:
    for i in range(count):
        db_session.add(
            Document(
                id=uuid.uuid4(),
                file_name=f"existing-{i}.txt",
                mime_type="text/plain",
                size_bytes=10,
                storage_key=f"existing-{i}.txt",
                status="ready",
            )
        )
    db_session.commit()


# --- cap reached: rejection reason ------------------------------------------


def test_upload_rejected_with_library_full_reason_once_cap_reached(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "3")
    _seed_documents(db_session, 3)

    response = client.post("/documents", files=[_file("new.txt")])

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == []
    assert len(body["rejected"]) == 1
    rejected = body["rejected"][0]
    assert rejected["file_name"] == "new.txt"
    reason = rejected["reason"].lower()
    assert "full" in reason
    assert "delete" in reason


def test_cap_applies_within_the_same_batch_once_reached(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "2")
    _seed_documents(db_session, 1)

    response = client.post(
        "/documents",
        files=[_file("first.txt"), _file("second.txt")],
    )

    body = response.json()
    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["file_name"] == "first.txt"
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["file_name"] == "second.txt"
    assert "full" in body["rejected"][0]["reason"].lower()


# --- cap reached: nothing stored, nothing scheduled for ingestion -----------


def test_cap_rejected_file_is_never_written_to_storage(
    client, db_session, monkeypatch, fake_object_store
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "1")
    _seed_documents(db_session, 1)

    client.post("/documents", files=[_file("never-stored.txt")])

    assert fake_object_store == {}


def test_cap_rejected_file_creates_no_document_row_and_no_chunks(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "1")
    _seed_documents(db_session, 1)

    client.post("/documents", files=[_file("never-ingested.txt")])

    listed_names = {item["file_name"] for item in client.get("/documents").json()}
    assert "never-ingested.txt" not in listed_names
    assert db_session.query(Document).filter(Document.file_name == "never-ingested.txt").count() == 0
    # No document row means nothing for the ingestion pipeline to ever pick
    # up for this file, and it leaves no chunk rows behind either.
    assert db_session.query(Chunk).count() == 0


# --- deleting at the cap immediately re-enables uploading -------------------


def test_deleting_a_document_at_cap_immediately_re_enables_uploading(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "1")
    _seed_documents(db_session, 1)
    existing_id = db_session.query(Document).first().id

    blocked = client.post("/documents", files=[_file("blocked.txt")])
    assert blocked.json()["accepted"] == []
    assert blocked.json()["rejected"][0]["file_name"] == "blocked.txt"

    delete_response = client.delete(f"/documents/{existing_id}")
    assert delete_response.status_code == 204

    accepted_response = client.post("/documents", files=[_file("now-allowed.txt")])
    body = accepted_response.json()
    assert body["rejected"] == []
    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["file_name"] == "now-allowed.txt"


# --- default cap and env override -------------------------------------------


def test_default_cap_applies_when_document_cap_env_unset(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    _seed_documents(db_session, DOCUMENT_CAP_DEFAULT)

    response = client.post("/documents", files=[_file("over-default-cap.txt")])

    body = response.json()
    assert body["accepted"] == []
    assert "full" in body["rejected"][0]["reason"].lower()


def test_overridden_document_cap_env_value_is_honoured(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "5")
    _seed_documents(db_session, 4)

    allowed = client.post("/documents", files=[_file("fifth.txt")])
    assert allowed.json()["accepted"][0]["file_name"] == "fifth.txt"
    assert allowed.json()["rejected"] == []

    blocked = client.post("/documents", files=[_file("sixth.txt")])
    assert blocked.json()["accepted"] == []
    assert "full" in blocked.json()["rejected"][0]["reason"].lower()


def test_document_cap_function_reflects_env_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    assert document_cap() == DOCUMENT_CAP_DEFAULT

    monkeypatch.setenv("DOCUMENT_CAP", "7")
    assert document_cap() == 7
