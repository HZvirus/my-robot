"""Async client for a local Ollama server using its OpenAI-compatible endpoints."""

from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_DUMMY_AUTH = "Bearer ollama"


class OllamaClient:
    """Thin async wrapper around Ollama's `/v1/embeddings` and `/v1/chat/completions`.

    Endpoints accept (and ignore) any bearer token, so a placeholder is sent.
    """

    def __init__(
        self,
        base_url: str | None = None,
        llm_model: str | None = None,
        embed_model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.llm_model = llm_model or settings.OLLAMA_LLM_MODEL
        self.embed_model = embed_model or settings.OLLAMA_EMBED_MODEL
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text (order preserved)."""
        if not texts:
            return []
        headers = {"Authorization": _DUMMY_AUTH, "Content-Type": "application/json"}
        payload = {"model": self.embed_model, "input": texts}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/embeddings", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0]

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream chat completion, yielding content deltas as they arrive."""
        headers = {"Authorization": _DUMMY_AUTH, "Content-Type": "application/json"}
        payload = {"model": self.llm_model, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/v1/chat/completions", headers=headers, json=payload
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


ollama_client = OllamaClient()
