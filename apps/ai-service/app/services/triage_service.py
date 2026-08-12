"""Triage RAG service: retrieve -> prompt -> stream -> persist."""

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
from app.models.triage import (
    TriageConversationOut,
    TriageHistoryResponse,
    TriageMessageOut,
    TriageSource,
)
from app.services.departments import match_departments, resolve_primary
from app.services.embedding import EmbeddingService
from app.services.ollama_client import OllamaClient
from app.services.vector_store import VectorStoreProtocol

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是医院的智能导诊助手。请仅依据下方提供的医院资料回答用户问题，并推荐合适的就诊科室。\n"
    "\n"
    "要求：\n"
    "- 不得下诊断、不得开处方、不得给出具体用药剂量。\n"
    "- 若提供的资料不足以回答，请明确说明，并建议前往导诊台咨询或拨打医院咨询电话。\n"
    "- 回答需简洁、贴近患者用语，可在末尾用 [1]、[2] 等标注引用的资料编号。\n"
    "\n"
    "【医院资料】\n"
    "{context}"
)

CONTEXT_BUDGET = 4000


class TriageService:
    def __init__(
        self,
        client: OllamaClient,
        vector_store: VectorStoreProtocol,
        embedding: EmbeddingService,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._client = client
        self._vector_store = vector_store
        self._embedding = embedding
        self._session_factory = session_factory

    async def stream_answer(
        self, message: str, conversation_id: str | None
    ) -> AsyncIterator[dict[str, Any]]:
        conv_id = conversation_id or str(uuid4())
        self._ensure_conversation(conv_id)
        history = self._load_history(conv_id)

        yield {"conversationId": conv_id}

        try:
            query_embedding = await self._embedding.embed_one(message)
            retrieved = self._vector_store.query(
                query_embedding, n_results=settings.TRIAGE_TOP_K
            )
        except Exception as exc:
            logger.exception("triage retrieval error conv=%s", conv_id)
            self._persist(conv_id, message, "", [], interrupted=True)
            yield {"error": f"检索失败: {exc}"}
            yield {"done": True}
            return

        sources = [
            TriageSource(
                file=str(r.get("metadata", {}).get("file", "")),
                text=str(r.get("document", "")),
            )
            for r in retrieved
        ]

        messages = self._build_messages(message, history, retrieved)

        yield {"sources": [s.model_dump() for s in sources]}

        parts: list[str] = []
        completed = False
        try:
            async for token in self._client.chat_stream(messages):
                parts.append(token)
                yield {"delta": token}
            completed = True
        except asyncio.CancelledError:
            self._persist(conv_id, message, "".join(parts), sources, interrupted=True)
            raise
        except Exception as exc:
            logger.exception("triage stream error conv=%s", conv_id)
            yield {"error": f"生成失败: {exc}"}
            self._persist(conv_id, message, "".join(parts), sources, interrupted=True)
            return

        if completed:
            text = "".join(parts)
            self._persist(conv_id, message, text, sources, interrupted=False)
            primary = resolve_primary(text)
            matched = match_departments(text)
            yield {
                "department": primary.to_dict() if primary else None,
                "matchedDepartments": [d.to_dict() for d in matched],
            }
            yield {"done": True}

    def _build_messages(
        self,
        message: str,
        history: list[dict[str, str]],
        retrieved: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        context = self._format_context(retrieved)
        system = SYSTEM_PROMPT.format(context=context)
        msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
        msgs.extend(history[-settings.TRIAGE_MAX_HISTORY :] if history else [])
        msgs.append({"role": "user", "content": message})
        return msgs

    @staticmethod
    def _format_context(retrieved: list[dict[str, Any]]) -> str:
        if not retrieved:
            return "（暂无资料）"
        blocks: list[str] = []
        total = 0
        for i, r in enumerate(retrieved, start=1):
            text = str(r.get("document", "")).strip()
            if not text:
                continue
            remaining = CONTEXT_BUDGET - total
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = text[:remaining]
            blocks.append(f"[{i}] {text}")
            total += len(text) + 6
        return "\n\n".join(blocks) if blocks else "（暂无资料）"

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
                    .limit(settings.TRIAGE_MAX_HISTORY)
                ).all()
            )
            rows.reverse()
            return [{"role": r.role, "content": r.content} for r in rows]

    def _persist(
        self,
        conv_id: str,
        user_message: str,
        assistant_text: str,
        sources: list[TriageSource],
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
                    sources=[s.model_dump() for s in sources] or None,
                    interrupted=interrupted,
                    created_at=now + timedelta(microseconds=1),
                )
            )
            db.commit()

    def get_history(self, conversation_id: str) -> TriageHistoryResponse:
        with self._session_scope() as db:
            rows = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                ).all()
            )
            messages = [
                TriageMessageOut(
                    id=r.id,
                    role=r.role,
                    content=r.content,
                    sources=self._to_sources(r.sources),
                    interrupted=r.interrupted,
                    createdAt=r.created_at,
                )
                for r in rows
            ]
            return TriageHistoryResponse(conversationId=conversation_id, messages=messages)

    def list_conversations(self, limit: int = 50) -> list[TriageConversationOut]:
        with self._session_scope() as db:
            convs = list(
                db.scalars(
                    select(Conversation).order_by(Conversation.created_at.desc()).limit(limit)
                ).all()
            )
            out: list[TriageConversationOut] = []
            for c in convs:
                first = db.scalars(
                    select(Message)
                    .where(Message.conversation_id == c.id, Message.role == "user")
                    .order_by(Message.created_at.asc())
                    .limit(1)
                ).first()
                preview = first.content[:60] if first else ""
                out.append(
                    TriageConversationOut(id=c.id, createdAt=c.created_at, preview=preview)
                )
            return out

    @staticmethod
    def _to_sources(raw: list[dict[str, Any]] | None) -> list[TriageSource] | None:
        if not raw:
            return None
        return [TriageSource(**item) for item in raw]


def _build_default_service() -> TriageService:
    from app.db.session import SessionLocal
    from app.services.embedding import embedding_service
    from app.services.ollama_client import ollama_client
    from app.services.vector_store import get_vector_store

    return TriageService(ollama_client, get_vector_store(), embedding_service, SessionLocal)


triage_service = _build_default_service()
