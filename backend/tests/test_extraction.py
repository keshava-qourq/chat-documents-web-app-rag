"""Unit tests for `app.extraction.extract_fragments` and its per-format
helpers.

Exercises the extractor directly against raw bytes -- no database, no
object store, no chunking or ingestion pipeline. `backend/app/tests/
test_ingestion.py` (not part of this suite's `testpaths`, see pytest.ini)
touches a handful of these cases incidentally while testing the pipeline
around it; these tests pin down extraction's own contract: the
`(text, source_location)` fragment shape for each of the four supported
formats, the page-numbering and empty-page rules for PDF, the
heading-grouping rules for DOCX, and the dispatch/validation behaviour of
`extract_fragments` itself.
"""

import io

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter

from app import extraction

# --- PDF test fixtures -------------------------------------------------------


def _blank_pdf_bytes(page_count: int) -> bytes:
    """pypdf's `PdfWriter` has no API for drawing text, so blank pages are
    the easy, reliable way to produce a PDF with no text layer at all --
    standing in for a scanned page."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _build_pdf_with_text(pages_text: list[str]) -> bytes:
    """Hand-rolls a minimal multi-page PDF with a real text layer (one `Tj`
    show-text operator per page), since the project has no PDF-generation
    library in requirements.txt and `PdfWriter` cannot draw text. A page
    whose text is the empty string gets a content stream that shows nothing,
    standing in for a page with no extractable text alongside pages that do
    have one, so page numbering across a mixed document can be checked.
    Object offsets for the xref table are computed from what is actually
    written, so this stays correct if the content above it changes."""
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages_text)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages_text)} >>".encode())

    font_obj_num = 3 + 2 * len(pages_text)
    for i, text in enumerate(pages_text):
        page_num = 3 + 2 * i
        content_num = page_num + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
                f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
                f"/Contents {content_num} 0 R >>"
            ).encode()
        )
        stream = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode()
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{i} 0 obj\n".encode())
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref_offset = buffer.tell()
    count = len(objects) + 1
    buffer.write(f"xref\n0 {count}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    )
    return buffer.getvalue()


# --- PDF extraction -----------------------------------------------------------


def test_extract_pdf_returns_one_fragment_per_page_with_correct_page_numbers() -> None:
    content = _build_pdf_with_text(["First page text", "Second page text"])

    fragments = extraction.extract_fragments(content, ".pdf", "report.pdf")

    assert fragments == [
        ("First page text", "report.pdf, page 1"),
        ("Second page text", "report.pdf, page 2"),
    ]


def test_extract_pdf_skips_pages_with_no_text_but_keeps_true_page_numbers_for_the_rest() -> None:
    # Page 1 has no text layer (as a scanned page would); page 2 does. The
    # fragment for page 2 must still say "page 2", not "page 1" -- the
    # numbering tracks the page's real position, not the fragment's.
    content = _build_pdf_with_text(["", "Second page text"])

    fragments = extraction.extract_fragments(content, ".pdf", "mixed.pdf")

    assert fragments == [("Second page text", "mixed.pdf, page 2")]


def test_extract_pdf_all_blank_pages_yields_no_fragments() -> None:
    content = _blank_pdf_bytes(page_count=2)

    fragments = extraction.extract_fragments(content, ".pdf", "scanned.pdf")

    assert fragments == []


# --- DOCX extraction -----------------------------------------------------------


def test_extract_docx_groups_text_under_headings_with_file_name_prefix() -> None:
    document = DocxDocument()
    document.add_heading("Introduction", level=1)
    document.add_paragraph("This is the intro body.")
    document.add_heading("Conclusion", level=1)
    document.add_paragraph("This is the conclusion body.")
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "notes.docx")

    assert fragments == [
        ("This is the intro body.", "notes.docx, Introduction"),
        ("This is the conclusion body.", "notes.docx, Conclusion"),
    ]


def test_extract_docx_joins_multiple_paragraphs_under_one_heading_with_newlines() -> None:
    document = DocxDocument()
    document.add_heading("Section", level=1)
    document.add_paragraph("First line.")
    document.add_paragraph("Second line.")
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "notes.docx")

    assert fragments == [("First line.\nSecond line.", "notes.docx, Section")]


def test_extract_docx_with_no_headings_uses_file_name_alone_as_location() -> None:
    document = DocxDocument()
    document.add_paragraph("No headings here, just body text.")
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "plain.docx")

    assert fragments == [("No headings here, just body text.", "plain.docx")]


def test_extract_docx_heading_with_no_body_text_produces_no_fragment_for_it() -> None:
    # Two consecutive headings: the first has no paragraph before the next
    # heading, so it must not surface as an empty fragment.
    document = DocxDocument()
    document.add_heading("Empty Section", level=1)
    document.add_heading("Real Section", level=1)
    document.add_paragraph("Body text for the real section.")
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "notes.docx")

    assert fragments == [("Body text for the real section.", "notes.docx, Real Section")]


def test_extract_docx_with_no_paragraphs_at_all_yields_no_fragments() -> None:
    document = DocxDocument()
    buffer = io.BytesIO()
    document.save(buffer)

    fragments = extraction.extract_fragments(buffer.getvalue(), ".docx", "empty.docx")

    assert fragments == []


# --- TXT / MD extraction -------------------------------------------------------


def test_extract_txt_returns_single_fragment_located_at_file_name() -> None:
    fragments = extraction.extract_fragments(b"hello world", ".txt", "readme.txt")
    assert fragments == [("hello world", "readme.txt")]


def test_extract_md_returns_single_fragment_located_at_file_name() -> None:
    fragments = extraction.extract_fragments(b"# Title\n\nbody", ".md", "summary.md")
    assert fragments == [("# Title\n\nbody", "summary.md")]


def test_extract_plain_strips_leading_and_trailing_whitespace() -> None:
    fragments = extraction.extract_fragments(b"  \n padded content \n  ", ".txt", "padded.txt")
    assert fragments == [("padded content", "padded.txt")]


def test_extract_plain_empty_or_whitespace_only_file_yields_no_fragments() -> None:
    assert extraction.extract_fragments(b"", ".txt", "empty.txt") == []
    assert extraction.extract_fragments(b"   \n  ", ".md", "empty.md") == []


def test_extract_plain_replaces_bytes_that_are_not_valid_utf8_instead_of_raising() -> None:
    # 0xff is not valid UTF-8 anywhere; the extractor must not raise on it.
    fragments = extraction.extract_fragments(b"valid \xff text", ".txt", "mixed.txt")

    assert len(fragments) == 1
    text, location = fragments[0]
    assert location == "mixed.txt"
    assert "valid" in text and "text" in text


# --- dispatch and validation ---------------------------------------------------


def test_extract_fragments_is_case_insensitive_on_the_extension() -> None:
    fragments = extraction.extract_fragments(b"hello world", ".TXT", "readme.txt")
    assert fragments == [("hello world", "readme.txt")]


def test_extract_fragments_unsupported_extension_raises_value_error() -> None:
    with pytest.raises(ValueError, match=r"\.xlsx"):
        extraction.extract_fragments(b"data", ".xlsx", "sheet.xlsx")
