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


def test_cap_applies_within_the_same_batch_once_reached(client, db_session, monkeypatch) -> None:
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


def test_cap_rejects_every_file_past_the_limit_within_a_single_batch(
    client, db_session, monkeypatch
) -> None:
    """The same cap check applies to every file in a batch, not just the
    first one past the limit -- with no existing documents and a cap of 3,
    five files in one request should leave exactly the first three accepted
    and the remaining two rejected, in order."""
    monkeypatch.setenv("DOCUMENT_CAP", "3")

    response = client.post(
        "/documents",
        files=[_file(f"f{i}.txt") for i in range(5)],
    )

    body = response.json()
    assert [item["file_name"] for item in body["accepted"]] == ["f0.txt", "f1.txt", "f2.txt"]
    assert [item["file_name"] for item in body["rejected"]] == ["f3.txt", "f4.txt"]
    for rejected in body["rejected"]:
        assert "full" in rejected["reason"].lower()


def test_cap_full_rejection_takes_precedence_over_unsupported_file_type(
    client, db_session, monkeypatch
) -> None:
    """When the library is already full, a file that would *also* have been
    rejected for being an unsupported type still gets the cap-full reason,
    not the unsupported-type one -- the cap check runs before any other
    validation, so a caller trying to clear space by replacing a document
    gets an unambiguous "library is full" answer rather than a type error
    that has nothing to do with why the upload actually failed."""
    monkeypatch.setenv("DOCUMENT_CAP", "1")
    _seed_documents(db_session, 1)

    response = client.post(
        "/documents",
        files=[_file("report.xlsx", b"fake xlsx content", "application/vnd.ms-excel")],
    )

    body = response.json()
    assert body["accepted"] == []
    assert len(body["rejected"]) == 1
    reason = body["rejected"][0]["reason"].lower()
    assert "full" in reason
    assert "delete" in reason
    assert "pdf" not in reason


def test_rejection_for_an_unrelated_reason_does_not_consume_cap_budget(
    client, db_session, monkeypatch
) -> None:
    """A file rejected for being an unsupported type never becomes a
    document row, so it must not count against the cap for files later in
    the same batch -- with a cap of 1 and no existing documents, an invalid
    file followed by a valid one should still let the valid one through."""
    monkeypatch.setenv("DOCUMENT_CAP", "1")

    response = client.post(
        "/documents",
        files=[
            _file("bad.xlsx", b"fake xlsx content", "application/vnd.ms-excel"),
            _file("good.txt"),
        ],
    )

    body = response.json()
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["file_name"] == "bad.xlsx"
    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["file_name"] == "good.txt"


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
    assert (
        db_session.query(Document).filter(Document.file_name == "never-ingested.txt").count() == 0
    )
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


def test_default_cap_applies_when_document_cap_env_unset(client, db_session, monkeypatch) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    _seed_documents(db_session, DOCUMENT_CAP_DEFAULT)

    response = client.post("/documents", files=[_file("over-default-cap.txt")])

    body = response.json()
    assert body["accepted"] == []
    assert "full" in body["rejected"][0]["reason"].lower()


def test_overridden_document_cap_env_value_is_honoured(client, db_session, monkeypatch) -> None:
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
