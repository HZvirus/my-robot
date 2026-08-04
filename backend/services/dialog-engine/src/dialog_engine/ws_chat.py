from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from my_robot_common.auth import decode_token
from my_robot_common.ws import WSMessage

from .chat import run_chat
from .session import create_session

logger = logging.getLogger("dialog_engine.ws")
router = APIRouter()


@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    await ws.accept()
    token = ws.query_params.get("token")
    claims = None
    if token:
        try:
            claims = decode_token(token)
        except Exception:  # noqa: BLE001
            claims = None
    if claims is None:
        await ws.send_text(
            WSMessage.error("unauthorized", message="无效或缺失的 token").model_dump_json()
        )
        await ws.close(code=4401)
        return

    session = await create_session(claims.tenant_id, claims.scene, claims.sub)
    session_id = session["session_id"]

    async def send(msg: WSMessage) -> None:
        await ws.send_text(msg.model_dump_json())

    await send(
        WSMessage.status(
            "connected",
            session_id=session_id,
            scene=claims.scene,
        )
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send(WSMessage.error("invalid_json", message="消息必须是合法 JSON"))
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await send(WSMessage.status("pong", session_id=session_id))
                continue
            if mtype == "chat":
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                await run_chat(send, session, text)
            else:
                await send(
                    WSMessage.error("unknown_type", message=f"未知消息类型: {mtype}")
                )
    except WebSocketDisconnect:
        logger.info("WS 断开 session=%s", session_id)
        return
