"""ChromaDB-backed vector store with per-scope physical isolation.

Each knowledge-base scope lives in its own ChromaDB collection
(hospital_kb__<scope>). ScopedVectorStore fans queries out only across the
collections the caller is permitted to read, so documents from other scopes
are never retrieved -- isolation is enforced at retrieval time, not in the
prompt.
"""

from pathlib import Path
from typing import Any, Protocol

import chromadb

from app.core.config import settings
from app.core.logger import get_logger
from app.core.rbac import KB_SCOPES

logger = get_logger(__name__)


class VectorStoreProtocol(Protocol):
    def upsert(
        self,
        scope: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str | int]],
        embeddings: list[list[float]],
    ) -> None: ...

    def query(
        self,
        embedding: list[float],
        *,
        scopes: list[str],
        n_results: int | None = None,
        where: dict[str, str | int] | None = None,
    ) -> list[dict[str, Any]]: ...

    def count(self, scope: str | None = None) -> int: ...


def _distance(r: dict[str, Any]) -> float:
    d = r.get("distance")
    return float(d) if d is not None else float("inf")


class ChromaVectorStore:
    """Single-collection ChromaDB store bound to one scope."""

    def __init__(self, persist_dir: str, collection_name: str) -> None:
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None

    def _ensure(self) -> None:
        if self._collection is not None:
            return
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_dir)
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


class ScopedVectorStore:
    """Routes upsert/query by knowledge-base scope.

    query() only touches the collections listed in scopes; collections for
    other scopes are never opened, so their content cannot leak into results.
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_prefix: str | None = None,
    ) -> None:
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._prefix = collection_prefix or settings.CHROMA_COLLECTION
        self._stores: dict[str, ChromaVectorStore] = {}

    def _store_for(self, scope: str) -> ChromaVectorStore:
        store = self._stores.get(scope)
        if store is None:
            store = ChromaVectorStore(self._persist_dir, f"{self._prefix}__{scope}")
            self._stores[scope] = store
        return store

    def upsert(
        self,
        scope: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str | int]],
        embeddings: list[list[float]],
    ) -> None:
        self._store_for(scope).upsert(ids, documents, metadatas, embeddings)

    def query(
        self,
        embedding: list[float],
        *,
        scopes: list[str],
        n_results: int | None = None,
        where: dict[str, str | int] | None = None,
    ) -> list[dict[str, Any]]:
        per_scope = n_results if n_results is not None else settings.TRIAGE_TOP_K
        merged: list[dict[str, Any]] = []
        for scope in scopes:
            try:
                merged.extend(
                    self._store_for(scope).query(
                        embedding, n_results=per_scope, where=where
                    )
                )
            except Exception:
                logger.warning("scope query failed scope=%s", scope, exc_info=True)
        # Cosine distance: lower is more similar; keep the closest chunks.
        merged.sort(key=_distance)
        top_n = n_results if n_results is not None else settings.TRIAGE_TOP_K
        return merged[:top_n]

    def count(self, scope: str | None = None) -> int:
        if scope is not None:
            try:
                return self._store_for(scope).count()
            except Exception:
                return 0
        total = 0
        for name in KB_SCOPES:
            try:
                total += self._store_for(name).count()
            except Exception:
                continue
        return total


_store: ScopedVectorStore | None = None


def get_vector_store() -> ScopedVectorStore:
    global _store
    if _store is None:
        _store = ScopedVectorStore()
    return _store
