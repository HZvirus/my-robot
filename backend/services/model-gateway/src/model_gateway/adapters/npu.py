from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import ChatRequest, ModelAdapter


class NPUAdapter(ModelAdapter):
    """端侧 NPU（RKNN）适配器占位：不在骨架范围，仅保留接口。"""

    name = "npu"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.model_path = kwargs.get("model_path", "rknn-vlm-local")

    async def chat(self, req: ChatRequest) -> str:
        raise NotImplementedError("端侧 NPU 推理（RKNN）不在骨架范围内，仅占位")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[str]:
        raise NotImplementedError("端侧 NPU 推理（RKNN）不在骨架范围内，仅占位")
        yield ""  # pragma: no cover

    async def models(self) -> list[str]:
        return [self.model_path]

    async def available(self) -> bool:
        return False

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "available": False, "model_path": self.model_path}
