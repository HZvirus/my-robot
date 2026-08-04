from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RobotDriver(ABC):
    """机器人驱动抽象基类。

    既有语义化方法（move_forward/rotate/speak/play_media/stop），也提供通用
    ``execute(action)`` 派发入口，便于 Task Executor 直接转发动作 schema。
    """

    name: str = "base"

    # ---- 语义化方法（转发到 execute）----
    async def move_forward(self, **params: Any) -> dict[str, Any]:
        return await self.execute({"type": "move_forward", "params": params})

    async def move_backward(self, **params: Any) -> dict[str, Any]:
        return await self.execute({"type": "move_backward", "params": params})

    async def rotate(self, **params: Any) -> dict[str, Any]:
        return await self.execute({"type": "rotate", "params": params})

    async def speak(self, **params: Any) -> dict[str, Any]:
        return await self.execute({"type": "speak", "params": params})

    async def play_media(self, **params: Any) -> dict[str, Any]:
        return await self.execute({"type": "play_media", "params": params})

    async def stop(self, **params: Any) -> dict[str, Any]:
        return await self.execute({"type": "stop", "params": params})

    # ---- 子类必须实现 ----
    @abstractmethod
    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """执行动作 {type, params}，返回结果 dict。"""
        raise NotImplementedError

    @abstractmethod
    async def status(self) -> dict[str, Any]:
        """返回驱动/设备状态。"""
        raise NotImplementedError

    async def available(self) -> bool:
        return True
