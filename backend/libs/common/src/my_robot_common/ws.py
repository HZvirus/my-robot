from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WSMessageType = Literal["token", "message", "action", "status", "error"]


class WSMessage(BaseModel):
    """统一 WS 出站消息：{type, session_id?, payload}。"""

    type: WSMessageType
    session_id: str | None = None
    payload: Any = None

    @classmethod
    def status(cls, state: str, *, session_id: str | None = None, **extra: Any) -> "WSMessage":
        payload: dict[str, Any] = {"state": state}
        payload.update(extra)
        return cls(type="status", session_id=session_id, payload=payload)

    @classmethod
    def token(cls, delta: str, *, session_id: str | None = None) -> "WSMessage":
        return cls(type="token", session_id=session_id, payload={"delta": delta})

    @classmethod
    def message(
        cls,
        text: str,
        *,
        message_id: str,
        session_id: str | None = None,
        scene: str | None = None,
    ) -> "WSMessage":
        return cls(
            type="message",
            session_id=session_id,
            payload={"message_id": message_id, "text": text, "scene": scene},
        )

    @classmethod
    def action(
        cls,
        action: dict[str, Any],
        *,
        status: str = "queued",
        session_id: str | None = None,
    ) -> "WSMessage":
        payload = {
            "id": action.get("id"),
            "type": action.get("type"),
            "params": action.get("params") or {},
            "status": status,
        }
        return cls(type="action", session_id=session_id, payload=payload)

    @classmethod
    def error(cls, message: str, *, code: str = "error", session_id: str | None = None) -> "WSMessage":
        return cls(type="error", session_id=session_id, payload={"code": code, "message": message})


class ChatIn(BaseModel):
    """客户端入站聊天消息。"""

    type: Literal["chat"] = "chat"
    text: str
    session_id: str | None = Field(default=None)


class PingIn(BaseModel):
    type: Literal["ping"] = "ping"
