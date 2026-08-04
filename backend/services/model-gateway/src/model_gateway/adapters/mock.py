from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .base import ChatRequest, ModelAdapter

HOSPITAL_INTRO = (
    "您好，我是医院智能服务机器人。"
    "可以为您查询科室、提醒查房、说明用药与医保政策。请问有什么可以帮您？"
)
HOME_INTRO = (
    "爷爷您好呀，我是家庭照护小助手。"
    "想听听天气、放点音乐，或者开灯关灯都可以告诉我。"
)

# 触发词 -> 结构化动作（由 dialog-engine 解析 JSON 后下发 Task Executor）
TRIGGER_ACTIONS: dict[str, dict] = {
    "天气": {"type": "weather_broadcast", "params": {"city": "深圳", "text": "今天多云转晴，26~32℃。"}},
    "查房": {"type": "dept_round", "params": {"target_dept": "骨科病房"}},
    "开灯": {"type": "home_light", "params": {"device": "客厅灯", "action": "on"}},
    "关灯": {"type": "home_light", "params": {"device": "客厅灯", "action": "off"}},
    "音乐": {"type": "play_media", "params": {"media": "舒缓钢琴曲", "duration_sec": 300}},
}


def _chunks(text: str, size: int = 2) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [text]


def _build_full_text(req: ChatRequest) -> str:
    scene = req.scene or "home"
    intro = HOSPITAL_INTRO if scene == "hospital" else HOME_INTRO
    user_text = " ".join(m.content for m in req.messages if m.role == "user")
    full = intro
    for trigger, action in TRIGGER_ACTIONS.items():
        if trigger in user_text:
            full += "\n\n```json\n" + json.dumps(action, ensure_ascii=False) + "\n```"
            break
    return full


class MockAdapter(ModelAdapter):
    """离线 mock：真异步 SSE 流式，按字符块推送。"""

    name = "mock"

    def __init__(self, delay: float = 0.03) -> None:
        self.delay = delay

    async def chat(self, req: ChatRequest) -> str:
        return _build_full_text(req)

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[str]:
        full = _build_full_text(req)
        for chunk in _chunks(full, size=2):
            yield chunk
            await asyncio.sleep(self.delay)

    async def models(self) -> list[str]:
        return ["skeleton-mock"]

    async def available(self) -> bool:
        return True

    def info(self) -> dict[str, str]:
        return {"name": self.name, "available": True}
