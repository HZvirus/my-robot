from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .adapters import ChatRequest, MockAdapter
from .groups import build_adapters, get_adapter, resolve_group

logger = logging.getLogger("model_gateway")
router = APIRouter()


def _sse(delta: str) -> str:
    payload = json.dumps({"choices": [{"delta": {"content": delta}}]}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _stream(adapter, req: ChatRequest) -> AsyncIterator[str]:
    try:
        async for chunk in adapter.stream_chat(req):
            yield _sse(chunk)
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001 上游不可用则回退 mock
        logger.warning("上游适配器 %s 流式失败，回退 mock: %s", getattr(adapter, "name", "?"), exc)
        mock = build_adapters()["skeleton_mock"]
        async for chunk in mock.stream_chat(req):
            yield _sse(chunk)
    yield "data: [DONE]\n\n"


@router.post("/v1/chat")
async def chat(body: ChatRequest):
    group = resolve_group(body.scene)
    used, adapter = get_adapter(group)
    if body.stream:
        headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Model-Group": used,
        }
        return StreamingResponse(
            _stream(adapter, body),
            media_type="text/event-stream",
            headers=headers,
        )
    try:
        text = await adapter.chat(body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("上游适配器 %s 同步失败，回退 mock: %s", adapter.name, exc)
        text = await MockAdapter().chat(body)
    return {
        "model": used,
        "choices": [{"message": {"role": "assistant", "content": text}}],
    }


@router.get("/v1/models")
async def list_models() -> dict[str, Any]:
    adapters = build_adapters()
    data: list[dict[str, str]] = []
    for name, adapter in adapters.items():
        for m in await adapter.models():
            data.append({"id": m, "group": name, "adapter": adapter.name})
    return {"object": "list", "data": data}


async def health_extra() -> dict[str, Any]:
    adapters = build_adapters()
    info: dict[str, Any] = {}
    for name, adapter in adapters.items():
        info[name] = adapter.info()
    return {"adapters": info, "default_group": resolve_group(None)}
