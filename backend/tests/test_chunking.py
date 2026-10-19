"""Unit tests for `app.chunking.chunk_fragments`.

Exercises the splitter directly against plain `(text, location)` fragment
tuples -- no database, no object store, no extraction -- since everything it
does is pure: given fragments, a size and an overlap, it returns
`(content, source_location, chunk_index)` tuples. `test_ingestion.py` (and
`backend/app/tests/test_ingestion.py`, not part of this suite's `testpaths`)
cover it indirectly through the full pipeline; these tests pin down its own
contract: step size, global indexing, per-fragment isolation, empty-piece
skipping, and the size/overlap edge cases documented in its docstring.
"""

import pytest

from app.chunking import chunk_fragments

# --- basic splitting with size and overlap ----------------------------------


def test_fragment_shorter_than_size_yields_a_single_chunk() -> None:
    chunks = chunk_fragments([("short text", "doc.txt")], size=1000, overlap=200)

    assert chunks == [("short text", "doc.txt", 0)]


def test_splits_with_configured_size_and_overlap_using_size_minus_overlap_step() -> None:
    # step = size - overlap = 2, so starts are 0, 2, 4, 6 (stop once end >= 10)
    chunks = chunk_fragments([("0123456789", "doc.txt")], size=4, overlap=2)

    assert chunks == [
        ("0123", "doc.txt", 0),
        ("2345", "doc.txt", 1),
        ("4567", "doc.txt", 2),
        ("6789", "doc.txt", 3),
    ]


def test_last_chunk_is_shorter_when_text_does_not_divide_evenly() -> None:
    chunks = chunk_fragments([("a" * 25, "doc.txt")], size=10, overlap=3)

    contents = [c[0] for c in chunks]
    # step = 10 - 3 = 7, so starts are 0, 7, 14, 21
    assert contents == ["a" * 10, "a" * 10, "a" * 10, "a" * 4]
    assert [c[2] for c in chunks] == [0, 1, 2, 3]


def test_zero_overlap_produces_contiguous_non_overlapping_chunks() -> None:
    chunks = chunk_fragments([("01234567", "doc.txt")], size=4, overlap=0)

    assert chunks == [("0123", "doc.txt", 0), ("4567", "doc.txt", 1)]


# --- per-fragment isolation: a chunk never straddles two locations ----------


def test_each_fragment_is_chunked_independently_and_never_straddles_a_boundary() -> None:
    # Concatenated, "ABCDE" + "FGHIJ" would be one 10-character chunk under
    # size=10 -- the point of this test is that it never is, because the two
    # fragments are chunked separately.
    fragments = [("ABCDE", "doc.pdf, page 1"), ("FGHIJ", "doc.pdf, page 2")]

    chunks = chunk_fragments(fragments, size=10, overlap=0)

    assert chunks == [
        ("ABCDE", "doc.pdf, page 1", 0),
        ("FGHIJ", "doc.pdf, page 2", 1),
    ]


def test_chunk_index_is_global_across_fragments_not_reset_per_fragment() -> None:
    fragments = [
        ("first fragment is long enough to need splitting", "doc.pdf, page 1"),
        ("second fragment also needs splitting into pieces", "doc.pdf, page 2"),
    ]

    chunks = chunk_fragments(fragments, size=15, overlap=5)

    indices = [c[2] for c in chunks]
    assert indices == list(range(len(chunks)))
    assert len(chunks) > 2  # each fragment produced more than one chunk
    # Every chunk's location is exactly the fragment it came from, never the
    # other one, regardless of where it falls in the global index sequence.
    page_one_indices = [c[2] for c in chunks if c[1] == "doc.pdf, page 1"]
    page_two_indices = [c[2] for c in chunks if c[1] == "doc.pdf, page 2"]
    assert page_one_indices + page_two_indices == indices


# --- empty pieces are skipped, not emitted as empty chunks ------------------


def test_whitespace_only_piece_is_skipped_and_does_not_consume_an_index() -> None:
    # size=3, overlap=0 -> step=3: "abc", "   ", "def". The middle piece
    # strips to empty and must be dropped rather than stored as "".
    chunks = chunk_fragments([("abc   def", "doc.txt")], size=3, overlap=0)

    assert chunks == [("abc", "doc.txt", 0), ("def", "doc.txt", 1)]
    assert all(content for content, _location, _index in chunks)


def test_fragment_that_is_entirely_whitespace_yields_no_chunks() -> None:
    chunks = chunk_fragments([("   \n\t  ", "doc.txt")], size=100, overlap=10)

    assert chunks == []


def test_leading_and_trailing_whitespace_in_a_piece_is_stripped() -> None:
    chunks = chunk_fragments([("  padded text  ", "doc.txt")], size=1000, overlap=0)

    assert chunks == [("padded text", "doc.txt", 0)]


# --- size/overlap edge cases -------------------------------------------------


def test_overlap_greater_than_or_equal_to_size_still_advances_and_terminates() -> None:
    # step = max(1, size - overlap) clamps to 1 instead of stalling or going
    # backwards, so this must still terminate with one-character advances.
    chunks = chunk_fragments([("01234", "doc.txt")], size=2, overlap=5)

    assert chunks == [
        ("01", "doc.txt", 0),
        ("12", "doc.txt", 1),
        ("23", "doc.txt", 2),
        ("34", "doc.txt", 3),
    ]


def test_negative_overlap_is_treated_as_zero() -> None:
    chunks_negative = chunk_fragments([("01234567", "doc.txt")], size=4, overlap=-50)
    chunks_zero = chunk_fragments([("01234567", "doc.txt")], size=4, overlap=0)

    assert chunks_negative == chunks_zero


@pytest.mark.parametrize("size", [0, -1, -100])
def test_non_positive_size_raises_value_error(size: int) -> None:
    with pytest.raises(ValueError):
        chunk_fragments([("some text", "doc.txt")], size=size, overlap=0)


def test_no_fragments_yields_no_chunks() -> None:
    assert chunk_fragments([], size=1000, overlap=200) == []


def test_chunk_size_equal_to_text_length_yields_one_chunk_with_no_remainder() -> None:
    chunks = chunk_fragments([("exact fit", "doc.txt")], size=len("exact fit"), overlap=0)

    assert chunks == [("exact fit", "doc.txt", 0)]
