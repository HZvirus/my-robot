"""Load knowledge-base markdown/text files and split them into chunked units.

Files live under <KB_DIR>/<scope>/ (e.g. knowledge/public/). The directory
name is the scope and becomes chunk metadata, driving per-scope isolation in
the vector store.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.rbac import KB_SCOPES
from app.services.text_splitter import split_text


@dataclass
class KbChunk:
    id: str
    text: str
    metadata: dict[str, str | int]


def load_kb(kb_dir: str | None = None) -> list[KbChunk]:
    """Read every .md/.txt file under <kb_dir>/<scope>/ and return chunked units.

    Stable ids of the form {scope}/{filename}#{index} make re-ingest
    idempotent per scope.
    """
    root = Path(kb_dir or settings.KB_DIR)
    if not root.exists():
        return []

    size = settings.TRIAGE_CHUNK_SIZE
    overlap = settings.TRIAGE_CHUNK_OVERLAP
    chunks: list[KbChunk] = []

    for scope in KB_SCOPES:
        scope_dir = root / scope
        if not scope_dir.exists():
            continue
        for path in sorted(scope_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8")
            pieces = split_text(text, size, overlap)
            for index, piece in enumerate(pieces):
                chunk_id = f"{scope}/{path.name}#{index}"
                chunks.append(
                    KbChunk(
                        id=chunk_id,
                        text=piece,
                        metadata={"file": path.name, "index": index, "scope": scope},
                    )
                )
    return chunks
