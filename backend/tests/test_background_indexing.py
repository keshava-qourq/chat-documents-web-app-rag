"""POST /documents must itself schedule background indexing -- the one seam
no per-component unit test in this suite exercises from both sides at once.

`test_document_cap.py`'s sibling ingestion tests (and `app/tests/
test_ingestion.py`) test `app.ingestion.ingest_document` by calling it
directly, proving the indexer works once invoked. `test_documents.py` tests
the upload endpoint's validation, storage and listing behaviour, but every
one of its accepted documents is only ever asserted to be `'processing'`
immediately after the response -- never followed up to see whether anything
ever moves it on. Neither file proves the handoff the architecture actually
promises: "api ... schedules background indexing" and "indexer: in-process
background task runner ... sets document status processing/ready/failed".

This posts one real upload through the real endpoint and polls the real
status endpoint, without this test ever calling `app.ingestion
.ingest_document` itself -- the only way to prove *something* in the
request path triggers it. The only Gemini call indexing would make
(`embed_texts`) is monkeypatched to a fast, deterministic stand-in -- never
a live Gemini call -- so this proves the scheduling handoff, not Gemini's
own behaviour (already covered by `test_ingestion.py` and
`test_gemini_config_error.py`).

`app.ingestion` imports `embed_texts` by name (`from app.embeddings import
... embed_texts`), so it resolves the call against its own module's
attribute at call time, not `app.embeddings`'s. The stand-in is therefore
patched onto `app.ingestion.embed_texts` -- patching `app.embeddings
.embed_texts` instead leaves `app.ingestion`'s own reference untouched and a
real (and here unreachable) Gemini call is attempted, which is exactly what
left this test failing before.

Uses the shared `client` and `fake_object_store` fixtures from
`conftest.py`: an in-memory SQLite database and a fake object store standing
in for MinIO, so this suite never touches a live database server or MinIO.
"""

from app import ingestion

TXT_BYTES = b"Employees are entitled to twenty five days of annual leave each year."


def test_accepted_upload_is_indexed_without_the_caller_ever_invoking_the_indexer(
    client, fake_object_store, monkeypatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[0.1, 0.2] for _ in texts])

    response = client.post(
        "/documents", files=[("files", ("handbook.txt", TXT_BYTES, "text/plain"))]
    )

    assert response.status_code == 200
    accepted = response.json()["accepted"]
    assert len(accepted) == 1
    document_id = accepted[0]["id"]
    assert accepted[0]["status"] == "processing"

    status_body = client.get(f"/documents/{document_id}/status").json()

    assert status_body["status"] == "ready", (
        "POST /documents accepted the file but it never reached a terminal "
        "status: nothing in the request path ever called "
        "app.ingestion.ingest_document for it. The upload endpoint must "
        "itself schedule background indexing (per the approved architecture "
        "-- the api component 'schedules background indexing', and the "
        "indexer is an 'in-process background task runner' that 'sets "
        "document status processing/ready/failed') -- for example via "
        "FastAPI's BackgroundTasks -- rather than leaving every accepted "
        "document stuck in 'processing' forever."
    )
    assert status_body["failure_reason"] is None
    assert status_body["progress"] == 100

    listed = client.get("/documents").json()
    item = next(d for d in listed if d["id"] == document_id)
    assert item["chunk_count"] > 0
