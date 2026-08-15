"""OpenAI-compatible async client for chat completions and embeddings.

A single client class talks to any OpenAI-compatible backend:

* local Ollama            -> http://localhost:11434          (LLM_*/EMBED_* unset -> OLLAMA_*)
* self-hosted vLLM        -> http://<host>:8000             (LLM_BASE_URL=...)
* hosted APIs (DashScope) -> https://dashscope.../v1        (LLM_BASE_URL=... + key)

Switch backends purely via config (LLM_*, EMBED_*); business code is untouched.
Generation and embedding can even use different backends (e.g. Qwen API for
chat + local Ollama bge-m3 for embeddings).

Module-level singletons:

* ``llm_client``   -> chat completions (generation)
* ``embed_client`` -> embeddings (retrieval / RAG ingestion)
"""

from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Ollama ignores bearer auth; sent when no API key is configured.
_DUMMY_AUTH = "Bearer ollama"


class OpenAICompatClient:
    """Async wrapper around OpenAI-compatible ``/v1/chat/completions`` and ``/v1/embeddings``.

    ``base_url`` may or may not end with ``/v1``; it is normalized at call time.
    When ``api_key`` is empty a placeholder bearer is sent (Ollama ignores it).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        llm_model: str,
        embed_model: str,
        timeout: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.llm_model = llm_model
        self.embed_model = embed_model
        self.timeout = timeout

    def _endpoint(self, path: str) -> str:
        base = self.base_url
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}{path}"

    def _auth(self) -> str:
        return f"Bearer {self.api_key}" if self.api_key else _DUMMY_AUTH

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text (order preserved)."""
        if not texts:
            return []
        headers = {"Authorization": self._auth(), "Content-Type": "application/json"}
        payload = {"model": self.embed_model, "input": texts}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self._endpoint("/embeddings"), headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0]

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict[str, object] | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion, yielding content deltas as they arrive."""
        headers = {"Authorization": self._auth(), "Content-Type": "application/json"}
        payload: dict[str, object] = {
            "model": self.llm_model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra:
            payload.update(extra)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", self._endpoint("/chat/completions"), headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    token = _parse_delta(line)
                    if token is not None:
                        yield token


def _parse_delta(line: str) -> str | None:
    """Parse a single SSE line; return content text, or None to skip."""
    if not line:
        return None
    line = line.strip()
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if payload == "[DONE]":
        return None
    try:
        import json

        obj = json.loads(payload)
    except ValueError:
        logger.debug("unparseable SSE line: %s", payload)
        return None
    choices = obj.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if not isinstance(content, str) or not content:
        return None
    return content


llm_client = OpenAICompatClient(
    base_url=settings.LLM_BASE_URL or settings.OLLAMA_BASE_URL,
    api_key=settings.LLM_API_KEY or "",
    llm_model=settings.LLM_MODEL or settings.OLLAMA_LLM_MODEL,
    embed_model=settings.EMBED_MODEL or settings.OLLAMA_EMBED_MODEL,
    timeout=settings.LLM_TIMEOUT if settings.LLM_TIMEOUT > 0 else settings.OLLAMA_TIMEOUT,
)

embed_client = OpenAICompatClient(
    base_url=settings.EMBED_BASE_URL or settings.OLLAMA_BASE_URL,
    api_key=settings.EMBED_API_KEY or "",
    llm_model=settings.LLM_MODEL or settings.OLLAMA_LLM_MODEL,
    embed_model=settings.EMBED_MODEL or settings.OLLAMA_EMBED_MODEL,
    timeout=settings.EMBED_TIMEOUT if settings.EMBED_TIMEOUT > 0 else settings.OLLAMA_TIMEOUT,
)

__all__ = ["OpenAICompatClient", "llm_client", "embed_client"]
