"""Triage RAG service: retrieve | prompt | stream | persist.

Retrieval is scoped by the caller role (see app.core.rbac): only the
knowledge-base collections the role may see are queried, and a defense-in-depth
filter drops any chunk whose stored scope is outside the allowed set before it
is fed to the LLM. Isolation therefore does not depend on the prompt.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from uuid import uuid4

from anyio import to_thread
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.rbac import Principal, scopes_for
from app.db.models import Conversation, Message
from app.models.triage import (
    TriageConversationOut,
    TriageHistoryResponse,
    TriageMessageOut,
    TriageSource,
)
from app.services.departments import match_departments, resolve_primary
from app.services.embedding import EmbeddingService
from app.services.llm_client import OpenAICompatClient
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
        client: OpenAICompatClient,
        vector_store: VectorStoreProtocol,
        embedding: EmbeddingService,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._client = client
        self._vector_store = vector_store
        self._embedding = embedding
        self._session_factory = session_factory

    async def stream_answer(
        self,
        message: str,
        conversation_id: str | None,
        principal: Principal,
    ) -> AsyncIterator[dict[str, Any]]:
        conv_id = conversation_id or str(uuid4())
        try:
            await to_thread.run_sync(
                partial(self._ensure_conversation, conv_id, principal)
            )
        except PermissionError:
            yield {"error": "无权访问该会话"}
            return
        history = await to_thread.run_sync(self._load_history, conv_id)

        yield {"conversationId": conv_id}

        scopes = list(scopes_for(principal.role))
        try:
            query_embedding = await self._embedding.embed_one(message)
            retrieved = self._vector_store.query(
                query_embedding, scopes=scopes, n_results=settings.TRIAGE_TOP_K
            )
        except Exception as exc:
            logger.exception("triage retrieval error conv=%s", conv_id)
            await to_thread.run_sync(
                partial(self._persist, conv_id, principal, message, "", [], True)
            )
            yield {"error": f"检索失败: {exc}"}
            yield {"done": True}
            return

        # Defense in depth: the router already queried only allowed scopes,
        # but drop any chunk whose stored scope is outside the set before it
        # reaches the LLM. A mismatch indicates a routing bug and is logged.
        allowed = [
            r
            for r in retrieved
            if not r.get("metadata", {}).get("scope")
            or str(r.get("metadata", {}).get("scope")) in scopes
        ]
        if len(allowed) != len(retrieved):
            leaked = [
                str(r.get("metadata", {}).get("scope"))
                for r in retrieved
                if r.get("metadata", {}).get("scope")
                and str(r.get("metadata", {}).get("scope")) not in scopes
            ]
            logger.error(
                "scope leak blocked conv=%s scopes=%s leaked=%s",
                conv_id,
                scopes,
                leaked,
            )

        sources = [
            TriageSource(
                file=str(r.get("metadata", {}).get("file", "")),
                text=str(r.get("document", "")),
                scope=str(r.get("metadata", {}).get("scope", "")),
            )
            for r in allowed
        ]

        messages = self._build_messages(message, history, allowed)

        yield {"sources": [s.model_dump() for s in sources]}

        parts: list[str] = []
        completed = False
        try:
            async for token in self._client.chat_stream(messages):
                parts.append(token)
                yield {"delta": token}
            completed = True
        except asyncio.CancelledError:
            await to_thread.run_sync(
                partial(
                    self._persist,
                    conv_id,
                    principal,
                    message,
                    "".join(parts),
                    sources,
                    True,
                )
            )
            raise
        except Exception as exc:
            logger.exception("triage stream error conv=%s", conv_id)
            yield {"error": f"生成失败: {exc}"}
            await to_thread.run_sync(
                partial(
                    self._persist,
                    conv_id,
                    principal,
                    message,
                    "".join(parts),
                    sources,
                    True,
                )
            )
            return

        if completed:
            text = "".join(parts)
            await to_thread.run_sync(
                partial(
                    self._persist,
                    conv_id,
                    principal,
                    message,
                    text,
                    sources,
                    False,
                )
            )
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
        msgs.extend(history)
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

    def _ensure_conversation(self, conv_id: str, principal: Principal) -> None:
        with self._session_scope() as db:
            conv = db.get(Conversation, conv_id)
            if conv is None:
                db.add(
                    Conversation(
                        id=conv_id, owner_id=principal.user_id, role=principal.role
                    )
                )
                db.commit()
            elif conv.owner_id != principal.user_id:
                raise PermissionError(conv_id)
            elif conv.role is not None and conv.role != principal.role:
                raise PermissionError(conv_id)

    def ensure_access(self, conversation_id: str, principal: Principal) -> None:
        """Raise KeyError unless the conversation exists and belongs to the user.

        Foreign conversations look identical to missing ones so ids cannot be
        probed. A conversation created under a different role is also treated
        as inaccessible, forcing a fresh conversation on role change.
        """
        with self._session_scope() as db:
            conv = db.get(Conversation, conversation_id)
            if conv is None or conv.owner_id != principal.user_id:
                raise KeyError(conversation_id)
            if conv.role is not None and conv.role != principal.role:
                raise KeyError(conversation_id)

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
        principal: Principal,
        user_message: str,
        assistant_text: str,
        sources: list[TriageSource],
        interrupted: bool,
    ) -> None:
        with self._session_scope() as db:
            if db.get(Conversation, conv_id) is None:
                db.add(
                    Conversation(
                        id=conv_id, owner_id=principal.user_id, role=principal.role
                    )
                )
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

    def get_history(
        self, conversation_id: str, principal: Principal
    ) -> TriageHistoryResponse:
        self.ensure_access(conversation_id, principal)
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
            return TriageHistoryResponse(
                conversationId=conversation_id, messages=messages
            )

    def list_conversations(
        self, principal: Principal, limit: int = 50
    ) -> list[TriageConversationOut]:
        with self._session_scope() as db:
            convs = list(
                db.scalars(
                    select(Conversation)
                    .where(
                        Conversation.owner_id == principal.user_id,
                        or_(
                            Conversation.role.is_(None),
                            Conversation.role == principal.role,
                        ),
                    )
                    .order_by(Conversation.created_at.desc())
                    .limit(limit)
                ).all()
            )
            out: list[TriageConversationOut] = []
            for c in convs:
                first = db.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == c.id,
                        Message.role == "user",
                    )
                    .order_by(Message.created_at.asc())
                    .limit(1)
                ).first()
                preview = first.content[:60] if first else ""
                out.append(
                    TriageConversationOut(
                        id=c.id, createdAt=c.created_at, preview=preview
                    )
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
    from app.services.llm_client import llm_client
    from app.services.vector_store import get_vector_store

    return TriageService(llm_client, get_vector_store(), embedding_service, SessionLocal)


triage_service = _build_default_service()
