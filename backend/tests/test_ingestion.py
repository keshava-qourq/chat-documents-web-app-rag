"""Unit tests for `app.ingestion.ingest_document`.

`app/tests/test_ingestion.py` (written under a different ticket's
`backend/app/` scope, with its own self-contained fixtures) already proves
the pipeline's happy path, chunking/extraction dispatch, retrying embedder
and the basic failure-reason mapping for a missing extractable text, an
unconfigured Gemini key and an embedding-service error on the very first
batch. `backend/tests/test_document_delete.py` and `backend/tests/
test_background_indexing.py` already prove the concurrent-delete race and
the upload-endpoint-to-indexer handoff.

What none of those reach, and what this file adds instead of repeating:

* a storage read that fails (the object the document's `storage_key` points
  at is gone or unreadable) -- `STORAGE_READ_REASON`, untested anywhere else;
* an extraction call that raises outright (an unsupported extension reaching
  `extract_fragments`, which the router should never let happen but
  `ingest_document` must still fail cleanly rather than propagate) --
  `NO_TEXT_REASON`;
* an unexpected, non-`EmbeddingServiceError` exception out of `embed_texts`
  -- proving the catch-all still fails the document and still deletes any
  chunks already committed, not just the two named exception types;
* `GeminiNotConfiguredError` arriving only after an earlier batch already
  committed chunks -- proving the configuration-error path cleans up partial
  work exactly like the embedding-service-error path does, which the
  existing test only checks when the key is missing from the first call;
* `EMBEDDING_BATCH_SIZE` configured as zero or negative -- the pipeline must
  not divide the work into zero-sized (or infinite) batches;
* the progress field never reading 100 while the loop is still committing
  batches, only once the document is actually marked `ready`; and
* a previously failed document being retried: the stale `failure_reason`
  from its earlier attempt must not survive a successful second pass.

Uses the shared `db_session` and `fake_object_store` fixtures from
`conftest.py`, so no live database or MinIO is ever touched; `embed_texts`
is monkeypatched on `app.ingestion` (the name `ingest_document` actually
calls) rather than on `app.embeddings`, for the same reason
`test_background_indexing.py` documents: `ingestion.py` imports the name
into its own module, so patching `app.embeddings.embed_texts` would leave
`ingestion`'s own reference untouched.
"""

import uuid

import pytest

from app import embeddings, ingestion
from app.ingestion import (
    CONFIGURATION_REASON,
    EMBEDDING_FAILURE_REASON,
    NO_TEXT_REASON,
    STORAGE_READ_REASON,
    ingest_document,
)
from app.models import Chunk, Document


def _make_document(db_session, file_name: str, storage_key: str, **overrides) -> Document:
    fields = {
        "id": uuid.uuid4(),
        "file_name": file_name,
        "mime_type": "text/plain",
        "size_bytes": 100,
        "storage_key": storage_key,
        "status": "processing",
    }
    fields.update(overrides)
    document = Document(**fields)
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _chunk_count(db_session, document_id) -> int:
    return db_session.query(Chunk).filter(Chunk.document_id == document_id).count()


# --- storage read failure ----------------------------------------------------


def test_storage_read_failure_fails_the_document_without_storing_chunks(
    db_session, fake_object_store
) -> None:
    # Nothing is put into fake_object_store under this key -- the fake S3
    # client's get_object raises, exactly as it would for an object deleted
    # out from under the pipeline or a storage_key that never existed.
    document = _make_document(db_session, "gone.txt", "gone.txt")

    ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == STORAGE_READ_REASON
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


# --- extraction failure --------------------------------------------------


def test_unsupported_extension_fails_cleanly_instead_of_raising(
    db_session, fake_object_store
) -> None:
    """The upload router already rejects unsupported extensions, but if one
    ever reaches the pipeline anyway (a storage_key out of step with its
    upload), ingest_document must still end the document in a terminal
    'failed' state rather than let extraction's ValueError propagate out of
    a background task with nothing to catch it."""
    fake_object_store["sheet.xlsx"] = (b"not really a spreadsheet", "application/octet-stream")
    document = _make_document(db_session, "sheet.xlsx", "sheet.xlsx")

    ingest_document(document.id, db_session)  # must not raise

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == NO_TEXT_REASON
    assert _chunk_count(db_session, document.id) == 0


# --- embedding failures beyond the named exception types --------------------


def test_unexpected_exception_from_embedder_still_fails_and_cleans_up(
    db_session, fake_object_store, monkeypatch
) -> None:
    """A bug in the embedding client that raises something other than
    EmbeddingServiceError or GeminiNotConfiguredError must still be caught --
    the document must not be left stuck in 'processing' forever."""
    fake_object_store["doc.txt"] = (b"some content to embed", "text/plain")
    document = _make_document(db_session, "doc.txt", "doc.txt")

    def broken_embed(texts):
        raise RuntimeError("completely unexpected failure")

    monkeypatch.setattr(ingestion, "embed_texts", broken_embed)

    ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == EMBEDDING_FAILURE_REASON
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


def test_configuration_error_after_a_successful_batch_deletes_the_partial_chunks(
    db_session, fake_object_store, monkeypatch
) -> None:
    """The existing configuration-error test only exercises a key missing
    from the very first call. If Gemini is de-configured partway through (or
    the key becomes invalid between batches), any chunks already committed
    for this document must not survive either -- a failed document must
    never have partial chunks a poller or the chat endpoint could read."""
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    fake_object_store["multi.txt"] = (b"a" * 15, "text/plain")  # three 5-char chunks
    document = _make_document(db_session, "multi.txt", "multi.txt")

    calls = {"count": 0}

    def embed_then_deconfigure(texts):
        calls["count"] += 1
        if calls["count"] == 1:
            return [[0.1] for _ in texts]
        raise embeddings.GeminiNotConfiguredError("GEMINI_API_KEY is not configured")

    monkeypatch.setattr(ingestion, "embed_texts", embed_then_deconfigure)

    ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == CONFIGURATION_REASON
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


# --- batch size configuration --------------------------------------------


def test_non_positive_embedding_batch_size_is_clamped_to_at_least_one(
    db_session, fake_object_store, monkeypatch
) -> None:
    """EMBEDDING_BATCH_SIZE=0 (or negative) must not produce a zero-sized or
    infinite batch -- the pipeline clamps it to 1 and still finishes."""
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "0")
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    fake_object_store["small.txt"] = (b"a" * 15, "text/plain")  # three 5-char chunks
    document = _make_document(db_session, "small.txt", "small.txt")

    calls = {"count": 0}

    def counting_embed(texts):
        calls["count"] += 1
        assert len(texts) == 1, "batch size 0 must be clamped to 1, not left unbounded"
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", counting_embed)

    ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.chunk_count == 3
    assert calls["count"] == 3


# --- progress reporting ---------------------------------------------------


def test_progress_never_reads_100_until_the_document_is_actually_ready(
    db_session, fake_object_store, monkeypatch
) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    fake_object_store["prog.txt"] = (b"a" * 25, "text/plain")  # five 5-char chunks
    document = _make_document(db_session, "prog.txt", "prog.txt")

    observed: list[int] = []

    def recording_embed(texts):
        # document.progress reflects whatever the previous batch committed,
        # since this runs on the same session as ingest_document.
        observed.append(document.progress)
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", recording_embed)

    ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.progress == 100
    # Every value read mid-pipeline (including right before the final batch
    # commits) must be strictly below 100 -- 100 is only ever set once the
    # document is genuinely finished, outside the loop.
    assert all(value < 100 for value in observed)
    assert observed == sorted(observed)


# --- retrying a previously failed document -----------------------------


def test_retrying_a_previously_failed_document_clears_the_stale_failure_reason(
    db_session, fake_object_store, monkeypatch
) -> None:
    fake_object_store["retry.txt"] = (b"now readable content", "text/plain")
    document = _make_document(
        db_session,
        "retry.txt",
        "retry.txt",
        status="failed",
        failure_reason="an earlier, unrelated failure",
        progress=100,
    )

    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[0.1] for _ in texts])

    ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.failure_reason is None
    assert document.chunk_count > 0


# --- unknown document id ---------------------------------------------------


def test_unknown_document_id_is_a_no_op(db_session, fake_object_store) -> None:
    ingest_document(uuid.uuid4(), db_session)  # must not raise
