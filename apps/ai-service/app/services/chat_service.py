"""General chat service: stream LLM replies with conversation context."""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Conversation, Message
from app.models.chat import ChatConversationOut, ChatHistoryResponse, ChatMessageOut
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是我的机器人智能助手，一位乐于助人的中文 AI 助手。"
    "请用简洁、清晰、自然的语言回答用户的问题。"
)


class ChatService:
    def __init__(
        self,
        client: OllamaClient,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._client = client
        self._session_factory = session_factory

    async def stream_answer(
        self, message: str, conversation_id: str | None
    ) -> AsyncIterator[dict[str, Any]]:
        conv_id = conversation_id or str(uuid4())
        self._ensure_conversation(conv_id)
        history = self._load_history(conv_id)

        yield {"conversationId": conv_id}

        messages = self._build_messages(message, history)

        parts: list[str] = []
        completed = False
        try:
            async for token in self._client.chat_stream(messages):
                parts.append(token)
                yield {"delta": token}
            completed = True
        except asyncio.CancelledError:
            self._persist(conv_id, message, "".join(parts), interrupted=True)
            raise
        except Exception as exc:
            logger.exception("chat stream error conv=%s", conv_id)
            yield {"error": f"生成失败: {exc}"}
            self._persist(conv_id, message, "".join(parts), interrupted=True)
            return

        if completed:
            self._persist(conv_id, message, "".join(parts), interrupted=False)
            yield {"done": True}

    def _build_messages(
        self, message: str, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        msgs.extend(history[-settings.CHAT_MAX_HISTORY :] if history else [])
        msgs.append({"role": "user", "content": message})
        return msgs

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def _ensure_conversation(self, conv_id: str) -> None:
        with self._session_scope() as db:
            if db.get(Conversation, conv_id) is None:
                db.add(Conversation(id=conv_id))
                db.commit()

    def _load_history(self, conv_id: str) -> list[dict[str, str]]:
        with self._session_scope() as db:
            rows = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at.desc())
                    .limit(settings.CHAT_MAX_HISTORY)
                ).all()
            )
            rows.reverse()
            return [{"role": r.role, "content": r.content} for r in rows]

    def _persist(
        self,
        conv_id: str,
        user_message: str,
        assistant_text: str,
        interrupted: bool,
    ) -> None:
        with self._session_scope() as db:
            if db.get(Conversation, conv_id) is None:
                db.add(Conversation(id=conv_id))
            now = datetime.now(UTC).replace(tzinfo=None)
            db.add(
                Message(
                    id=str(uuid4()),
                    conversation_id=conv_id,
                    role="user",
                    content=user_message,
                    interrupted=False,
                    created_at=now,
                )
            )
            db.add(
                Message(
                    id=str(uuid4()),
                    conversation_id=conv_id,
                    role="assistant",
                    content=assistant_text,
                    interrupted=interrupted,
                    created_at=now + timedelta(microseconds=1),
                )
            )
            db.commit()

    def get_history(self, conversation_id: str) -> ChatHistoryResponse:
        with self._session_scope() as db:
            rows = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                ).all()
            )
            messages = [
                ChatMessageOut(
                    id=r.id,
                    role=r.role,
                    content=r.content,
                    interrupted=r.interrupted,
                    createdAt=r.created_at,
                )
                for r in rows
            ]
            return ChatHistoryResponse(conversationId=conversation_id, messages=messages)

    def list_conversations(self, limit: int = 50) -> list[ChatConversationOut]:
        with self._session_scope() as db:
            convs = list(
                db.scalars(
                    select(Conversation).order_by(Conversation.created_at.desc()).limit(limit)
                ).all()
            )
            out: list[ChatConversationOut] = []
            for c in convs:
                first = db.scalars(
                    select(Message)
                    .where(Message.conversation_id == c.id, Message.role == "user")
                    .order_by(Message.created_at.asc())
                    .limit(1)
                ).first()
                preview = first.content[:60] if first else ""
                out.append(
                    ChatConversationOut(id=c.id, createdAt=c.created_at, preview=preview)
                )
            return out


def _build_default_service() -> ChatService:
    from app.db.session import SessionLocal
    from app.services.ollama_client import ollama_client

    return ChatService(ollama_client, SessionLocal)


chat_service = _build_default_service()
