"""Ingest knowledge-base markdown/text files into the ChromaDB collection.

Run with either:
    python -m scripts.ingest_kb
    python scripts/ingest_kb.py
    ingest-kb   (if installed via pip install -e ".[dev]")
"""

import asyncio

from app.services.kb_loader import load_kb
from app.services.llm_client import embed_client
from app.services.vector_store import get_vector_store

BATCH_SIZE = 32


async def run() -> None:
    chunks = load_kb()
    if not chunks:
        print("No knowledge files found under KB_DIR.")
        return

    store = get_vector_store()
    total = 0
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        embeddings = await embed_client.embed([c.text for c in batch])
        store.upsert(
            ids=[c.id for c in batch],
            documents=[c.text for c in batch],
            metadatas=[c.metadata for c in batch],
            embeddings=embeddings,
        )
        total += len(batch)
        print(f"ingested {total}/{len(chunks)} chunks")

    print(f"done: collection now holds {store.count()} chunks")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
