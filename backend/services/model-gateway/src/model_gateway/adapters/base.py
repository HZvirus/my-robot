from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int | None = None
    scene: str | None = None


class ModelAdapter:
    """适配器基类（非 ABC，便于 npu 占位不实例化）。"""

    name: str = "base"

    async def chat(self, req: ChatRequest) -> str:
        raise NotImplementedError

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""  # pragma: no cover  (类型为 async generator)

    async def models(self) -> list[str]:
        return []

    async def available(self) -> bool:
        return True

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "available": True}
