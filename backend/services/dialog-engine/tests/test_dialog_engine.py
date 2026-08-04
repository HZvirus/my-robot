import pytest

from dialog_engine.actions import extract_action
from dialog_engine.safety import check_safety
from dialog_engine.scene_config import (
    AVAILABLE_SCENES,
    load_scene_config,
)
from dialog_engine.ws_chat import router as ws_router
from dialog_engine.feedback_routes import router as feedback_router


def test_scene_configs():
    h = load_scene_config("hospital")
    assert h.rag_mode == "force"
    assert h.safety_policy == "escalate"
    assert h.output_format == "structured"
    assert "hospital_dept" in h.rag_collections

    home = load_scene_config("home")
    assert home.rag_mode == "on_demand"
    assert home.safety_policy == "soothe"
    assert home.output_format == "natural"
    assert AVAILABLE_SCENES == ("hospital", "home")


def test_safety_escalate_vs_soothe():
    assert check_safety("普通文字", "escalate") is None
    esc = check_safety("他提到癌症", "escalate")
    assert esc["event"] == "escalate"
    soo = check_safety("他提到癌症", "soothe")
    assert soo["event"] == "soothe"
    assert "陪着" in soo["message"]


def test_extract_action_fenced_and_bare():
    fenced = '回复\n```json\n{"type":"weather_broadcast","params":{"city":"深圳"}}\n```'
    action = extract_action(fenced)
    assert action is not None
    assert action["type"] == "weather_broadcast"
    assert action["params"]["city"] == "深圳"
    assert "id" in action

    bare = '好的 {"type":"home_light","params":{"device":"客厅灯","action":"on"}} 完成'
    action2 = extract_action(bare)
    assert action2["type"] == "home_light"

    assert extract_action("纯文本没有动作") is None
    assert extract_action('{"foo":"bar"}') is None


@pytest.mark.asyncio
async def test_run_chat_streams_and_enqueues_action(monkeypatch):
    from dialog_engine import chat
    from dialog_engine.session import SessionState
    from my_robot_common.ws import WSMessage

    sent: list[WSMessage] = []

    async def fake_send(msg):
        sent.append(msg)

    async def noop(*a, **k):
        return None

    async def fake_history(_sid):
        return []

    async def fake_stream(scene, messages):
        yield "我是"
        yield "机器人"
        yield '\n```json\n{"type":"weather_broadcast","params":{"city":"深圳"}}\n```'

    async def fake_collect_context(collections, query, top_k=2):
        return ""

    captured: dict = {}

    async def fake_enqueue(session, action):
        captured["action"] = action

    monkeypatch.setattr(chat, "set_state", noop)
    monkeypatch.setattr(chat, "add_history", noop)
    monkeypatch.setattr(chat, "get_history", fake_history)
    monkeypatch.setattr(chat, "stream_chat", fake_stream)
    monkeypatch.setattr(chat, "collect_context", fake_collect_context)
    monkeypatch.setattr(chat, "enqueue_task", fake_enqueue)

    session = {
        "session_id": "s1",
        "tenant_id": "t-hospital-0001",
        "scene": "hospital",
        "user_id": "u1",
        "device_id": "mock-01",
    }
    await chat.run_chat(fake_send, session, "今天天气")

    types = [m.type for m in sent]
    assert "token" in types
    assert "action" in types
    assert "message" in types
    assert captured["action"]["type"] == "weather_broadcast"
    # 完整回复 message 中含动作文本
    msg = next(m for m in sent if m.type == "message")
    assert "机器人" in msg.payload["text"]


def test_ws_and_feedback_routers_exist():
    assert ws_router.prefix == "" or ws_router.prefix is None
    paths = {r.path for r in ws_router.routes}
    assert "/ws/chat" in paths
    assert feedback_router.prefix == "/api"
