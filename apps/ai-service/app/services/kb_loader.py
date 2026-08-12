"""Load knowledge-base markdown/text files and split them into chunked units."""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.text_splitter import split_text


@dataclass
class KbChunk:
    id: str
    text: str
    metadata: dict[str, str | int]


def load_kb(kb_dir: str | None = None) -> list[KbChunk]:
    """Read every ``*.md``/``*.txt`` file under *kb_dir* and return chunked units.

    Stable ids of the form ``{filename}#{index}`` make re-ingest idempotent.
    """
    root = Path(kb_dir or settings.KB_DIR)
    if not root.exists():
        return []

    size = settings.TRIAGE_CHUNK_SIZE
    overlap = settings.TRIAGE_CHUNK_OVERLAP
    chunks: list[KbChunk] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        pieces = split_text(text, size, overlap)
        for index, piece in enumerate(pieces):
            chunk_id = f"{path.name}#{index}"
            chunks.append(
                KbChunk(
                    id=chunk_id,
                    text=piece,
                    metadata={"file": path.name, "index": index},
                )
            )
    return chunks
