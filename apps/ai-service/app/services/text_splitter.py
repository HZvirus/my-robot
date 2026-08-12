"""Character-sliding-window text splitter with simple paragraph-aware boundaries."""


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Split *text* into chunks of at most *size* characters with *overlap*.

    Splits on paragraph/line boundaries first, then packs segments into chunks
    without exceeding *size*. When a single segment is longer than *size* it is
    hard-split with the given *overlap* so no content is dropped.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    for segment in _segments(text):
        if len(segment) <= size:
            chunks = _append_chunk(chunks, segment, size, overlap)
        else:
            for piece in _hard_split(segment, size, overlap):
                chunks = _append_chunk(chunks, piece, size, overlap)
    return chunks


def _segments(text: str) -> list[str]:
    """Split into non-empty paragraph/line segments, preserving headings."""
    parts = [p.strip() for p in text.split("\n")]
    return [p for p in parts if p]


def _append_chunk(chunks: list[str], piece: str, size: int, overlap: int) -> list[str]:
    if not piece:
        return chunks
    if chunks and len(chunks[-1]) + 1 + len(piece) <= size:
        chunks[-1] = f"{chunks[-1]}\n{piece}"
    else:
        chunks.append(piece)
    return chunks


def _hard_split(segment: str, size: int, overlap: int) -> list[str]:
    step = size - overlap
    out: list[str] = []
    i = 0
    while i < len(segment):
        out.append(segment[i : i + size])
        if i + size >= len(segment):
            break
        i += step
    return out
