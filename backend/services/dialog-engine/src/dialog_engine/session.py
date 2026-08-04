from __future__ import annotations

import json
from enum import Enum
from uuid import uuid4

from my_robot_common.redis import get_redis

SESSION_TTL = 3600


class SessionState(str, Enum):
    IDLE = "idle"
    AWAITING_INPUT = "awaiting_input"
    PROCESSING = "processing"
    STREAMING = "streaming"
    AWAITING_TASK = "awaiting_task"


def new_session_id() -> str:
    return uuid4().hex


def new_message_id() -> str:
    return uuid4().hex


async def create_session(tenant_id: str, scene: str, user_id: str) -> dict[str, str]:
    session_id = new_session_id()
    r = await get_redis()
    key = f"session:{session_id}"
    await r.hset(
        key,
        mapping={
            "session_id": session_id,
            "tenant_id": tenant_id,
            "scene": scene,
            "user_id": user_id,
            "state": SessionState.AWAITING_INPUT.value,
            "history": "[]",
            "device_id": "mock-01",
        },
    )
    await r.expire(key, SESSION_TTL)
    return {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "scene": scene,
        "user_id": user_id,
        "device_id": "mock-01",
    }


async def get_session(session_id: str) -> dict | None:
    r = await get_redis()
    data = await r.hgetall(f"session:{session_id}")
    if not data:
        return None
    return data


async def set_state(session_id: str, state: SessionState) -> None:
    r = await get_redis()
    await r.hset(f"session:{session_id}", mapping={"state": state.value})


async def get_history(session_id: str) -> list[dict]:
    r = await get_redis()
    raw = await r.hget(f"session:{session_id}", "history")
    try:
        return json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []


async def add_history(session_id: str, role: str, content: str, limit: int = 10) -> None:
    r = await get_redis()
    key = f"session:{session_id}"
    raw = await r.hget(key, "history")
    items: list = []
    if raw:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            items = []
    items.append({"role": role, "content": content})
    items = items[-limit:]
    await r.hset(key, "history", json.dumps(items, ensure_ascii=False))
