import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rbac import Principal
from app.db import models as db_models  # noqa: F401 - register ORM models
from app.db.session import Base
from app.services.departments import (
    match_departments,
    resolve_primary,
)
from app.services.embedding import EmbeddingService
from app.services.text_splitter import split_text
from app.services.triage_service import TriageService


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


PATIENT = Principal(user_id="user-1", role="patient")
DOCTOR = Principal(user_id="user-1", role="doctor")


class FakeOllamaClient:
    def __init__(self, deltas: list[str]) -> None:
        self.deltas = deltas
        self.chat_calls: list[list[dict[str, str]]] = []
        self._embed_calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._embed_calls += 1
        dim = 8
        return [
            [float(i + self._embed_calls * 100 + j) for j in range(dim)]
            for i in range(len(texts))
        ]

    async def embed_one(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.chat_calls.append(messages)
        for delta in self.deltas:
            yield delta


class CancellingClient(FakeOllamaClient):
    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.chat_calls.append(messages)
        yield "部分"
        raise asyncio.CancelledError


class FakeVectorStore:
    """Single public doc; honors scopes for isolation tests."""

    def __init__(self, doc: str = "肚子疼建议挂消化内科", scope: str = "public") -> None:
        self.doc = doc
        self.scope = scope
        self.last_scopes: list[str] | None = None

    def upsert(self, scope, ids, documents, metadatas, embeddings) -> None:
        return None

    def query(self, embedding, *, scopes, n_results=None, where=None):
        self.last_scopes = list(scopes)
        if self.scope not in scopes:
            return []
        return [
            {
                "document": self.doc,
                "metadata": {"file": "symptoms.md", "index": 1, "scope": self.scope},
                "distance": 0.1,
            }
        ]

    def count(self, scope=None) -> int:
        return 1


class ScopeAwareStore:
    """Returns only chunks whose scope is in the queried scopes."""

    def __init__(self, docs: list[tuple[str, str, float]]) -> None:
        self.docs = docs
        self.last_scopes: list[str] | None = None

    def upsert(self, scope, ids, documents, metadatas, embeddings) -> None:
        return None

    def query(self, embedding, *, scopes, n_results=None, where=None):
        self.last_scopes = list(scopes)
        return [
            {
                "document": doc,
                "metadata": {"file": f"f{i}.md", "index": 0, "scope": scope},
                "distance": dist,
            }
            for i, (doc, scope, dist) in enumerate(self.docs)
            if scope in scopes
        ]

    def count(self, scope=None) -> int:
        return len(self.docs)


class LeakingStore:
    """Simulates a router bug: returns a clinical chunk for any scopes."""

    def upsert(self, scope, ids, documents, metadatas, embeddings) -> None:
        return None

    def query(self, embedding, *, scopes, n_results=None, where=None):
        return [
            {
                "document": "临床限制内容SECRET",
                "metadata": {"file": "clin.md", "index": 0, "scope": "clinical"},
                "distance": 0.01,
            }
        ]

    def count(self, scope=None) -> int:
        return 1


def _make_service(
    client: FakeOllamaClient,
    session_factory: sessionmaker[Session],
    store: object | None = None,
) -> TriageService:
    if store is None:
        store = FakeVectorStore()
    return TriageService(client, store, EmbeddingService(client), session_factory)


def test_split_short_text() -> None:
    assert split_text("短文本", size=500, overlap=80) == ["短文本"]


def test_split_empty_text() -> None:
    assert split_text("   \n  ", size=500, overlap=80) == []


def test_split_multiline_packs_into_one_chunk() -> None:
    text = "第一段\n第二段\n第三段"
    chunks = split_text(text, size=500, overlap=80)
    assert len(chunks) == 1


def test_split_long_text_boundaries() -> None:
    long = "x" * 1200
    chunks = split_text(long, size=500, overlap=80)
    assert len(chunks) == 3
    assert all(len(c) <= 500 for c in chunks)
    assert chunks[0] == long[:500]


def test_split_invalid_args() -> None:
    with pytest.raises(ValueError):
        split_text("abc", size=0, overlap=0)
    with pytest.raises(ValueError):
        split_text("abc", size=100, overlap=100)
    with pytest.raises(ValueError):
        split_text("abc", size=100, overlap=-1)


async def test_stream_answer_event_sequence_and_persist(session_factory) -> None:
    service = _make_service(FakeOllamaClient(deltas=["消化", "内科"]), session_factory)
    events = [
        event
        async for event in service.stream_answer("肚子疼挂什么科", None, PATIENT)
    ]

    assert "conversationId" in events[0]
    assert events[1]["sources"] == [
        {"file": "symptoms.md", "text": "肚子疼建议挂消化内科", "scope": "public"}
    ]
    assert [e for e in events if "delta" in e] == [{"delta": "消化"}, {"delta": "内科"}]
    assert events[-1] == {"done": True}

    history = service.get_history(events[0]["conversationId"], PATIENT)
    assert [m.role for m in history.messages] == ["user", "assistant"]
    assert history.messages[0].content == "肚子疼挂什么科"
    assert history.messages[1].content == "消化内科"
    assert history.messages[1].interrupted is False


async def test_stream_answer_includes_history(session_factory) -> None:
    client = FakeOllamaClient(deltas=["好"])
    service = _make_service(client, session_factory)
    conv_id = "conv-1"
    async for _ in service.stream_answer("第一次", conv_id, PATIENT):
        pass
    async for _ in service.stream_answer("第二次", conv_id, PATIENT):
        pass

    assert len(client.chat_calls) == 2
    roles = [m["role"] for m in client.chat_calls[1]]
    assert roles == ["system", "user", "assistant", "user"]
    assert client.chat_calls[1][-1]["content"] == "第二次"
    assert client.chat_calls[1][-2]["content"] == "好"
    assert client.chat_calls[1][0]["role"] == "system"
    assert "肚子疼建议挂消化内科" in client.chat_calls[1][0]["content"]


async def test_stream_answer_cancel_persists_partial(session_factory) -> None:
    service = _make_service(CancellingClient(deltas=[]), session_factory)
    events: list[dict[str, object]] = []
    with pytest.raises(asyncio.CancelledError):
        async for event in service.stream_answer("问一个问题", None, PATIENT):
            events.append(event)

    conv_id = events[0]["conversationId"]
    history = service.get_history(conv_id, PATIENT)
    assert len(history.messages) == 2
    assert history.messages[1].content == "部分"
    assert history.messages[1].interrupted is True


async def test_list_conversations_returns_preview(session_factory) -> None:
    client = FakeOllamaClient(deltas=["回复"])
    service = _make_service(client, session_factory)
    async for _ in service.stream_answer("我肚子疼", None, PATIENT):
        pass

    convs = service.list_conversations(PATIENT)
    assert len(convs) == 1
    assert convs[0].preview == "我肚子疼"


def test_match_departments_returns_mentioned_in_order() -> None:
    text = "若腹痛剧烈且持续不缓解，请到急诊科就诊；反复腹泻建议挂消化内科。"
    names = [d.name for d in match_departments(text)]
    assert names == ["急诊科", "消化内科"]


def test_departments_carry_ids() -> None:
    dept = match_departments("建议挂消化内科")[0]
    assert dept.id == "0102"
    assert dept.category == "内科"


def test_match_departments_ignores_unknown() -> None:
    assert match_departments("建议挂肾内科（本院暂无此科）") == []


def test_resolve_primary_from_marker() -> None:
    text = "建议就诊消化内科。\n推荐科室：消化内科"
    assert resolve_primary(text).name == "消化内科"


def test_resolve_primary_falls_back_to_first_mention() -> None:
    assert resolve_primary("请到急诊科挂号").name == "急诊科"


def test_resolve_primary_none_when_no_department() -> None:
    assert resolve_primary("请前往导诊台咨询。\n推荐科室：无") is None


async def test_stream_answer_emits_department_events(session_factory) -> None:
    deltas = ["反复腹泻建议挂消化内科。", " 若腹痛剧烈请到急诊科。"]
    service = _make_service(FakeOllamaClient(deltas=deltas), session_factory)
    events = [
        event
        async for event in service.stream_answer("反复腹泻挂什么科", None, PATIENT)
    ]

    department_event = next(e for e in events if "department" in e)
    assert department_event["department"]["name"] == "消化内科"
    assert [d["name"] for d in department_event["matchedDepartments"]] == [
        "消化内科",
        "急诊科",
    ]
    assert events[-1] == {"done": True}

    history = service.get_history(events[0]["conversationId"], PATIENT)
    assert (
        history.messages[1].content
        == "反复腹泻建议挂消化内科。 若腹痛剧烈请到急诊科。"
    )


async def test_patient_cannot_retrieve_clinical_knowledge(session_factory) -> None:
    store = ScopeAwareStore([
        ("公开导诊信息PUBLIC", "public", 0.10),
        ("临床限制内容SECRET", "clinical", 0.05),
    ])
    client = FakeOllamaClient(deltas=["回复"])
    service = _make_service(client, session_factory, store=store)
    events = [
        event
        async for event in service.stream_answer("问诊", None, PATIENT)
    ]

    sources_event = next(e for e in events if "sources" in e)
    assert [s["scope"] for s in sources_event["sources"]] == ["public"]
    assert "SECRET" not in client.chat_calls[0][0]["content"]
    assert "PUBLIC" in client.chat_calls[0][0]["content"]
    assert set(store.last_scopes) == {"public"}


async def test_doctor_retrieves_clinical_scope(session_factory) -> None:
    store = ScopeAwareStore([
        ("公开导诊信息PUBLIC", "public", 0.10),
        ("临床限制内容SECRET", "clinical", 0.05),
    ])
    client = FakeOllamaClient(deltas=["回复"])
    service = _make_service(client, session_factory, store=store)
    events = [
        event
        async for event in service.stream_answer("问诊", None, DOCTOR)
    ]

    sources_event = next(e for e in events if "sources" in e)
    assert set(s["scope"] for s in sources_event["sources"]) == {"public", "clinical"}
    assert "SECRET" in client.chat_calls[0][0]["content"]
    assert set(store.last_scopes) == {"public", "clinical"}


async def test_service_filters_leaked_scope_before_llm(session_factory) -> None:
    """Even with a broken router returning a clinical chunk, the patient's
    context fed to the LLM must not contain it: isolation does not rely on
    the prompt."""
    store = LeakingStore()
    client = FakeOllamaClient(deltas=["回复"])
    service = _make_service(client, session_factory, store=store)
    events = [
        event
        async for event in service.stream_answer("问诊", None, PATIENT)
    ]

    sources_event = next(e for e in events if "sources" in e)
    assert sources_event["sources"] == []
    assert "SECRET" not in client.chat_calls[0][0]["content"]


async def test_role_change_forces_new_conversation(session_factory) -> None:
    client = FakeOllamaClient(deltas=["好"])
    service = _make_service(client, session_factory)
    events = [e async for e in service.stream_answer("第一次", None, DOCTOR)]
    conv_id = events[0]["conversationId"]

    events = [e async for e in service.stream_answer("继续", conv_id, PATIENT)]
    assert events == [{"error": "无权访问该会话"}]
