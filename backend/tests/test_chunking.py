"""Unit tests for `app/chunking.py` in isolation from the rest of the
ingestion pipeline (extraction, embeddings, persistence are covered in
`test_ingestion.py`). These exercise `chunk_fragments` directly against the
behaviours described in its module docstring: character-based size/overlap
from caller-supplied arguments, one fragment never straddling a chunk, a
strictly increasing global index, and the edge cases the basic
size/overlap test in `test_ingestion.py` does not reach -- overlap clamped
at or above size, negative overlap, boundary-exact fragments, whitespace-only
pieces, and index continuity across a fragment that yields no chunk at all.

No acceptance criteria are attached to this ticket; the cases below follow
from the module's own documented contract instead.
"""

import pytest

from app import chunking


def test_chunk_fragments_empty_fragment_list_returns_no_chunks() -> None:
    assert chunking.chunk_fragments([], size=100, overlap=10) == []


def test_chunk_fragments_rejects_negative_size() -> None:
    with pytest.raises(ValueError):
        chunking.chunk_fragments([("x", "loc")], size=-5, overlap=0)


def test_chunk_fragments_overlap_at_or_above_size_still_advances() -> None:
    """step = max(1, size - overlap); an overlap >= size must not stall the
    loop or produce a step of zero (which would loop forever)."""
    chunks = chunking.chunk_fragments([("abcdefgh", "loc")], size=5, overlap=10)

    contents = [c[0] for c in chunks]
    indices = [c[2] for c in chunks]
    assert contents == ["abcde", "bcdef", "cdefg", "defgh"]
    assert indices == [0, 1, 2, 3]


def test_chunk_fragments_negative_overlap_behaves_like_zero_overlap() -> None:
    text = "abcdefghijkl"
    with_negative = chunking.chunk_fragments([(text, "loc")], size=5, overlap=-3)
    with_zero = chunking.chunk_fragments([(text, "loc")], size=5, overlap=0)

    assert with_negative == with_zero
    assert [c[0] for c in with_negative] == ["abcde", "fghij", "kl"]


def test_chunk_fragments_text_exactly_matching_size_yields_a_single_chunk() -> None:
    chunks = chunking.chunk_fragments([("a" * 10, "loc")], size=10, overlap=2)

    assert len(chunks) == 1
    assert chunks[0] == ("a" * 10, "loc", 0)


def test_chunk_fragments_strips_whitespace_introduced_at_a_chunk_boundary() -> None:
    """A chunk boundary landing inside whitespace must not leave that
    whitespace in the stored content, on either side of the cut."""
    chunks = chunking.chunk_fragments([("ab   cd", "loc")], size=4, overlap=0)

    assert [c[0] for c in chunks] == ["ab", "cd"]
    assert [c[2] for c in chunks] == [0, 1]


def test_chunk_fragments_whitespace_only_fragment_yields_no_chunk_and_does_not_consume_an_index(
    ) -> None:
    """A fragment whose entire text strips to nothing (e.g. extraction
    produced a blank section) must be skipped silently -- and the index
    sequence given to the next fragment's chunks must not show a gap for it."""
    fragments = [("   \n  ", "blank-loc"), ("real text here", "real-loc")]

    chunks = chunking.chunk_fragments(fragments, size=100, overlap=0)

    assert len(chunks) == 1
    assert chunks[0] == ("real text here", "real-loc", 0)


def test_chunk_fragments_global_index_is_contiguous_across_multiple_chunked_fragments() -> None:
    """Each fragment is chunked independently (a chunk never straddles two
    source locations), but the index sequence handed back must still be one
    contiguous, increasing run across fragment boundaries."""
    fragments = [("a" * 12, "loc1"), ("b" * 12, "loc2")]

    chunks = chunking.chunk_fragments(fragments, size=5, overlap=0)

    assert [c[2] for c in chunks] == [0, 1, 2, 3, 4, 5]
    assert [c[1] for c in chunks] == ["loc1", "loc1", "loc1", "loc2", "loc2", "loc2"]
    assert [c[0] for c in chunks] == ["aaaaa", "aaaaa", "aa", "bbbbb", "bbbbb", "bb"]


def test_chunk_fragments_no_chunk_ever_mixes_content_from_two_fragments() -> None:
    fragments = [("first fragment body", "loc-a"), ("second fragment body", "loc-b")]

    chunks = chunking.chunk_fragments(fragments, size=1000, overlap=200)

    assert len(chunks) == 2
    assert chunks[0][0] == "first fragment body"
    assert chunks[0][1] == "loc-a"
    assert chunks[1][0] == "second fragment body"
    assert chunks[1][1] == "loc-b"
