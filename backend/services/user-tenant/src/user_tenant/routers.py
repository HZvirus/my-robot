from __future__ import annotations

from fastapi import FastAPI

from .auth_routes import router as auth_router
from .tenant_routes import router as tenant_router
from .user_routes import router as user_router


def register_routers(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(tenant_router)
