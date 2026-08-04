from __future__ import annotations

import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select  # noqa: F401  保留以便扩展

from my_robot_common.redis import get_redis
from my_robot_common.exceptions import AppException

from .store import get_task_status

router = APIRouter()


class TaskCreateIn(BaseModel):
    type: str
    params: dict = {}
    tenant_id: str | None = None
    device_id: str | None = None
    scene: str | None = None


@router.post("/tasks", status_code=202)
async def create_task(body: TaskCreateIn) -> dict:
    task_id = uuid4().hex
    payload = json.dumps(
        {
            "id": task_id,
            "type": body.type,
            "params": body.params,
            "tenant_id": body.tenant_id or "unknown",
            "device_id": body.device_id or "mock-01",
            "scene": body.scene,
        },
        ensure_ascii=False,
    )
    r = await get_redis()
    await r.xadd("task:execute", {"payload": payload})
    await _set_pending(task_id)
    return {"id": task_id, "status": "pending", "queued": True}


async def _set_pending(task_id: str) -> None:
    from .store import set_task_status

    await set_task_status(task_id, "pending")


@router.get("/tasks/{task_id}")
async def task_status(task_id: str) -> dict:
    status = await get_task_status(task_id)
    if status is None:
        raise AppException(404, "task_not_found", "任务不存在或已过期")
    return {"id": task_id, **status}
