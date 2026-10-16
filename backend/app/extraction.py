"""Text extraction for the four supported upload formats.

Each extractor returns a list of `(text, source_location)` fragments rather
than one blob, so the chunker and the stored chunks can each carry a source
location precise enough to cite back to -- a page number for PDF, a section
heading for DOCX, and the file name itself for TXT/MD. A scanned, image-only
PDF yields no fragments at all (pypdf extracts nothing from a page with no
text layer); the caller treats that the same as any other empty-extraction
case and marks the document failed rather than storing zero chunks silently.
"""

import io

from docx import Document as DocxDocument
from pypdf import PdfReader

Fragment = tuple[str, str]


def extract_fragments(content: bytes, extension: str, file_name: str) -> list[Fragment]:
    """Dispatches to the extractor for `extension` (expected lower-cased, with the dot).

    Raises `ValueError` for any extension the pipeline does not support --
    the router already rejects these at upload time, so reaching this means
    something else went wrong (a storage_key that doesn't match its upload).
    """
    extension = extension.lower()
    if extension == ".pdf":
        return _extract_pdf(content, file_name)
    if extension == ".docx":
        return _extract_docx(content, file_name)
    if extension in (".txt", ".md"):
        return _extract_plain(content, file_name)
    raise ValueError(f"Unsupported file extension: {extension}")


def _extract_pdf(content: bytes, file_name: str) -> list[Fragment]:
    reader = PdfReader(io.BytesIO(content))
    fragments: list[Fragment] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            fragments.append((text, f"{file_name}, page {page_number}"))
    return fragments


def _extract_docx(content: bytes, file_name: str) -> list[Fragment]:
    document = DocxDocument(io.BytesIO(content))
    fragments: list[Fragment] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        text = "\n".join(current_lines).strip()
        if text:
            location = f"{file_name}, {current_heading}" if current_heading else file_name
            fragments.append((text, location))

    for paragraph in document.paragraphs:
        style_name = (paragraph.style.name if paragraph.style else "") or ""
        if style_name.lower().startswith("heading"):
            flush()
            current_heading = paragraph.text.strip() or current_heading
            current_lines = []
        elif paragraph.text.strip():
            current_lines.append(paragraph.text)

    flush()
    return fragments


def _extract_plain(content: bytes, file_name: str) -> list[Fragment]:
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    return [(text, file_name)]
