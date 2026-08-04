from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from my_robot_common.db import close_db, create_tables, enable_pgvector, init_db

from .db import Base
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    try:
        await enable_pgvector()
    except Exception as exc:  # noqa: BLE001 数据库无权限时仅告警
        app.state.logger_warning = str(exc)
    await create_tables(Base)
    from .seed import seed_if_empty

    await seed_if_empty()
    yield
    await close_db()


def register_routers(app: FastAPI) -> None:
    app.include_router(router)
