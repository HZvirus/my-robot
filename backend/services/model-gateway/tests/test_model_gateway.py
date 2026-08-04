import pytest
from fastapi.testclient import TestClient

from model_gateway.adapters import ChatMessage, ChatRequest, MockAdapter
from model_gateway.groups import build_adapters, get_adapter, resolve_group
from model_gateway.main import app

client = TestClient(app)


def test_health_reports_adapters():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "adapters" in body
    assert "skeleton_mock" in body["adapters"]


def test_resolve_group_by_scene():
    assert resolve_group("hospital") == "hospital_cloud"
    assert resolve_group("home") == "home_edge"
    assert resolve_group(None) == "skeleton_mock"


def test_hospital_cloud_without_key_falls_back_to_mock():
    used, adapter = get_adapter("hospital_cloud")
    assert used == "skeleton_mock"
    assert adapter.name == "mock"


@pytest.mark.asyncio
async def test_mock_adapter_streams_tokens():
    adapter = MockAdapter(delay=0)
    req = ChatRequest(
        messages=[ChatMessage(role="user", content="你好")],
        scene="hospital",
    )
    chunks = [c async for c in adapter.stream_chat(req)]
    full = "".join(chunks)
    assert "医院智能服务机器人" in full


@pytest.mark.asyncio
async def test_mock_action_on_weather_trigger():
    adapter = MockAdapter(delay=0)
    req = ChatRequest(
        messages=[ChatMessage(role="user", content="今天天气怎么样")],
        scene="home",
    )
    full = "".join([c async for c in adapter.stream_chat(req)])
    assert "weather_broadcast" in full


def test_v1_chat_stream_endpoint():
    resp = client.post(
        "/v1/chat",
        json={
            "messages": [{"role": "user", "content": "你好"}],
            "stream": True,
            "scene": "hospital",
        },
    )
    assert resp.status_code == 200
    text = resp.text
    assert "data: " in text
    assert "[DONE]" in text


def test_v1_models_endpoint():
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()["data"]]
    assert "skeleton-mock" in ids
