"""Unit tests for `app.chunking.chunk_fragments`.

This exercises the splitter in isolation from extraction and embeddings --
`app/tests/test_ingestion.py` already covers the basic size/overlap split,
per-fragment independence of `source_location`, and rejection of a
non-positive size; this file reaches the edges that leaves uncovered: a
negative overlap, an overlap that meets or exceeds the chunk size (which
must still terminate rather than loop or duplicate a chunk forever),
whitespace-only fragments being dropped rather than stored as empty chunks,
a fragment whose length divides evenly into chunks leaving no trailing
empty piece, `chunk_index` staying globally sequential across *multiple*
chunks from *multiple* fragments (not just one chunk per fragment), and an
empty fragment list producing no chunks at all.
"""

import pytest

from app.chunking import chunk_fragments


def test_empty_fragment_list_returns_no_chunks() -> None:
    assert chunk_fragments([], size=10, overlap=2) == []


def test_negative_size_raises_value_error() -> None:
    with pytest.raises(ValueError):
        chunk_fragments([("some text", "doc.txt")], size=-5, overlap=0)


def test_negative_overlap_is_treated_as_no_overlap() -> None:
    # size=5, overlap=-10 must behave exactly like overlap=0 (step == size):
    # consecutive, non-overlapping chunks with nothing repeated between them.
    text = "a" * 15
    chunks = chunk_fragments([(text, "doc.txt")], size=5, overlap=-10)

    contents = [c[0] for c in chunks]
    assert contents == ["a" * 5, "a" * 5, "a" * 5]
    assert [c[2] for c in chunks] == [0, 1, 2]


def test_overlap_equal_to_size_still_terminates_and_advances_by_one() -> None:
    # step = max(1, size - overlap) = max(1, 0) = 1, so this must not loop
    # forever and must still make forward progress one character at a time
    # once the text is longer than a single window.
    text = "abcdefgh"
    chunks = chunk_fragments([(text, "doc.txt")], size=5, overlap=5)

    contents = [c[0] for c in chunks]
    assert contents == ["abcde", "bcdef", "cdefg", "defgh"]
    assert [c[2] for c in chunks] == list(range(len(chunks)))


def test_overlap_greater_than_size_still_terminates() -> None:
    text = "abcdefghij"
    chunks = chunk_fragments([(text, "doc.txt")], size=4, overlap=100)

    # Must still finish (step floors at 1) and must still cover the text.
    assert len(chunks) > 0
    assert chunks[-1][0].endswith("j")


def test_fragment_length_exact_multiple_of_size_has_no_trailing_empty_chunk() -> None:
    text = "a" * 20
    chunks = chunk_fragments([(text, "doc.txt")], size=10, overlap=0)

    contents = [c[0] for c in chunks]
    assert contents == ["a" * 10, "a" * 10]
    assert [c[2] for c in chunks] == [0, 1]


def test_whitespace_only_fragment_yields_no_chunks() -> None:
    chunks = chunk_fragments([("   \n\t  ", "doc.txt")], size=10, overlap=2)
    assert chunks == []


def test_leading_and_trailing_whitespace_in_a_piece_is_stripped() -> None:
    # size=6 over "  ab  cd  " (10 chars) produces windows that land on
    # whitespace-padded slices; the stored content must be stripped.
    text = "  ab  cd  "
    chunks = chunk_fragments([(text, "doc.txt")], size=6, overlap=0)

    for content, _location, _index in chunks:
        assert content == content.strip()
        assert content != ""


def test_chunk_index_is_globally_sequential_across_multiple_chunks_in_multiple_fragments() -> None:
    # Each fragment here produces more than one chunk on its own (size=5
    # against a 12-character fragment), so this proves the running index
    # carries across fragment boundaries, not just across fragment count.
    fragments = [
        ("a" * 12, "doc.txt, page 1"),
        ("b" * 12, "doc.txt, page 2"),
    ]

    chunks = chunk_fragments(fragments, size=5, overlap=0)

    assert [c[2] for c in chunks] == list(range(len(chunks)))
    page_one_locations = [loc for _content, loc, _idx in chunks if loc == "doc.txt, page 1"]
    page_two_locations = [loc for _content, loc, _idx in chunks if loc == "doc.txt, page 2"]
    assert len(page_one_locations) > 1
    assert len(page_two_locations) > 1
    # The last chunk of page 1 and the first chunk of page 2 must have
    # consecutive indices -- the counter never resets at a fragment boundary.
    page_one_last_index = max(idx for _content, loc, idx in chunks if loc == "doc.txt, page 1")
    page_two_first_index = min(idx for _content, loc, idx in chunks if loc == "doc.txt, page 2")
    assert page_two_first_index == page_one_last_index + 1


def test_a_fragment_with_only_whitespace_does_not_consume_a_chunk_index() -> None:
    # The blank fragment in the middle must be skipped entirely rather than
    # reserving an index for an empty chunk that is never appended.
    fragments = [
        ("first", "doc.txt, a"),
        ("   ", "doc.txt, b"),
        ("second", "doc.txt, c"),
    ]

    chunks = chunk_fragments(fragments, size=100, overlap=0)

    assert [c[1] for c in chunks] == ["doc.txt, a", "doc.txt, c"]
    assert [c[2] for c in chunks] == [0, 1]
