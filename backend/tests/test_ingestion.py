"""Tests for the background ingestion pipeline: extraction, chunking,
embeddings with retry, and the terminal status/progress/failure handling
`ingest_document` is responsible for.

No live Gemini, MinIO or Postgres: Gemini calls go through `embed_texts`,
which every ingestion test monkeypatches directly, and the object store is a
tiny in-memory stand-in for `storage.get_client()`. Self-contained fixtures
(not the shared `conftest.py` ones, which are wired for the FastAPI
`TestClient`), since this module calls `app.ingestion.ingest_document`
directly.

The last block below (storage/extraction failure paths, the cancel/delete
race `ingestion.py`'s own docstring describes, retry-after-failure, and a
Gemini-rejected key) covers what the rest of this file -- and the
`app/tests/test_ingestion.py` draft it was grown from -- never reached:
every one of those is a real branch in `ingest_document` with no prior
assertion that would fail if it broke.
"""

import io
import uuid

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import chunking, database, embeddings, extraction, ingestion, models, storage

# --- extraction ---------------------------------------------------------------


def _pdf_bytes_with_pages(pages: list[str]) -> bytes:
    """pypdf cannot easily synthesise real text layers, so these tests exercise
    the page-numbering and empty-page behaviour instead using a writer-built
    PDF; a page with no text content yields no fragment, matching a scanned
    page with no text layer."""
    writer = PdfWriter()
    for _ in pages:
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extract_pdf_blank_pages_yield_no_fragments() -> None:
    content = _pdf_bytes_with_pages(["", ""])
    fragments = extraction.extract_fragments(content, ".pdf", "scanned.pdf")
    assert fragments == []


def test_extract_docx_groups_text_under_headings_with_file_name_prefix() -> None:
    document = DocxDocument()
    document.add_heading("Introduction", level=1)
    document.add_paragraph("This is the intro body.")
    document.add_heading("Conclusion", level=1)
    document.add_paragraph("This is the conclusion body.")
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "notes.docx")

    assert len(fragments) == 2
    assert fragments[0] == ("This is the intro body.", "notes.docx, Introduction")
    assert fragments[1] == ("This is the conclusion body.", "notes.docx, Conclusion")


def test_extract_docx_with_no_headings_uses_file_name_as_location() -> None:
    document = DocxDocument()
    document.add_paragraph("No headings here, just body text.")
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "plain.docx")

    assert fragments == [("No headings here, just body text.", "plain.docx")]


def test_extract_txt_returns_single_fragment_located_at_file_name() -> None:
    fragments = extraction.extract_fragments(b"hello world", ".txt", "readme.txt")
    assert fragments == [("hello world", "readme.txt")]


def test_extract_md_returns_single_fragment_located_at_file_name() -> None:
    fragments = extraction.extract_fragments(b"# Title\n\nbody", ".md", "summary.md")
    assert fragments == [("# Title\n\nbody", "summary.md")]


def test_extract_empty_file_returns_no_fragments() -> None:
    assert extraction.extract_fragments(b"   \n  ", ".txt", "empty.txt") == []


def test_extract_unsupported_extension_raises() -> None:
    with pytest.raises(ValueError):
        extraction.extract_fragments(b"data", ".xlsx", "sheet.xlsx")


# --- chunking -------------------------------------------------------------


def test_chunk_fragments_splits_with_configured_size_and_overlap() -> None:
    text = "a" * 25
    fragments = [(text, "doc.txt, page 1")]

    chunks = chunking.chunk_fragments(fragments, size=10, overlap=3)

    contents = [c[0] for c in chunks]
    indices = [c[2] for c in chunks]
    locations = {c[1] for c in chunks}
    assert indices == list(range(len(chunks)))
    assert locations == {"doc.txt, page 1"}
    # step = size - overlap = 7, so starts are 0, 7, 14, 21
    assert contents == ["a" * 10, "a" * 10, "a" * 10, "a" * 4]


def test_chunk_fragments_keeps_each_fragment_independently_indexed_and_located() -> None:
    fragments = [("short page one", "doc.pdf, page 1"), ("short page two", "doc.pdf, page 2")]

    chunks = chunking.chunk_fragments(fragments, size=100, overlap=10)

    assert [c[1] for c in chunks] == ["doc.pdf, page 1", "doc.pdf, page 2"]
    assert [c[2] for c in chunks] == [0, 1]


def test_chunk_fragments_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        chunking.chunk_fragments([("x", "loc")], size=0, overlap=0)


# --- embeddings -------------------------------------------------------------


def test_embed_texts_raises_not_configured_when_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(embeddings.GeminiNotConfiguredError):
        embeddings.embed_texts(["hello"])


def test_embed_texts_retries_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "3")

    calls = {"count": 0}

    class FakeEmbedding:
        def __init__(self, values):
            self.values = values

    class FakeResult:
        def __init__(self, vectors):
            self.embeddings = [FakeEmbedding(v) for v in vectors]

    class FakeModels:
        def embed_content(self, model, contents, config=None):
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("transient failure")
            return FakeResult([[0.1, 0.2] for _ in contents])

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)

    result = embeddings.embed_texts(["a", "b"])

    assert calls["count"] == 3
    assert result == [[0.1, 0.2], [0.1, 0.2]]


def test_embed_texts_raises_service_error_after_exhausting_retries(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "2")

    class FakeModels:
        def embed_content(self, model, contents, config=None):
            raise RuntimeError("always fails")

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)

    with pytest.raises(embeddings.EmbeddingServiceError):
        embeddings.embed_texts(["a"])


# --- ingest_document ---------------------------------------------------------


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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


def _make_document(
    db_session, file_name: str, storage_key: str, status: str = "processing"
) -> models.Document:
    document = models.Document(
        id=uuid.uuid4(),
        file_name=file_name,
        mime_type="text/plain",
        size_bytes=100,
        storage_key=storage_key,
        status=status,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _chunk_count(db_session, document_id) -> int:
    return db_session.query(models.Chunk).filter(models.Chunk.document_id == document_id).count()


def test_ingest_document_success_stores_chunks_and_marks_ready(
    db_session, fake_store, monkeypatch
) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "10")
    monkeypatch.setenv("CHUNK_OVERLAP", "2")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "2")
    fake_store["doc1.txt"] = b"abcdefghijklmnopqrstuvwxyz"
    document = _make_document(db_session, "doc1.txt", "doc1.txt")

    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[0.1, 0.2, 0.3] for _ in texts])

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.progress == 100
    assert document.failure_reason is None
    stored_chunks = (
        db_session.query(models.Chunk)
        .filter(models.Chunk.document_id == document.id)
        .order_by(models.Chunk.chunk_index)
        .all()
    )
    assert document.chunk_count == len(stored_chunks)
    assert len(stored_chunks) > 1
    for chunk in stored_chunks:
        assert chunk.source_location == "doc1.txt"
        assert chunk.embedding == [0.1, 0.2, 0.3]
    assert [c.chunk_index for c in stored_chunks] == list(range(len(stored_chunks)))


def test_ingest_document_progress_advances_across_batches_before_completion(
    db_session, fake_store, monkeypatch
) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    fake_store["doc2.txt"] = b"a" * 25  # 5 chunks of size 5
    document = _make_document(db_session, "doc2.txt", "doc2.txt")

    seen_progress: list[int] = []

    def fake_embed(texts):
        seen_progress.append(document.progress)
        return [[0.0] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", fake_embed)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.progress == 100
    # Progress observed before each embed call must strictly increase across
    # batches -- a poller reading between batches would see it climb.
    assert seen_progress == sorted(seen_progress)
    assert seen_progress[0] == 0
    assert seen_progress[-1] < 100


def test_ingest_document_no_extractable_text_fails_without_storing_chunks(
    db_session, fake_store, monkeypatch
) -> None:
    fake_store["blank.txt"] = b"   \n  "
    document = _make_document(db_session, "blank.txt", "blank.txt")

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert "scanned" in document.failure_reason.lower()
    assert (
        "no text" in document.failure_reason.lower()
        or "could not" in document.failure_reason.lower()
    )
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


def test_ingest_document_embedding_failure_marks_failed_and_deletes_chunks(
    db_session, fake_store, monkeypatch
) -> None:
    # Forces the 65-character fixture below to split into more than one
    # chunk (two batches of one at CHUNK_SIZE=30), so the second embed call
    # -- the one that raises -- is actually reached. Without overriding
    # CHUNK_SIZE, the default (1000) keeps this short fixture to a single
    # chunk/batch, the first (succeeding) call satisfies the whole document,
    # and the intended failure path is never exercised.
    monkeypatch.setenv("CHUNK_SIZE", "30")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    fake_store["doc3.txt"] = b"first chunk content here that is long enough to split into two"
    document = _make_document(db_session, "doc3.txt", "doc3.txt")

    calls = {"count": 0}

    def flaky_embed(texts):
        calls["count"] += 1
        if calls["count"] == 1:
            return [[0.1] for _ in texts]
        raise embeddings.EmbeddingServiceError("embedding service error")

    monkeypatch.setattr(ingestion, "embed_texts", flaky_embed)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert calls["count"] >= 2  # the failure path was actually reached
    assert document.status == "failed"
    assert document.failure_reason == "embedding service error"
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


def test_ingest_document_missing_gemini_key_fails_with_configuration_reason(
    db_session, fake_store, monkeypatch
) -> None:
    fake_store["doc4.txt"] = b"some content to embed"
    document = _make_document(db_session, "doc4.txt", "doc4.txt")

    def not_configured(texts):
        raise embeddings.GeminiNotConfiguredError("GEMINI_API_KEY is not configured")

    monkeypatch.setattr(ingestion, "embed_texts", not_configured)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert "gemini" in document.failure_reason.lower()
    assert _chunk_count(db_session, document.id) == 0


def test_ingest_document_unknown_id_is_a_no_op(db_session) -> None:
    ingestion.ingest_document(uuid.uuid4(), db_session)  # must not raise


# --- gaps left uncovered above: storage/extraction failures, the cancel/ ---
# --- delete race, retry-after-failure, and a Gemini-rejected key -----------


def test_ingest_document_storage_read_failure_fails_with_storage_read_reason(
    db_session, fake_store
) -> None:
    """`storage_key` points at an object the fake store never received --
    the same shape a dangling/garbage-collected S3 key would take in
    production. `_read_original` must be caught on its own, before
    extraction or Gemini are ever reached, and reported distinctly from a
    "no text" failure."""
    document = _make_document(db_session, "missing.txt", "does-not-exist.txt")

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.STORAGE_READ_REASON
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


def test_ingest_document_unsupported_file_extension_fails_with_no_text_reason(
    db_session, fake_store
) -> None:
    """The upload router already rejects unsupported extensions, but if one
    ever reaches the indexer anyway (a storage_key that doesn't match its
    original upload), `extract_fragments`'s `ValueError` must be caught and
    turned into the same terminal "no text" failure as any other
    unextractable file, not an unhandled exception that leaves the document
    stuck in `processing`."""
    fake_store["sheet.xlsx"] = b"some binary spreadsheet content"
    document = _make_document(db_session, "sheet.xlsx", "sheet.xlsx")

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.NO_TEXT_REASON
    assert _chunk_count(db_session, document.id) == 0


def test_ingest_document_extraction_error_fails_with_no_text_reason_not_a_crash(
    db_session, fake_store, monkeypatch
) -> None:
    """A corrupt file of an otherwise-supported extension (a bad PDF/DOCX)
    makes the extractor itself raise, rather than simply returning no
    fragments. `ingest_document` must catch that too and fail the document
    the same way, instead of propagating the exception out of a background
    task with no one to see it."""
    fake_store["corrupt.pdf"] = b"not actually a pdf"
    document = _make_document(db_session, "corrupt.pdf", "corrupt.pdf")

    def raiser(content, extension, file_name):
        raise RuntimeError("could not parse file")

    monkeypatch.setattr(ingestion, "extract_fragments", raiser)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.NO_TEXT_REASON
    assert _chunk_count(db_session, document.id) == 0


def test_ingest_document_still_indexable_check_before_a_batch_stops_further_embedding(
    db_session, fake_store, monkeypatch
) -> None:
    """Documents the race `ingestion.py`'s own module docstring describes: a
    `DELETE /documents/{id}` landing on another session while a document is
    mid-index must stop the loop before it spends another Gemini call on a
    document that is no longer indexable. This pins down specifically the
    check made "before embedding this batch" (as opposed to the one made
    right after an embed call returns), by letting the first two checks
    (iteration 1's "before" and "after") run for real and only then forcing
    the next one -- iteration 2's "before this batch" check -- to report
    "no longer indexable", the same as a concurrent delete/cancel would.
    Whatever chunks iteration 1 already persisted must be deleted too: a
    document that stops indexing partway through never keeps a partial set
    of chunks."""
    monkeypatch.setenv("CHUNK_SIZE", "5")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "1")
    fake_store["cancel1.txt"] = b"a" * 15  # 3 chunks of size 5 -> 3 batches
    document = _make_document(db_session, "cancel1.txt", "cancel1.txt")

    embed_calls = {"count": 0}

    def fake_embed(texts):
        embed_calls["count"] += 1
        return [[0.1] for _ in texts]

    monkeypatch.setattr(ingestion, "embed_texts", fake_embed)

    real_check = ingestion._document_still_indexable
    check_calls = {"count": 0}

    def fake_check(db, document_id):
        check_calls["count"] += 1
        if check_calls["count"] <= 2:  # iteration 1's own "before" and "after" checks
            return real_check(db, document_id)
        return False  # iteration 2's "before this batch" check

    monkeypatch.setattr(ingestion, "_document_still_indexable", fake_check)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert embed_calls["count"] == 1  # the second and third batches were never embedded
    assert check_calls["count"] == 3
    assert _chunk_count(db_session, document.id) == 0  # batch 1's chunks were deleted too
    assert document.chunk_count == 0


def test_ingest_document_cancelled_during_embed_call_is_caught_before_persisting_that_batch(
    db_session, fake_store, monkeypatch
) -> None:
    """The second, narrower check `ingestion.py` describes: a cancellation
    that lands while a (possibly slow) embedding call is in flight must
    still stop that very batch from being committed, even though it already
    passed the check made before the call started."""
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "100")
    fake_store["cancel2.txt"] = b"a short document, one batch only"
    document = _make_document(db_session, "cancel2.txt", "cancel2.txt")

    calls = {"count": 0}

    def fake_embed(texts):
        calls["count"] += 1
        vectors = [[0.2] for _ in texts]
        # The cancellation lands "while" this call is running -- observed
        # only once it has already returned a result.
        document.status = "cancelled"
        db_session.commit()
        return vectors

    monkeypatch.setattr(ingestion, "embed_texts", fake_embed)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert calls["count"] == 1
    assert document.status == "cancelled"  # ingest_document never overrides a cancellation
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0


def test_ingest_document_deleted_during_embed_call_is_caught_before_persisting_that_batch(
    db_session, fake_store, monkeypatch
) -> None:
    """The other half of `_document_still_indexable`: the document row is
    gone outright (a completed `DELETE`), not merely marked `cancelled`,
    discovered right after an embed call returns and before that batch is
    persisted. Must abort cleanly with no chunk rows left pointing at a
    document id that no longer exists."""
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "100")
    fake_store["deleted.txt"] = b"a short document, one batch only"
    document = _make_document(db_session, "deleted.txt", "deleted.txt")
    document_id = document.id

    calls = {"count": 0}

    def fake_embed(texts):
        calls["count"] += 1
        vectors = [[0.1] for _ in texts]
        db_session.delete(document)
        db_session.commit()
        return vectors

    monkeypatch.setattr(ingestion, "embed_texts", fake_embed)

    ingestion.ingest_document(document_id, db_session)

    assert calls["count"] == 1
    assert db_session.query(models.Document).filter_by(id=document_id).first() is None
    assert _chunk_count(db_session, document_id) == 0


def test_ingest_document_retry_resets_prior_failure_and_succeeds(
    db_session, fake_store, monkeypatch
) -> None:
    """A document left `failed` by a previous attempt (Gemini was down, the
    key was missing, whatever) must be indexable again on retry: the stale
    `failure_reason` and `progress` from that earlier run must not survive
    into a run that goes on to succeed."""
    fake_store["retry.txt"] = b"content that will embed fine this time"
    document = _make_document(db_session, "retry.txt", "retry.txt", status="failed")
    document.failure_reason = "embedding service error"
    document.progress = 100
    db_session.commit()

    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[0.1] for _ in texts])

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "ready"
    assert document.failure_reason is None
    assert document.progress == 100
    assert document.chunk_count > 0


def test_ingest_document_gemini_rejected_key_fails_the_document(
    db_session, fake_store, monkeypatch
) -> None:
    """`embed_texts` can also raise `GeminiKeyRejectedError` (a key Gemini
    itself rejects, as opposed to one simply missing). `ingest_document` has
    no `except` clause naming that type specifically, so today it falls into
    the same generic path as any other embedding failure; this pins down
    that the document still ends up in a clean terminal `failed` state with
    its chunks removed, rather than an unhandled exception escaping the
    background task."""
    fake_store["rejected.txt"] = b"content that will never get embedded"
    document = _make_document(db_session, "rejected.txt", "rejected.txt")

    def rejected(texts):
        raise embeddings.GeminiKeyRejectedError("GEMINI_API_KEY was rejected", status_code=401)

    monkeypatch.setattr(ingestion, "embed_texts", rejected)

    ingestion.ingest_document(document.id, db_session)

    db_session.refresh(document)
    assert document.status == "failed"
    assert document.failure_reason == ingestion.EMBEDDING_FAILURE_REASON
    assert _chunk_count(db_session, document.id) == 0
    assert document.chunk_count == 0
