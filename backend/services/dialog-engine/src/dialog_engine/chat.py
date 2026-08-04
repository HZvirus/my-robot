from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from my_robot_common.redis import get_redis
from my_robot_common.ws import WSMessage

from .actions import extract_action
from .gateway_client import stream_chat
from .rag_client import collect_context
from .safety import check_safety
from .scene_config import SceneConfig, load_scene_config
from .session import (
    SessionState,
    add_history,
    get_history,
    new_message_id,
    set_state,
)

logger = logging.getLogger("dialog_engine.chat")

WsSender = Callable[[WSMessage], Awaitable[None]]


async def enqueue_task(session: dict[str, str], action: dict[str, Any]) -> None:
    r = await get_redis()
    payload = json.dumps(
        {
            "id": action["id"],
            "type": action["type"],
            "params": action.get("params") or {},
            "tenant_id": session.get("tenant_id", "unknown"),
            "device_id": session.get("device_id", "mock-01"),
            "scene": session.get("scene"),
        },
        ensure_ascii=False,
    )
    await r.xadd("task:execute", {"payload": payload})


async def run_chat(
    send: WsSender,
    session: dict[str, str],
    text: str,
) -> None:
    session_id = session["session_id"]
    scene = session["scene"]
    scene_cfg: SceneConfig = load_scene_config(scene)

    await set_state(session_id, SessionState.PROCESSING)
    await send(WSMessage.status("processing", session_id=session_id))

    messages: list[dict] = [{"role": "system", "content": scene_cfg.system_prompt}]
    messages.extend(await get_history(session_id))
    messages.append({"role": "user", "content": text})

    if scene_cfg.rag_mode == "force" and scene_cfg.rag_collections:
        context = await collect_context(scene_cfg.rag_collections, text)
        if context:
            messages.insert(1, {"role": "system", "content": f"[知识库参考]\n{context}"})

    await set_state(session_id, SessionState.STREAMING)
    parts: list[str] = []
    try:
        async for delta in stream_chat(scene, messages):
            parts.append(delta)
            await send(WSMessage.token(delta, session_id=session_id))
    except Exception as exc:  # noqa: BLE001 model-gateway 不可用降级
        logger.warning("模型流式失败，降级纯文本: %s", exc)
        fallback = _fallback_text(scene_cfg, text)
        parts.append(fallback)
        await send(WSMessage.token(fallback, session_id=session_id))

    answer = "".join(parts).strip() or _fallback_text(scene_cfg, text)

    # 安全风控
    safety = check_safety(answer, scene_cfg.safety_policy)
    if safety:
        await send(
            WSMessage.status(
                "alert",
                session_id=session_id,
                event=safety["event"],
                hit=safety["hit"],
                message=safety["message"],
            )
        )

    # 动作提取 -> 下发任务流
    action = extract_action(answer)
    if action:
        await set_state(session_id, SessionState.AWAITING_TASK)
        await enqueue_task(session, action)
        await send(WSMessage.action(action, status="queued", session_id=session_id))

    message_id = new_message_id()
    await send(
        WSMessage.message(answer, message_id=message_id, session_id=session_id, scene=scene)
    )
    await add_history(session_id, "user", text)
    await add_history(session_id, "assistant", answer)
    await set_state(session_id, SessionState.AWAITING_INPUT)
    await send(WSMessage.status("awaiting_input", session_id=session_id))


def _fallback_text(scene_cfg: SceneConfig, user_text: str) -> str:
    if scene_cfg.name == "hospital":
        return "我是医院智能服务机器人，正在为您服务。请稍候，我将尽快回复。"
    return "爷爷，我在呢，刚刚没听清楚，您可以再说一遍吗？"
