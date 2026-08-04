from __future__ import annotations

from typing import Any

from .base import RobotDriver


class XiaomiDriver(RobotDriver):
    """小米/石头机器人驱动占位（不在骨架范围）。"""

    name = "xiaomi"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("小米真机驱动不在骨架范围内，仅占位")

    async def status(self) -> dict[str, Any]:
        raise NotImplementedError("小米真机驱动不在骨架范围内，仅占位")

    async def available(self) -> bool:
        return False
