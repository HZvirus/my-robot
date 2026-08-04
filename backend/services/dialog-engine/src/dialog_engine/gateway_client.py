from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from my_robot_common.settings import get_settings


async def stream_chat(scene: str, messages: list[dict]) -> AsyncIterator[str]:
    """调用 model-gateway 的 SSE 流式接口，逐 delta 产出文本。"""
    settings = get_settings()
    url = f"{settings.model_gateway_url}/v1/chat"
    body = {
        "messages": messages,
        "stream": True,
        "scene": scene,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta
