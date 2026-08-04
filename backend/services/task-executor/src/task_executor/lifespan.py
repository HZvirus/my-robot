from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from my_robot_common.settings import get_settings

from .router import router
from .worker import start_background

logger = logging.getLogger("task_executor")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await start_background(app)
    logger.info("task-executor 后台 worker 已启动")
    try:
        yield
    finally:
        cancel = getattr(app.state, "task_cancel", None)
        if cancel is not None:
            await cancel()


def register_routers(app: FastAPI) -> None:
    app.include_router(router)


async def health_extra() -> dict:
    settings = get_settings()
    return {
        "mqtt_broker": f"{settings.emqx_host}:{settings.emqx_port}",
        "stream": "task:execute",
        "consumer_group": "task-executors",
    }


# 防止 asyncio 未使用告警
_ = asyncio
