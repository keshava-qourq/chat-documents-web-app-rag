"""Tests for the background ingestion pipeline: extraction, chunking,
embeddings with retry, and the terminal status/progress/failure handling
`ingest_document` is responsible for.

No live Gemini, MinIO or Postgres: Gemini calls go through `embed_texts`,
which every ingestion test monkeypatches directly, and the object store is a
tiny in-memory stand-in for `storage.get_client()`.
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
        def embed_content(self, model, contents):
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
        def embed_content(self, model, contents):
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


def _make_document(db_session, file_name: str, storage_key: str) -> models.Document:
    document = models.Document(
        id=uuid.uuid4(),
        file_name=file_name,
        mime_type="text/plain",
        size_bytes=100,
        storage_key=storage_key,
        status="processing",
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
