from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from my_robot_common.redis import get_redis
from my_robot_hal import default_driver, get_driver

from .mqtt import publish_command, subscribe_state_forever
from .store import set_task_status

logger = logging.getLogger("task_executor.worker")

STREAM = "task:execute"
GROUP = "task-executors"

# 未知动作类型时降级为 speak，保证链路可见
FALLBACK_ACTION_TYPE = "speak"


async def _ensure_group() -> None:
    r = await get_redis()
    try:
        await r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as exc:  # noqa: BLE001 已存在组会报错，忽略
        if "BUSYGROUP" not in str(exc):
            logger.debug("xgroup_create: %s", exc)


async def handle_task(message_id: str, payload: dict[str, Any]) -> None:
    task_id = payload.get("id") or message_id
    action_type = payload.get("type") or FALLBACK_ACTION_TYPE
    params = payload.get("params") or {}
    tenant_id = payload.get("tenant_id", "unknown")
    device_id = payload.get("device_id", "mock-01")
    driver_name = params.pop("driver", "mock") if isinstance(params, dict) else "mock"

    await set_task_status(task_id, "processing")
    try:
        try:
            driver = get_driver(driver_name)
        except KeyError:
            driver = default_driver()
        result = await driver.execute({"type": action_type, "params": params})
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": str(exc)}
        logger.exception("动作执行失败 task=%s", task_id)

    await set_task_status(task_id, "done", result)
    await publish_command(
        tenant_id,
        device_id,
        task_id,
        {"type": action_type, "params": params},
        result,
    )


async def worker_loop(stop_event: asyncio.Event | None = None) -> None:
    await _ensure_group()
    r = await get_redis()
    consumer = os.getenv("HOSTNAME", "worker-1")
    logger.info("task-executor worker 启动，consumer=%s", consumer)
    while stop_event is None or not stop_event.is_set():
        try:
            resp = await r.xreadgroup(
                GROUP, consumer, {STREAM: ">"}, count=1, block=5000
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("xreadgroup 异常: %s", exc)
            await asyncio.sleep(1)
            continue
        if not resp:
            continue
        for _stream, entries in resp:
            for message_id, fields in entries:
                raw = fields.get("payload", "{}")
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError:
                    payload = {}
                await handle_task(message_id, payload)
                await r.xack(STREAM, GROUP, message_id)


async def start_background(app=None) -> asyncio.Task:
    """启动 worker + 状态订阅后台任务。"""
    worker_task = asyncio.create_task(worker_loop(), name="task-worker")
    state_task = asyncio.create_task(subscribe_state_forever(), name="task-state-sub")

    async def _cancel():
        worker_task.cancel()
        state_task.cancel()

    if app is not None:
        app.state.task_worker = worker_task
        app.state.task_state_sub = state_task
        app.state.task_cancel = _cancel
    return worker_task
