"""Unit tests for `app.retrieval` reaching past what
`backend/app/tests/test_retrieval.py` already covers.

That sibling file already proves: `retrieve_context`'s signature carries no
per-document or per-thread filter; an empty shared library (no document, or
only a `'processing'` one) returns `has_ready_documents=False` without ever
calling `embed_texts`; ranking spans every `'ready'` document, not just one;
chunks from a non-`'ready'` document are excluded; chunks below the
configured similarity threshold are discarded (including down to zero
survivors); and `retrieval_top_k()` caps how many chunks come back -- all of
it against the in-Python cosine fallback this module takes on SQLite.

This file reaches what that leaves uncovered:

- `retrieval_top_k()` and `retrieval_similarity_threshold()` themselves,
  read directly rather than monkeypatched away as every test in the sibling
  file does -- their documented defaults, and that each is actually read
  fresh from its own environment variable;
- `retrieve_context` embeds exactly `[question]` -- one call, one text, the
  text actually asked -- not just *some* list with one element, which is
  all the sibling file's blanket `lambda texts: [[...]]` stubs are sensitive
  to;
- the dialect dispatch itself: a `postgresql`-dialect session is routed to
  `_retrieve_postgres` and never touches `_retrieve_python`, and vice versa
  for every non-Postgres dialect -- exercised here by faking only the
  no-argument `db.get_bind()` call `retrieve_context` itself makes (the
  internal, keyword-argument calls SQLAlchemy issues to actually run a
  query are left to reach the real engine), so the branch is proved without
  a live Postgres connection;
- `max(1, retrieval_top_k())`: a misconfigured zero-or-negative top-k still
  returns exactly one chunk rather than zero;
- `_cosine_similarity`'s own zero-vector guard, which no ranking test above
  a single surviving chunk would ever exercise since a zero-norm chunk
  never has the highest score;
- the full shape of one `RetrievedChunk` -- every field, not just the
  `(document_name, source_location)` pairs the ranking-order test checks --
  and `RetrievedContext()`'s empty defaults;
- a documented, reproduced defect: a chunk that has no embedding yet
  (`Chunk.embedding is None`) is *not* actually excluded by
  `.filter(Chunk.embedding.isnot(None))` on the SQLite/JSON fallback path
  this whole suite (and a fresh local clone, per `database.py`'s own
  default) runs on, and `_retrieve_python` crashes on it with a `TypeError`
  rather than skipping it -- see that test's own docstring for why.

No live Gemini: `embed_texts` is monkeypatched in every test that reaches
it, the same way the sibling file does. No live Postgres either: the one
test about pgvector's actual cosine-distance query is a documented skip,
same as the module's own docstring says that path needs a real Postgres to
exercise -- `_retrieve_postgres` is only reached indirectly here, through a
faked dialect name, never through a real `vector` column.
"""

import uuid

import pytest

from app import retrieval
from app.models import Chunk, Document


def _make_document(db_session, status: str, file_name: str = "handbook.pdf") -> Document:
    document = Document(
        id=uuid.uuid4(),
        file_name=file_name,
        mime_type="application/pdf",
        size_bytes=10,
        storage_key=f"{uuid.uuid4()}.pdf",
        status=status,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def _make_chunk(
    db_session,
    document: Document,
    embedding: list[float] | None,
    location: str = "handbook.pdf, page 1",
    index: int = 0,
) -> Chunk:
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content=f"content for {location}",
        source_location=location,
        chunk_index=index,
        embedding=embedding,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


# --- retrieval_top_k / retrieval_similarity_threshold: read directly -------


def test_retrieval_top_k_defaults_to_documented_constant(monkeypatch) -> None:
    monkeypatch.delenv("RETRIEVAL_TOP_K", raising=False)

    assert retrieval.retrieval_top_k() == retrieval.RETRIEVAL_TOP_K_DEFAULT


def test_retrieval_top_k_is_read_from_its_own_env_var(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_TOP_K", "3")

    assert retrieval.retrieval_top_k() == 3


def test_retrieval_similarity_threshold_defaults_to_documented_constant(monkeypatch) -> None:
    monkeypatch.delenv("RETRIEVAL_SIMILARITY_THRESHOLD", raising=False)

    assert (
        retrieval.retrieval_similarity_threshold()
        == retrieval.RETRIEVAL_SIMILARITY_THRESHOLD_DEFAULT
    )


def test_retrieval_similarity_threshold_is_read_from_its_own_env_var(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.75")

    assert retrieval.retrieval_similarity_threshold() == 0.75


# --- embed_texts is called with exactly [question] --------------------------


def test_retrieve_context_embeds_exactly_the_question_as_a_single_element_list(
    db_session, monkeypatch
) -> None:
    _make_document(db_session, "ready")
    captured = {}

    def fake_embed(texts):
        captured["texts"] = texts
        return [[1.0, 0.0]]

    monkeypatch.setattr(retrieval, "embed_texts", fake_embed)

    retrieval.retrieve_context(db_session, "What is the parental leave policy?")

    assert captured["texts"] == ["What is the parental leave policy?"]


# --- a chunk with no embedding yet: a reproduced, documented defect ---------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known defect, discovered while reaching for coverage this ticket "
        "does not provide a writable path to fix (app/retrieval.py and "
        "app/models.py are both outside backend/tests/): on the SQLite/JSON "
        "fallback `EmbeddingVector` degrades to (the path every local clone "
        "runs on by `database.py`'s own default, and the only path this "
        "entire suite runs against), SQLAlchemy's `JSON` type defaults to "
        "`none_as_null=False` -- a column assigned Python `None` is "
        "persisted as the *JSON* literal `null`, not SQL `NULL`. "
        "`.filter(Chunk.embedding.isnot(None))` compiles to `IS NOT NULL`, "
        "which that row still satisfies, so the chunk is not excluded as "
        "intended; `_retrieve_python` then calls `_cosine_similarity` with "
        "`None` for that chunk's vector and crashes with a `TypeError` "
        "instead of skipping it. On a real Postgres `vector` column this "
        "does not arise -- assigning `None` there stores genuine SQL NULL -- "
        "so this is specific to local/dev/test SQLite, not to production, "
        "and is not currently reachable through `app.ingestion.ingest_document` "
        "(which never commits a chunk before it has a real embedding); it "
        "would need either `EmbeddingVector.none_as_null = True` or an "
        "explicit `sqlalchemy.null()` in retrieval's own filters to close."
    ),
)
def test_chunk_with_no_embedding_yet_is_excluded_from_the_result(db_session, monkeypatch) -> None:
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 1", 0)
    _make_chunk(db_session, document, None, "handbook.pdf, page 2", 1)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert [c.source_location for c in context.chunks] == ["handbook.pdf, page 1"]


# --- dialect dispatch: routed by db.get_bind().dialect.name, not hard-coded -


class _FakeDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeBind:
    def __init__(self, name: str) -> None:
        self.dialect = _FakeDialect(name)


def _patch_reported_dialect(monkeypatch, db_session, name: str) -> None:
    """Makes `db.get_bind()` (the exact, no-argument call `retrieve_context`
    itself makes to read the dialect name) report `name`, while every
    *internal* call SQLAlchemy issues to actually run a query -- always
    passed keyword arguments such as `clause` -- still reaches the session's
    real bind, so queries keep working against the real in-memory engine."""
    original_get_bind = db_session.get_bind

    def fake_get_bind(*args, **kwargs):
        if not args and not kwargs:
            return _FakeBind(name)
        return original_get_bind(*args, **kwargs)

    monkeypatch.setattr(db_session, "get_bind", fake_get_bind)


def test_postgresql_dialect_is_routed_to_the_postgres_path_not_the_python_one(
    db_session, monkeypatch
) -> None:
    _make_document(db_session, "ready")
    _patch_reported_dialect(monkeypatch, db_session, "postgresql")
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("_retrieve_python must not run for a postgresql dialect")

    monkeypatch.setattr(retrieval, "_retrieve_python", fail_if_called)
    monkeypatch.setattr(retrieval, "_retrieve_postgres", lambda db, vector, top_k: [])

    context = retrieval.retrieve_context(db_session, "question")

    assert context.has_ready_documents is True
    assert context.chunks == []


def test_non_postgresql_dialect_is_routed_to_the_python_path_not_postgres(
    db_session, monkeypatch
) -> None:
    document = _make_document(db_session, "ready")
    _make_chunk(db_session, document, [1.0, 0.0])
    _patch_reported_dialect(monkeypatch, db_session, "sqlite")
    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("_retrieve_postgres must not run for a non-postgresql dialect")

    monkeypatch.setattr(retrieval, "_retrieve_postgres", fail_if_called)

    context = retrieval.retrieve_context(db_session, "question")

    assert context.has_ready_documents is True
    assert len(context.chunks) == 1


@pytest.mark.skip(
    reason=(
        "_retrieve_postgres issues a real pgvector cosine_distance() query "
        "against an actual `vector(768)` column; SQLite has no such column "
        "type and no such operator, so this path cannot be exercised from "
        "an in-memory SQLite suite. The module's own docstring already "
        "names a real Postgres instance as where that path is proved; the "
        "dispatch that routes a postgresql-dialect session to it is covered "
        "above without needing one."
    )
)
def test_retrieve_postgres_ranks_by_pgvector_cosine_distance_on_a_real_postgres() -> None:
    raise AssertionError("not run: see skip reason")


# --- max(1, retrieval_top_k()): a misconfigured top-k still returns one ----


@pytest.mark.parametrize("configured_top_k", [0, -3])
def test_top_k_configured_at_zero_or_negative_still_returns_exactly_one_chunk(
    db_session, monkeypatch, configured_top_k
) -> None:
    document = _make_document(db_session, "ready")
    for i in range(3):
        _make_chunk(db_session, document, [1.0, 0.0], f"handbook.pdf, page {i}", i)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)
    monkeypatch.setattr(retrieval, "retrieval_top_k", lambda: configured_top_k)

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 1


# --- _cosine_similarity: zero-vector guard -----------------------------------


def test_cosine_similarity_returns_zero_for_a_zero_vector_instead_of_dividing_by_zero() -> None:
    assert retrieval._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert retrieval._cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0
    assert retrieval._cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_cosine_similarity_of_identical_vectors_is_one() -> None:
    assert retrieval._cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


# --- dataclass shapes ---------------------------------------------------------


def test_retrieved_context_defaults_to_empty_chunks_and_no_ready_documents() -> None:
    context = retrieval.RetrievedContext()

    assert context.chunks == []
    assert context.has_ready_documents is False


def test_retrieved_chunk_carries_every_field_the_result_needs(db_session, monkeypatch) -> None:
    document = _make_document(db_session, "ready", "handbook.pdf")
    chunk = _make_chunk(db_session, document, [1.0, 0.0], "handbook.pdf, page 3", 2)

    monkeypatch.setattr(retrieval, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(retrieval, "retrieval_similarity_threshold", lambda: -1.0)

    context = retrieval.retrieve_context(db_session, "question")

    assert len(context.chunks) == 1
    result = context.chunks[0]
    assert result.chunk_id == chunk.id
    assert result.document_id == document.id
    assert result.document_name == "handbook.pdf"
    assert result.source_location == "handbook.pdf, page 3"
    assert result.content == chunk.content
    assert result.similarity == pytest.approx(1.0)
