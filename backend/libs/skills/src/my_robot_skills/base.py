from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class Skill:
    """技能定义：name / description / args_schema / handler。"""

    name: str
    description: str
    handler: Handler
    args_schema: dict[str, Any] = field(default_factory=dict)

    async def run(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.handler(args or {})
