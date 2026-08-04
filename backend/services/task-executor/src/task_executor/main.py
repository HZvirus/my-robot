from __future__ import annotations

import os

from my_robot_common.app_factory import create_app
from my_robot_common.settings import get_settings

from .lifespan import health_extra, lifespan, register_routers


def build_app():
    settings = get_settings()
    settings.service_name = os.getenv("SERVICE_NAME", "task-executor")
    return create_app(
        settings,
        lifespan=lifespan,
        register_routers=register_routers,
        health_extra=health_extra,
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("TASK_EXECUTOR_PORT", "8500"))
    uvicorn.run(app, host="0.0.0.0", port=port)
