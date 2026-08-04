from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .base import ChatRequest, ModelAdapter


class OpenAICompatAdapter(ModelAdapter):
    """OpenAI 兼容适配器（DeepSeek / Qwen 云端等），SDK 可选，纯 httpx。

    base_url 为任意 OpenAI 兼容端点（如 https://api.deepseek.com/v1）。
    无 api_key 时 ``available()`` 返回 False，由网关回退到 mock。
    """

    name = "openai_compat"

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        default_model: str = "deepseek-chat",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _body(self, req: ChatRequest, stream: bool) -> dict:
        body: dict = {
            "model": req.model or self.default_model,
            "messages": [m.model_dump() for m in req.messages],
            "stream": stream,
            "temperature": req.temperature,
        }
        if req.max_tokens is not None:
            body["max_tokens"] = req.max_tokens
        return body

    async def chat(self, req: ChatRequest) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._body(req, False),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._body(req, True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta

    async def models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                if resp.status_code != 200:
                    return [self.default_model]
                return [m["id"] for m in resp.json().get("data", [])]
            except httpx.HTTPError:
                return [self.default_model]

    async def available(self) -> bool:
        return bool(self.api_key)

    def info(self) -> dict[str, object]:
        return {"name": self.name, "available": bool(self.api_key), "base_url": self.base_url}
