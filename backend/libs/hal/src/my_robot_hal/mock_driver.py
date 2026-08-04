from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import RobotDriver

logger = logging.getLogger("hal.mock")


class MockDriver(RobotDriver):
    """离线 mock 驱动：仅记录日志，模拟硬件延迟。"""

    name = "mock"

    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        action_type = action.get("type")
        params = action.get("params") or {}
        logger.info("[mock-robot] 收到动作 type=%s params=%s", action_type, params)
        await asyncio.sleep(0.05)
        result: dict[str, Any] = {
            "ok": True,
            "driver": self.name,
            "action": action_type,
            "params": params,
            "output": f"mock-executed-{action_type}",
        }
        logger.info("[mock-robot] 执行结果 %s", result)
        return result

    async def status(self) -> dict[str, Any]:
        return {"driver": self.name, "online": True, "battery": 88, "pose": [0.0, 0.0, 0.0]}
