from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from my_robot_common.db import close_db, create_tables, init_db

from .db import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await create_tables(Base)
    yield
    await close_db()


def register_routers(app: FastAPI) -> None:
    from .feedback_routes import router as feedback_router
    from .ws_chat import router as ws_router

    app.include_router(feedback_router)
    app.include_router(ws_router)


async def health_extra() -> dict:
    from .scene_config import available_scenes
    from my_robot_skills import list_skills

    return {
        "scenes": list(available_scenes()),
        "skills": [s.name for s in list_skills()],
        "endpoints": ["/ws/chat", "/api/feedback"],
    }
