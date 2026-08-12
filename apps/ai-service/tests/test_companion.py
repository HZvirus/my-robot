import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models as db_models  # noqa: F401 - register ORM models
from app.db.session import Base
from app.services.companion_service import CompanionService


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


class FakeOllamaClient:
    def __init__(self, deltas: list[str]) -> None:
        self.deltas = deltas
        self.chat_calls: list[list[dict[str, str]]] = []

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.chat_calls.append(messages)
        for delta in self.deltas:
            yield delta


class CancellingClient(FakeOllamaClient):
    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.chat_calls.append(messages)
        yield "部分"
        raise asyncio.CancelledError


class FailingClient:
    def __init__(self) -> None:
        self.chat_calls: list[list[dict[str, str]]] = []

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.chat_calls.append(messages)
        raise RuntimeError("boom")
        yield  # pragma: no cover - marks this as an async generator


def _make_service(
    client: FakeOllamaClient, session_factory: sessionmaker[Session]
) -> CompanionService:
    return CompanionService(client, session_factory)


async def test_stream_answer_event_sequence_and_persist(session_factory) -> None:
    service = _make_service(FakeOllamaClient(deltas=["别", "担心"]), session_factory)
    events = [event async for event in service.stream_answer("最近压力好大", None)]

    assert "conversationId" in events[0]
    assert [e for e in events if "delta" in e] == [{"delta": "别"}, {"delta": "担心"}]
    assert events[-1] == {"done": True}

    history = service.get_history(events[0]["conversationId"])
    assert [m.role for m in history.messages] == ["user", "assistant"]
    assert history.messages[0].content == "最近压力好大"
    assert history.messages[1].content == "别担心"
    assert history.messages[1].interrupted is False


async def test_stream_answer_uses_companion_system_prompt(session_factory) -> None:
    client = FakeOllamaClient(deltas=["我在"])
    service = _make_service(client, session_factory)
    async for _ in service.stream_answer("你好", None):
        pass

    assert client.chat_calls[0][0]["role"] == "system"
    assert "健康陪伴" in client.chat_calls[0][0]["content"]


async def test_stream_answer_includes_history(session_factory) -> None:
    client = FakeOllamaClient(deltas=["好的"])
    service = _make_service(client, session_factory)
    conv_id = "conv-1"
    async for _ in service.stream_answer("第一次", conv_id):
        pass
    async for _ in service.stream_answer("第二次", conv_id):
        pass

    assert len(client.chat_calls) == 2
    roles = [m["role"] for m in client.chat_calls[1]]
    assert roles == ["system", "user", "assistant", "user"]
    assert client.chat_calls[1][-1]["content"] == "第二次"
    assert client.chat_calls[1][-2]["content"] == "好的"


async def test_stream_answer_cancel_persists_partial(session_factory) -> None:
    service = _make_service(CancellingClient(deltas=[]), session_factory)
    events: list[dict[str, object]] = []
    with pytest.raises(asyncio.CancelledError):
        async for event in service.stream_answer("陪我聊聊", None):
            events.append(event)

    conv_id = events[0]["conversationId"]
    history = service.get_history(conv_id)
    assert len(history.messages) == 2
    assert history.messages[1].content == "部分"
    assert history.messages[1].interrupted is True


async def test_stream_answer_error_yields_error(session_factory) -> None:
    service = _make_service(FailingClient(), session_factory)
    events = [event async for event in service.stream_answer("在吗", None)]

    assert any("error" in e for e in events)
    assert not any("done" in e for e in events)
    history = service.get_history(events[0]["conversationId"])
    assert history.messages[1].interrupted is True


async def test_list_conversations_returns_preview(session_factory) -> None:
    client = FakeOllamaClient(deltas=["加油"])
    service = _make_service(client, session_factory)
    async for _ in service.stream_answer("今天不想起床", None):
        pass

    convs = service.list_conversations()
    assert len(convs) == 1
    assert convs[0].preview == "今天不想起床"
