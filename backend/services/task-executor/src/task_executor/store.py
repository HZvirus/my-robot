from __future__ import annotations

import json
from typing import Any

from my_robot_common.redis import get_redis

# 任务状态存 Redis：key task:status:{id} -> {status, result, ts}
_STATUS_TTL = 3600


async def set_task_status(task_id: str, status: str, result: dict[str, Any] | None = None) -> None:
    r = await get_redis()
    payload = {"status": status, "result": result or {}}
    await r.set(f"task:status:{task_id}", json.dumps(payload, ensure_ascii=False), ex=_STATUS_TTL)


async def get_task_status(task_id: str) -> dict[str, Any] | None:
    r = await get_redis()
    raw = await r.get(f"task:status:{task_id}")
    if not raw:
        return None
    return json.loads(raw)
