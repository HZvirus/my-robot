import pytest
from fastapi.testclient import TestClient

from task_executor.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stream"] == "task:execute"


def test_task_status_not_found():
    resp = client.get("/tasks/nope")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_handle_task_uses_mock_driver(monkeypatch):
    from task_executor import worker

    captured: dict = {}

    async def fake_publish(t, d, tid, action, result):
        captured["tenant"] = t
        captured["device"] = d
        captured["action"] = action
        captured["result"] = result

    monkeypatch.setattr(worker, "publish_command", fake_publish)
    monkeypatch.setattr(worker, "set_task_status", lambda *a, **k: _noop())

    await worker.handle_task(
        "m1",
        {
            "id": "t1",
            "type": "speak",
            "params": {"text": "你好"},
            "tenant_id": "t-tenant",
            "device_id": "mock-01",
        },
    )
    assert captured["tenant"] == "t-tenant"
    assert captured["action"]["type"] == "speak"
    assert captured["result"]["ok"] is True
    assert captured["result"]["driver"] == "mock"


async def _noop():
    return None
