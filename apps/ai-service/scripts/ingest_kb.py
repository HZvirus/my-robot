"""Ingest knowledge-base markdown/text files into per-scope ChromaDB collections.

Run with either:
    python -m scripts.ingest_kb
    python scripts/ingest_kb.py
    ingest-kb   (if installed via pip install -e ".[dev]")
"""

import asyncio

from app.services.kb_loader import KbChunk, load_kb
from app.services.llm_client import embed_client
from app.services.vector_store import get_vector_store

BATCH_SIZE = 32


async def run() -> None:
    chunks = load_kb()
    if not chunks:
        print("No knowledge files found under <KB_DIR>/<scope>/.")
        return

    store = get_vector_store()
    by_scope: dict[str, list[KbChunk]] = {}
    for chunk in chunks:
        scope = str(chunk.metadata.get("scope", "public"))
        by_scope.setdefault(scope, []).append(chunk)

    total = 0
    for scope, group in by_scope.items():
        for start in range(0, len(group), BATCH_SIZE):
            batch = group[start : start + BATCH_SIZE]
            embeddings = await embed_client.embed([c.text for c in batch])
            store.upsert(
                scope,
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[c.metadata for c in batch],
                embeddings=embeddings,
            )
            total += len(batch)
            print(f"ingested {total}/{len(chunks)} chunks (scope={scope})")

    print(f"done: {store.count()} chunks across scopes {sorted(by_scope)}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
