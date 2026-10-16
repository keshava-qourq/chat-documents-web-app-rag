"""Unit tests for `app.extraction.extract_fragments` and its per-format
extractors.

No implementing-agent tests ship with this ticket (only `extraction.py`
itself was written), so this file is the extraction module's own suite.
`app/tests/test_ingestion.py` (a sibling ticket's file, not this one)
exercises extraction only as a stepping stone to the ingestion pipeline --
blank PDF pages, DOCX heading grouping, plain-text round-trips, and the
unsupported-extension error -- so it is left alone. This file goes after
what that coverage does not reach: real multi-page PDF numbering with mixed
text/blank pages (via a fake `PdfReader` since pypdf alone cannot easily
synthesise a text layer), DOCX edge cases in the heading/flush state machine
(consecutive headings, an empty-text heading, a heading with no body, a
trailing section after the last heading), extension case-insensitivity, and
non-UTF-8 bytes being replaced rather than raising.
"""

import pytest
from docx import Document as DocxDocument

from app import extraction
from app.extraction import extract_fragments


# --- dispatch -----------------------------------------------------------------


def test_extension_matching_is_case_insensitive() -> None:
    lower = extract_fragments(b"hello world", ".txt", "a.txt")
    upper = extract_fragments(b"hello world", ".TXT", "a.txt")
    assert lower == upper == [("hello world", "a.txt")]


def test_unsupported_extension_raises_value_error() -> None:
    with pytest.raises(ValueError):
        extract_fragments(b"data", ".xlsx", "sheet.xlsx")


def test_fragments_are_two_item_string_tuples() -> None:
    fragments = extract_fragments(b"hello", ".txt", "a.txt")
    assert len(fragments) == 1
    text, location = fragments[0]
    assert isinstance(text, str)
    assert isinstance(location, str)


# --- PDF ------------------------------------------------------------------


class _FakePage:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class _FakePdfReader:
    def __init__(self, _stream) -> None:
        # Populated by `_fake_pdf_reader_with_pages` below before use; a bare
        # instance is never constructed directly in these tests.
        self.pages: list[_FakePage] = []


def _fake_pdf_reader_with_pages(monkeypatch, page_texts: list[str | None]) -> None:
    class _Reader(_FakePdfReader):
        def __init__(self, stream) -> None:
            super().__init__(stream)
            self.pages = [_FakePage(t) for t in page_texts]

    monkeypatch.setattr(extraction, "PdfReader", _Reader)


def test_pdf_numbers_each_fragment_by_its_one_based_page_number(monkeypatch) -> None:
    _fake_pdf_reader_with_pages(monkeypatch, ["Page one text", "Page two text"])

    fragments = extract_fragments(b"irrelevant", ".pdf", "report.pdf")

    assert fragments == [
        ("Page one text", "report.pdf, page 1"),
        ("Page two text", "report.pdf, page 2"),
    ]


def test_pdf_skips_blank_pages_but_keeps_the_true_page_number_of_pages_with_text(
    monkeypatch,
) -> None:
    # Page 2 has no text layer (e.g. a scanned page) and must be skipped
    # entirely -- but page 4's fragment must still say "page 4", not "page
    # 2" (i.e. the numbering is not renumbered after skipping).
    _fake_pdf_reader_with_pages(monkeypatch, ["First", None, "", "Fourth"])

    fragments = extract_fragments(b"irrelevant", ".pdf", "scanned.pdf")

    assert fragments == [
        ("First", "scanned.pdf, page 1"),
        ("Fourth", "scanned.pdf, page 4"),
    ]


def test_pdf_with_only_whitespace_text_on_every_page_yields_no_fragments(monkeypatch) -> None:
    _fake_pdf_reader_with_pages(monkeypatch, ["   ", "\n\t"])

    assert extract_fragments(b"irrelevant", ".pdf", "scanned.pdf") == []


def test_pdf_fragment_text_is_stripped_of_surrounding_whitespace(monkeypatch) -> None:
    _fake_pdf_reader_with_pages(monkeypatch, ["  padded text  \n"])

    fragments = extract_fragments(b"irrelevant", ".pdf", "doc.pdf")

    assert fragments == [("padded text", "doc.pdf, page 1")]


# --- DOCX -------------------------------------------------------------------


def _docx_bytes(build) -> bytes:
    import io

    document = DocxDocument()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_docx_joins_multiple_paragraphs_under_the_same_heading_with_newlines() -> None:
    content = _docx_bytes(
        lambda d: (
            d.add_heading("Overview", level=1),
            d.add_paragraph("First line."),
            d.add_paragraph("Second line."),
        )
    )

    fragments = extract_fragments(content, ".docx", "notes.docx")

    assert fragments == [("First line.\nSecond line.", "notes.docx, Overview")]


def test_docx_consecutive_headings_with_no_body_text_produce_no_empty_fragment() -> None:
    content = _docx_bytes(
        lambda d: (
            d.add_heading("Empty Section", level=1),
            d.add_heading("Real Section", level=1),
            d.add_paragraph("Body text."),
        )
    )

    fragments = extract_fragments(content, ".docx", "notes.docx")

    # Nothing was ever flushed for "Empty Section" since no text accumulated
    # under it before the next heading replaced it.
    assert fragments == [("Body text.", "notes.docx, Real Section")]


def test_docx_heading_with_empty_text_keeps_the_previous_heading_as_the_location() -> None:
    content = _docx_bytes(
        lambda d: (
            d.add_heading("Section A", level=1),
            d.add_paragraph("Text under A."),
            d.add_heading("", level=1),
            d.add_paragraph("More text, still under A."),
        )
    )

    fragments = extract_fragments(content, ".docx", "notes.docx")

    assert fragments == [
        ("Text under A.", "notes.docx, Section A"),
        ("More text, still under A.", "notes.docx, Section A"),
    ]


def test_docx_with_a_heading_and_no_body_text_at_all_yields_no_fragments() -> None:
    content = _docx_bytes(lambda d: d.add_heading("Lonely Heading", level=1))

    assert extract_fragments(content, ".docx", "notes.docx") == []


def test_docx_text_after_the_last_heading_is_flushed_without_a_trailing_heading() -> None:
    # The final `flush()` call after the loop ends is what this covers: text
    # accumulated under the last heading must not be dropped just because
    # there is no subsequent heading to trigger the flush.
    content = _docx_bytes(
        lambda d: (
            d.add_heading("Only Heading", level=1),
            d.add_paragraph("Trailing body text."),
        )
    )

    fragments = extract_fragments(content, ".docx", "notes.docx")

    assert fragments == [("Trailing body text.", "notes.docx, Only Heading")]


def test_docx_blank_paragraphs_between_body_lines_are_not_added_as_empty_lines() -> None:
    content = _docx_bytes(
        lambda d: (
            d.add_heading("Section", level=1),
            d.add_paragraph("Line one."),
            d.add_paragraph(""),
            d.add_paragraph("Line two."),
        )
    )

    fragments = extract_fragments(content, ".docx", "notes.docx")

    assert fragments == [("Line one.\nLine two.", "notes.docx, Section")]


# --- TXT / MD ----------------------------------------------------------------


def test_txt_and_md_are_extracted_identically_as_a_single_fragment_at_the_file_name() -> None:
    body = "# Title\n\nSome body text."
    txt_fragments = extract_fragments(body.encode("utf-8"), ".txt", "notes.txt")
    md_fragments = extract_fragments(body.encode("utf-8"), ".md", "notes.md")

    assert txt_fragments == [(body, "notes.txt")]
    assert md_fragments == [(body, "notes.md")]


def test_plain_text_whitespace_only_content_yields_no_fragments() -> None:
    assert extract_fragments(b"   \n\t  ", ".txt", "empty.txt") == []


def test_plain_text_non_utf8_bytes_are_replaced_rather_than_raising() -> None:
    # 0xff is not valid UTF-8 on its own; this must not raise a
    # UnicodeDecodeError, and the surrounding valid text must survive intact.
    content = b"before \xff after"

    fragments = extract_fragments(content, ".txt", "binary.txt")

    assert len(fragments) == 1
    text, location = fragments[0]
    assert location == "binary.txt"
    assert "before" in text
    assert "after" in text
