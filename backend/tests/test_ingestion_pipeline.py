"""Gaps in `app.ingestion.ingest_document` that `app/tests/test_ingestion.py`
and `test_background_indexing.py` / `test_document_delete.py` do not reach:

* a storage read that fails outright (the object is missing/unreadable)
  before extraction is ever attempted;
* an extraction failure that is not "no text" but an outright unsupported
  extension, which the pipeline still has to fail cleanly without ever
  calling Gemini;
* the *pre-batch* existence/cancellation check catching a cancellation that
  lands strictly between two already-committed batches -- as distinct from
  the check right before a batch is persisted, which the existing mid-flight
  delete tests already cover;
* the right-before-persist check catching a cancellation expressed as a
  status flip (the `_document_still_indexable` contract explicitly names
  "marked cancelled" as well as deleted, even though today's DELETE endpoint
  only ever removes the row outright);
* re-ingesting a document that previously failed, which must come out clean
  with no leftover failure reason or stale progress;
* an *unexpected* exception during the embedding loop -- something other
  than the two documented `embed_texts` exceptions -- raised between two
  whole batches still being caught by `ingest_document`'s own catch-all and
  failing the document cleanly, with nothing left over from the batch that
  already committed;
* a reproduced, documented defect in that same catch-all when the
  unexpected exception instead lands *inside* a batch, after some chunks in
  it were already added to the session but before that batch is committed
  -- see that test's own docstring for why `_delete_chunks` does not
  actually remove them.

No live Gemini, MinIO or Postgres: `app.ingestion.embed_texts` is
monkeypatched directly in every test, and the object store is the same
in-memory stand-in for `storage.get_client()` used in `app/tests/
test_ingestion.py`, so this suite never touches a live database server,
MinIO or Gemini.
"""

import uuid

import pytest

from app import ingestion, models, storage


@pytest.fixture()
def fake_store(monkeypatch):
    objects: dict[str, bytes] = {}

    class FakeBody:
        def __init__(self, data: bytes):
            self._data = data

        def read(self) -> bytes:
            return self._data

    class FakeClient:
        def get_object(self, Bucket, Key):  # noqa: N803 -- matches boto3's signature
            if Key not in objects:
                raise KeyError(Key)
            return {"Body": FakeBody(objects[Key])}

    monkeypatch.setattr(storage, "get_client", lambda: FakeClient())
    return objects


def _make_document(db_session, file_name: str, storage_key: str, **overrides) -> models.Document:
    fields = {
        "id": uuid.uuid4(),
        "file_name": file_name,
        "mime_type": "text/plain",
        "size_bytes": 100,
        "storage_key": storage_key,
        "status": "processing",
    }
    fields.update(overrides)
    document = models.Document(**fields)
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _chunk_count(db_session, document_id) -> int:
    return db_session.query(models.Chunk).filter(models.Chunk.document_id == document_id).count()


def _refusing_embed(texts):
    raise AssertionError("embed_texts must not be called when extraction already failed")


# --- storage read failure ---------------------------------------------------


def test_unreadable_original_fails_document_without_calling_embeddings(
    db_session, fake_store, monkeypatch
) -> None:
    # Nothing is seeded under this key, so the fake client's get_object raises.
    document = _make_document(db_session, "missing.txt", "missing-key.txt")
    monkeypatch.setattr(ingestion, "embed_texts", _refusing_embed)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.STORAGE_READ_REASON
    assert document.progress == 100
    assert _chunk_count(db_session, document.id) == 0


# --- unsupported extension reaching ingest_document directly ---------------


def test_unsupported_extension_fails_cleanly_without_calling_embeddings(
    db_session, fake_store, monkeypatch
) -> None:
    """The upload endpoint already rejects unsupported extensions before a
    document row ever exists, but `ingest_document` has no such guarantee
    about what it is handed -- it must fail just as cleanly, and without
    spending a Gemini call, if it ever is."""
    fake_store["sheet.xlsx"] = b"some bytes"
    document = _make_document(db_session, "sheet.xlsx", "sheet.xlsx")
    monkeypatch.setattr(ingestion, "embed_texts", _refusing_embed)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.NO_TEXT_REASON
    assert _chunk_count(db_session, document.id) == 0


# --- pre-batch check catches a cancellation landing between two batches ----


def test_status_flip_landing_between_batches_is_caught_by_the_pre_batch_check(
    db_session, fake_store, monkeypatch
) -> None:
    """Distinguishes the pre-batch existence check from the right-before-
    persist check: the cancellation here lands only after batch 0 is fully
    committed, so the second batch's embed_texts call must never happen --
    if it were the persist-time check doing the catching instead, a second
    call would already have gone out."""
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    fake_store["cancel.txt"] = b"a" * 15  # three 5-char chunks -> three batches of one
    document = _make_document(db_session, "cancel.txt", "cancel.txt")

    embed_calls = {"count": 0}

    def fake_embed(texts):
        embed_calls["count"] += 1
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", fake_embed)

    original_commit = db_session.commit
    commit_calls = {"count": 0}

    def flipping_commit():
        commit_calls["count"] += 1
        original_commit()
        # The 2nd commit is the one right after batch 0's chunk is
        # persisted. Flip the document to cancelled immediately afterwards,
        # strictly between batch 0's commit and batch 1's pre-check, with no
        # embed_texts call for batch 1 ever in flight.
        if commit_calls["count"] == 2:
            db_session.query(models.Document).filter(models.Document.id == document.id).update(
                {"status": "cancelled"}
            )
            original_commit()

    monkeypatch.setattr(db_session, "commit", flipping_commit)

    ingestion.ingest_document(document.id, db_session)

    assert embed_calls["count"] == 1, (
        "a second embed_texts call means the pre-batch check did not catch "
        "the cancellation before spending a Gemini call on batch 1"
    )
    assert _chunk_count(db_session, document.id) == 0


# --- right-before-persist check catches a cancellation flag too -----------


def test_status_flip_during_an_in_flight_embed_call_is_caught_before_persisting(
    db_session, fake_store, monkeypatch
) -> None:
    """`_document_still_indexable` treats a 'cancelled' status exactly like a
    deleted row -- the mid-flight delete tests in test_document_delete.py
    only ever exercise the deletion path; this exercises the status-flag
    path the same contract explicitly promises."""
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    fake_store["cancel2.txt"] = b"a" * 10  # two 5-char chunks
    document = _make_document(db_session, "cancel2.txt", "cancel2.txt")
    document_id = document.id

    def cancel_during_embed(texts):
        db_session.query(models.Document).filter(models.Document.id == document_id).update(
            {"status": "cancelled"}
        )
        db_session.commit()
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", cancel_during_embed)

    ingestion.ingest_document(document_id, db_session)

    remaining = db_session.query(models.Document).filter(models.Document.id == document_id).first()
    assert remaining is not None
    assert remaining.status == "cancelled"  # never overwritten to failed/ready
    assert _chunk_count(db_session, document_id) == 0


# --- retrying a previously failed document ---------------------------------


def test_reingesting_a_previously_failed_document_clears_the_old_failure(
    db_session, fake_store, monkeypatch
) -> None:
    fake_store["retry.txt"] = b"short enough text to embed in one batch"
    document = _make_document(
        db_session,
        "retry.txt",
        "retry.txt",
        status="failed",
        failure_reason="embedding service error",
        progress=100,
    )
    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[0.1, 0.2] for _ in texts])

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.failure_reason is None
    assert document.progress == 100
    assert document.chunk_count > 0


# --- an unexpected, undocumented exception between two batches -------------


def test_an_unexpected_exception_between_batches_fails_the_document_and_deletes_chunks(
    db_session, fake_store, monkeypatch
) -> None:
    """`EmbeddingServiceError` and `GeminiNotConfiguredError` are the two
    exceptions `embed_texts` is documented to raise, but `ingest_document`
    also wraps the whole embedding loop in a bare `except Exception`. This
    proves that catch-all actually does something: a completely unrelated
    exception raised from a later batch's `embed_texts` call (a bug, not a
    documented failure mode) still fails the document with the same reason
    an exhausted-retries failure gets, and still deletes the chunk already
    committed from the batch before it -- rather than propagating out of
    `ingest_document` and leaving the row stuck in 'processing' forever with
    no failure reason anyone would ever see."""
    monkeypatch.setenv("CHUNK_SIZE", "10")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    fake_store["unexpected.txt"] = b"a" * 25  # three 10/10/5-char chunks -> three batches of one
    document = _make_document(db_session, "unexpected.txt", "unexpected.txt")

    calls = {"count": 0}

    def embed_then_blow_up(texts):
        calls["count"] += 1
        if calls["count"] == 1:
            return [[0.1] for _ in texts]
        raise ValueError("an unrelated bug, not EmbeddingServiceError")

    monkeypatch.setattr(ingestion, "embed_texts", embed_then_blow_up)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.EMBEDDING_FAILURE_REASON
    assert _chunk_count(db_session, document.id) == 0


# --- the same catch-all, but the exception lands mid-batch: a reproduced defect


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known defect, discovered while reaching for coverage this ticket "
        "does not provide a writable path to fix (app/ingestion.py is "
        "outside backend/tests/): when `embed_texts` returns fewer vectors "
        "than the batch it was given, `zip(batch, vectors, strict=True)` "
        "raises ValueError partway through the batch -- after `db.add()` "
        "has already been called for the chunks that *did* pair up, but "
        "before this batch's own `db.commit()`. The surrounding "
        "`except Exception` then calls `_delete_chunks`, which issues a "
        "bulk `Query.delete()`; `SessionLocal` (app/database.py) and this "
        "test's own `db_session` fixture both construct their sessionmaker "
        "with `autoflush=False`, so that bulk DELETE runs against the "
        "database as it stood at the last commit and never sees the "
        "pending, not-yet-flushed `Chunk` objects added earlier in this "
        "same batch. `_fail()`'s own `db.commit()` right after then "
        "flushes and persists exactly those orphaned rows for a document "
        "the user is shown as 'failed' -- the opposite of this module's "
        "own docstring promise that 'a failed document never has partial "
        "chunks a poller or the chat endpoint could stumble on'. Fixing it "
        "needs either an explicit `db.flush()` before `_delete_chunks`'s "
        "query, or `session.flush()`/autoflush enabled in app/ingestion.py "
        "or app/database.py, neither of which backend/tests/ can write."
    ),
)
def test_embed_texts_returning_fewer_vectors_than_texts_mid_batch_fails_cleanly(
    db_session, fake_store, monkeypatch
) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "10")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    fake_store["shortfall.txt"] = b"a" * 25  # three 10/10/5-char chunks, one batch
    document = _make_document(db_session, "shortfall.txt", "shortfall.txt")

    # One fewer vector than the number of texts sent -- `zip(..., strict=True)`
    # must raise rather than silently dropping the last chunk.
    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[0.1] for _ in texts[:-1]])

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.EMBEDDING_FAILURE_REASON
    assert _chunk_count(db_session, document.id) == 0
