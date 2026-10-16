"""Splits extracted text fragments into overlapping, retrieval-sized chunks.

Size and overlap are character counts read from `app.config` at call time
(`CHUNK_SIZE` / `CHUNK_OVERLAP`, documented defaults 1000 / 200) so they can
be tuned per deployment without a code change. Each fragment -- one PDF page,
one DOCX section, or the whole file for TXT/MD -- is chunked independently,
so a chunk never straddles two source locations; its `source_location` is
always exactly the fragment's.
"""

from app.extraction import Fragment

ChunkTuple = tuple[str, str, int]


def chunk_fragments(fragments: list[Fragment], size: int, overlap: int) -> list[ChunkTuple]:
    """Returns `(content, source_location, chunk_index)` tuples, globally indexed."""
    if size <= 0:
        raise ValueError("chunk size must be positive")

    step = max(1, size - max(0, overlap))
    chunks: list[ChunkTuple] = []
    index = 0

    for text, location in fragments:
        length = len(text)
        start = 0
        while start < length:
            end = min(start + size, length)
            piece = text[start:end].strip()
            if piece:
                chunks.append((piece, location, index))
                index += 1
            if end >= length:
                break
            start += step

    return chunks
