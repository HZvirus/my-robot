from my_robot_common.auth import (
    TokenClaims,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from my_robot_common.ws import WSMessage


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_roundtrip_carries_scene():
    claims = TokenClaims.create(
        sub="u1", tenant_id="t1", scene="hospital", role="admin"
    )
    token = create_access_token(claims)
    decoded = decode_token(token)
    assert decoded.sub == "u1"
    assert decoded.tenant_id == "t1"
    assert decoded.scene == "hospital"
    assert decoded.role == "admin"


def test_ws_message_builders():
    assert WSMessage.token("你").payload == {"delta": "你"}
    msg = WSMessage.status("processing", event="escalate", message="hi")
    assert msg.type == "status"
    assert msg.payload["state"] == "processing"
    assert msg.payload["event"] == "escalate"
    act = WSMessage.action({"id": "a1", "type": "speak", "params": {"text": "x"}})
    assert act.payload["type"] == "speak"
    assert act.payload["status"] == "queued"
