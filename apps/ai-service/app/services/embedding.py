"""Embedding helper wrapping :class:`OpenAICompatClient` with optional single-text caching."""

from collections.abc import Sequence

from app.services.llm_client import OpenAICompatClient, embed_client


class EmbeddingService:
    def __init__(self, client: OpenAICompatClient | None = None, cache_size: int = 256) -> None:
        self._client = client or embed_client
        self._cache_size = cache_size
        self._cache: dict[str, list[float]] = {}

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)
        if not texts:
            return []
        return await self._client.embed(texts)

    async def embed_one(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = await self._client.embed_one(text)
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[text] = vector
        return vector


embedding_service = EmbeddingService()
