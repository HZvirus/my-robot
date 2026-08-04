from __future__ import annotations

import httpx

from my_robot_common.settings import get_settings


async def retrieve(collection: str, query: str, top_k: int = 3) -> list[dict]:
    """调用 rag-engine 检索接口，返回结果列表。失败时返回空。"""
    settings = get_settings()
    url = f"{settings.rag_engine_url}/retrieve"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, json={"collection": collection, "query": query, "top_k": top_k}
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
    except (httpx.HTTPError, ValueError):
        return []


async def collect_context(collections: list[str], query: str, top_k: int = 2) -> str:
    """跨多个集合检索并拼接上下文。"""
    parts: list[str] = []
    for col in collections:
        results = await retrieve(col, query, top_k=top_k)
        for r in results:
            text = r.get("text", "").strip()
            if text:
                parts.append(f"[{col}] {text}")
    return "\n".join(parts)
