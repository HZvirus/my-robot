'''Science service: stream plain-text popular-science chat with conversation context.'''

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from uuid import uuid4

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Conversation, Message
from app.models.science import (
    ScienceConversationOut,
    ScienceHistoryResponse,
    ScienceMessageOut,
)
from app.services.llm_client import OpenAICompatClient
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    '你是「小科」，一位知识面广、耐心细致的科普百科助手，面向普通用户做通俗易懂的科普讲解。'
    '要求：'
    '- 语言平实易懂，优先用生活化的比喻和例子解释复杂概念，避免堆砌专业术语。'
    '- 涉及具体数据、原理或历史时尽量准确；不确定或存在争议的内容要如实说明，不编造。'
    '- 回答结构清晰，可适当使用分点或小标题帮助理解，但篇幅以说清楚为准。'
    '- 涉及医学、健康、用药等话题时，明确提示仅作科普参考，不替代专业诊疗，必要时建议咨询医生。'
    '- 引导孩子式的好奇心，鼓励追问，不嘲笑任何问题。'
)


def _cosine_similarity(a: list[float], b: list[float]):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


class ScienceService:
    def __init__(
        self,
        client: OpenAICompatClient,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._client = client
        self._session_factory = session_factory

    async def stream_answer(
        self, message: str, conversation_id: str | None, owner_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        conv_id = conversation_id or str(uuid4())
        history: list[dict[str, str]] = []
        if conversation_id:
            history = await to_thread.run_sync(self._load_history, conversation_id)
            try:
                # Topic-drift detection: start a fresh conversation when the new
                # message is semantically unrelated to the recent context.
                if await self._is_new_topic(message, history):
                    conv_id = str(uuid4())
                    history = []
            except Exception:
                logger.warning(
                    'topic detection failed, keep current conversation',
                    exc_info=True,
                )

        try:
            await to_thread.run_sync(partial(self._ensure_conversation, conv_id, owner_id))
        except PermissionError:
            yield {'error': '无权访问该会话'}
            return
        if not history:
            history = await to_thread.run_sync(self._load_history, conv_id)

        yield {'conversationId': conv_id}

        messages = self._build_messages(message, history)

        parts: list[str] = []
        completed = False
        try:
            async for token in self._client.chat_stream(messages):
                parts.append(token)
                yield {'delta': token}
            completed = True
        except asyncio.CancelledError:
            await to_thread.run_sync(
                partial(self._persist, conv_id, message, ''.join(parts), True)
            )
            raise
        except Exception as exc:
            logger.exception('science stream error conv=%s', conv_id)
            yield {'error': f'生成失败: {exc}'}
            await to_thread.run_sync(
                partial(self._persist, conv_id, message, ''.join(parts), True)
            )
            return

        if completed:
            await to_thread.run_sync(
                partial(self._persist, conv_id, message, ''.join(parts), False)
            )
            yield {'done': True}

    async def _load_topic_vector(self, history: list[dict[str, str]]):
        # Weighted topic centroid: user messages carry more intent than assistant
        # replies, and more recent messages decay less.
        recent = [m for m in history[-settings.SCIENCE_TOPIC_WINDOW:]]
        if not recent:
            return None
        vectors = await embedding_service.embed([m['content'] for m in recent])
        if not vectors:
            return None
        n, dim = len(vectors), len(vectors[0])
        topic = [0.0] * dim
        total = 0.0
        for i, v in enumerate(vectors):
            role_w = settings.SCIENCE_TOPIC_USER_WEIGHT if recent[i]['role'] == 'user' else (1.0 - settings.SCIENCE_TOPIC_USER_WEIGHT)
            decay = settings.SCIENCE_TOPIC_DECAY ** (n - 1 - i)
            w = role_w * decay
            total += w
            for d in range(dim):
                topic[d] += v[d] * w
        return [x / total for x in topic]

    async def _is_new_topic(self, message: str, history: list[dict[str, str]]):
        # True when the message drifts away from the conversation topic.
        topic = await self._load_topic_vector(history)
        if topic is None:
            return False
        vec = await embedding_service.embed_one(message)
        sim = _cosine_similarity(vec, topic)
        logger.info(
            'science topic sim=%.3f new_topic=%s',
            sim,
            sim < settings.SCIENCE_TOPIC_SIM_THRESHOLD,
        )
        return sim < settings.SCIENCE_TOPIC_SIM_THRESHOLD

    def _build_messages(
        self, message: str, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        msgs.extend(history)
        msgs.append({'role': 'user', 'content': message})
        return msgs

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def _ensure_conversation(self, conv_id: str, owner_id: str) -> None:
        with self._session_scope() as db:
            conv = db.get(Conversation, conv_id)
            if conv is None:
                db.add(Conversation(id=conv_id, owner_id=owner_id))
                db.commit()
            elif conv.owner_id != owner_id:
                raise PermissionError(conv_id)

    def ensure_access(self, conversation_id: str, owner_id: str) -> None:
        '''Raise KeyError unless the conversation exists and belongs to the user.

        Foreign conversations look identical to missing ones so ids cannot be probed.
        '''
        with self._session_scope() as db:
            conv = db.get(Conversation, conversation_id)
            if conv is None or conv.owner_id != owner_id:
                raise KeyError(conversation_id)

    def _load_history(self, conv_id: str) -> list[dict[str, str]]:
        with self._session_scope() as db:
            rows = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at.desc())
                    .limit(settings.SCIENCE_MAX_HISTORY)
                ).all()
            )
            rows.reverse()
            return [{'role': r.role, 'content': r.content} for r in rows]

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
                    role='user',
                    content=user_message,
                    interrupted=False,
                    created_at=now,
                )
            )
            db.add(
                Message(
                    id=str(uuid4()),
                    conversation_id=conv_id,
                    role='assistant',
                    content=assistant_text,
                    interrupted=interrupted,
                    created_at=now + timedelta(microseconds=1),
                )
            )
            db.commit()

    def get_history(self, conversation_id: str, owner_id: str) -> ScienceHistoryResponse:
        self.ensure_access(conversation_id, owner_id)
        with self._session_scope() as db:
            rows = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                ).all()
            )
            messages = [
                ScienceMessageOut(
                    id=r.id,
                    role=r.role,
                    content=r.content,
                    interrupted=r.interrupted,
                    createdAt=r.created_at,
                )
                for r in rows
            ]
            return ScienceHistoryResponse(
                conversationId=conversation_id, messages=messages
            )

    def list_conversations(self, owner_id: str, limit: int = 50) -> list[ScienceConversationOut]:
        with self._session_scope() as db:
            convs = list(
                db.scalars(
                    select(Conversation)
                    .where(Conversation.owner_id == owner_id)
                    .order_by(Conversation.created_at.desc())
                    .limit(limit)
                ).all()
            )
            out: list[ScienceConversationOut] = []
            for c in convs:
                first = db.scalars(
                    select(Message)
                    .where(Message.conversation_id == c.id, Message.role == 'user')
                    .order_by(Message.created_at.asc())
                    .limit(1)
                ).first()
                preview = first.content[:60] if first else ''
                out.append(
                    ScienceConversationOut(id=c.id, createdAt=c.created_at, preview=preview)
                )
            return out


def _build_default_service() -> ScienceService:
    from app.db.session import SessionLocal
    from app.services.llm_client import llm_client

    return ScienceService(llm_client, SessionLocal)


science_service = _build_default_service()
