from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from my_robot_common.db import close_db, create_tables, init_db

from .models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await create_tables(Base)
    # 延迟导入避免循环
    from .seed import seed_if_empty

    await seed_if_empty()
    yield
    await close_db()
