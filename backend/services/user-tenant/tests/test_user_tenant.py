from fastapi.testclient import TestClient

from my_robot_common.db import get_db

from user_tenant.main import app

client = TestClient(app)


async def _fake_db():
    yield None


def test_health_without_lifespan():
    # 不进入 lifespan（不连库），/health 仍可返回
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_missing_body_returns_422():
    # 覆写 DB 依赖，仅验证 body 校验
    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_seed_constants():
    from user_tenant.seed import (
        HOSPITAL_TENANT_ID,
        HOME_TENANT_ID,
        SEED_PHONE_HOSPITAL,
        SEED_PHONE_HOME,
    )

    assert HOSPITAL_TENANT_ID.startswith("t-hospital")
    assert HOME_TENANT_ID.startswith("t-home")
    assert SEED_PHONE_HOSPITAL != SEED_PHONE_HOME
