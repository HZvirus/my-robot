from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .base import ChatRequest, ModelAdapter


class OllamaAdapter(ModelAdapter):
    """Ollama 本地适配器（如 qwen2.5-1.5b），走 /api/chat 流式。"""

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen2.5-1.5b",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout

    def _payload(self, req: ChatRequest, stream: bool) -> dict:
        return {
            "model": req.model or self.default_model,
            "messages": [m.model_dump() for m in req.messages],
            "stream": stream,
            "options": {"temperature": req.temperature},
        }

    async def chat(self, req: ChatRequest) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=self._payload(req, False),
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=self._payload(req, True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = obj.get("message", {}).get("content")
                    if delta:
                        yield delta
                    if obj.get("done"):
                        break

    async def models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return [self.default_model]
                return [m["name"] for m in resp.json().get("models", [])]
            except httpx.HTTPError:
                return [self.default_model]

    async def available(self) -> bool:
        async with httpx.AsyncClient(timeout=3.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
            except httpx.HTTPError:
                return False

    def info(self) -> dict[str, object]:
        return {"name": self.name, "base_url": self.base_url, "default_model": self.default_model}
