from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import close_db, init_db
from .exceptions import AppException
from .settings import Settings

Lifespan = Callable[[FastAPI], AsyncIterator[None]]
HealthExtra = Callable[[], Coroutine[Any, Any, dict[str, Any]]] | None


def create_app(
    settings: Settings,
    *,
    lifespan: Lifespan | None = None,
    register_routers: Callable[[FastAPI], None] | None = None,
    health_extra: HealthExtra = None,
) -> FastAPI:
    @asynccontextmanager
    async def _default_lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=settings.log_level.upper())
        await init_db()
        yield
        await close_db()

    app = FastAPI(
        title=settings.service_name,
        version="0.1.0",
        lifespan=lifespan or _default_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        base: dict[str, Any] = {"status": "ok", "service": settings.service_name}
        if health_extra is not None:
            try:
                base.update(await health_extra())
            except Exception as exc:  # noqa: BLE001
                base["health_error"] = str(exc)
        return base

    @app.exception_handler(AppException)
    async def _handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    if register_routers is not None:
        register_routers(app)

    return app
