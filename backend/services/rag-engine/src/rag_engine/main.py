from __future__ import annotations

import os

from my_robot_common.app_factory import create_app
from my_robot_common.settings import get_settings

from .lifespan import lifespan, register_routers
from .router import health_extra


def build_app():
    settings = get_settings()
    settings.service_name = os.getenv("SERVICE_NAME", "rag-engine")
    return create_app(
        settings,
        lifespan=lifespan,
        register_routers=register_routers,
        health_extra=health_extra,
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("RAG_ENGINE_PORT", "8400"))
    uvicorn.run(app, host="0.0.0.0", port=port)
