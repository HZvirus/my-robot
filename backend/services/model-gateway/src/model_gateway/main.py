from __future__ import annotations

import os

from my_robot_common.app_factory import create_app
from my_robot_common.settings import get_settings

from .router import health_extra, router


def build_app():
    settings = get_settings()
    settings.service_name = os.getenv("SERVICE_NAME", "model-gateway")
    return create_app(
        settings,
        register_routers=lambda app: app.include_router(router),
        health_extra=health_extra,
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MODEL_GATEWAY_PORT", "8300"))
    uvicorn.run(app, host="0.0.0.0", port=port)
