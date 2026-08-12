"""ChromaDB-backed vector store with a stable interface (swappable for FAISS)."""

from pathlib import Path
from typing import Any, Protocol

import chromadb

from app.core.config import settings


class VectorStoreProtocol(Protocol):
    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str | int]],
        embeddings: list[list[float]],
    ) -> None: ...

    def query(
        self,
        embedding: list[float],
        n_results: int | None = None,
        where: dict[str, str | int] | None = None,
    ) -> list[dict[str, Any]]: ...

    def count(self) -> int: ...


class ChromaVectorStore:
    """Persistent ChromaDB collection storing hospital knowledge-base chunks."""

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._collection_name = collection_name or settings.CHROMA_COLLECTION
        self._client: Any = None
        self._collection: Any = None

    def _ensure(self) -> None:
        if self._collection is not None:
            return
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str | int]],
        embeddings: list[list[float]],
    ) -> None:
        self._ensure()
        assert self._collection is not None
        self._collection.upsert(
            ids=list(ids),
            documents=list(documents),
            metadatas=list(metadatas),
            embeddings=[list(e) for e in embeddings],
        )

    def query(
        self,
        embedding: list[float],
        n_results: int | None = None,
        where: dict[str, str | int] | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure()
        assert self._collection is not None
        try:
            return self._run_query(self._collection, embedding, n_results, where)
        except Exception:
            # ChromaDB caches segment metadata in the collection object; if the
            # KB was re-ingested by another process while this server was
            # running, the cached state is stale. Invalidate and retry once.
            self._collection = None
            self._ensure()
            assert self._collection is not None
            return self._run_query(self._collection, embedding, n_results, where)

    def _run_query(
        self,
        collection: Any,
        embedding: list[float],
        n_results: int | None,
        where: dict[str, str | int] | None,
    ) -> list[dict[str, Any]]:
        n = n_results if n_results is not None else settings.TRIAGE_TOP_K
        result = collection.query(
            query_embeddings=[list(embedding)],
            n_results=n,
            where=where,
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        out: list[dict[str, Any]] = []
        for i, doc in enumerate(documents):
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = distances[i] if i < len(distances) else None
            out.append({"document": doc, "metadata": meta or {}, "distance": dist})
        return out

    def count(self) -> int:
        self._ensure()
        assert self._collection is not None
        return int(self._collection.count())


_store: ChromaVectorStore | None = None


def get_vector_store() -> ChromaVectorStore:
    global _store
    if _store is None:
        _store = ChromaVectorStore()
    return _store
