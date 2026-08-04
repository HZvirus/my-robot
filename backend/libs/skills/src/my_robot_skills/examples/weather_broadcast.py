from __future__ import annotations

from typing import Any

from ..registry import skill


@skill(
    name="weather_broadcast",
    description="播报天气（stub）",
    args_schema={"city": "string"},
)
async def weather_broadcast(args: dict[str, Any]) -> dict[str, Any]:
    city = args.get("city", "深圳")
    return {
        "ok": True,
        "city": city,
        "text": f"{city}今天多云转晴，26~32℃，建议开空调保持舒适。",
        "note": "骨架 stub 返回示例天气，未接入真实天气服务",
    }
