import hashlib
import hmac
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db import models as db_models  # noqa: F401 - register ORM models
from app.db.session import Base
from app.main import app
from app.services.auth_service import AuthService

client = TestClient(app)


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


def test_register_and_verify_roundtrip(session_factory) -> None:
    service = AuthService(session_factory)
    token = "device-token-0123456789abcdef"
    user_id = service.register_device(token)
    assert service.verify_token(token) == user_id
    assert service.verify_token("wrong-token-0123456789abcdef") is None


def test_register_is_idempotent(session_factory) -> None:
    service = AuthService(session_factory)
    token = "device-token-0123456789abcdef"
    assert service.register_device(token) == service.register_device(token)


def test_register_rejects_short_tokens(session_factory) -> None:
    service = AuthService(session_factory)
    with pytest.raises(ValueError):
        service.register_device("short")


def test_register_defaults_to_patient(session_factory) -> None:
    service = AuthService(session_factory)
    token = "device-token-0123456789abcdef"
    user_id = service.register_device(token)
    principal = service.resolve_principal(token)
    assert principal is not None
    assert principal.user_id == user_id
    assert principal.role == "patient"


def test_register_elevated_role_requires_secret(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RBAC_SIGNING_SECRET", "")
    service = AuthService(session_factory)
    with pytest.raises(PermissionError):
        service.register_device("device-token-0123456789abcdef", role="doctor")


def test_register_elevated_role_with_valid_token(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RBAC_SIGNING_SECRET", "topsecret")
    service = AuthService(session_factory)
    role_token = hmac.new(b"topsecret", b"doctor", hashlib.sha256).hexdigest()
    user_id = service.register_device(
        "device-token-0123456789abcdef", role="doctor", role_token=role_token
    )
    principal = service.resolve_principal("device-token-0123456789abcdef")
    assert principal is not None
    assert principal.user_id == user_id
    assert principal.role == "doctor"


def test_register_elevated_role_rejects_bad_token(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RBAC_SIGNING_SECRET", "topsecret")
    service = AuthService(session_factory)
    with pytest.raises(PermissionError):
        service.register_device(
            "device-token-0123456789abcdef", role="doctor", role_token="wrong"
        )


def test_auth_device_validates_input() -> None:
    resp = client.post("/api/auth/device", json={"device_id": "short"})
    assert resp.status_code == 422


def test_device_auth_request_accepts_camelcase_alias() -> None:
    from app.models.auth import DeviceAuthRequest

    req = DeviceAuthRequest(deviceId="device-token-0123456789abcdef")
    assert req.device_id == "device-token-0123456789abcdef"
    assert req.role == "patient"


def test_device_auth_response_serializes_camelcase() -> None:
    from app.models.auth import DeviceAuthResponse

    payload = DeviceAuthResponse(user_id="u1").model_dump(by_alias=True)
    assert payload == {"userId": "u1", "role": "patient"}


def test_auth_device_endpoint_accepts_camelcase(monkeypatch) -> None:
    from app.api.routes import auth as auth_route

    class FakeAuthService:
        def register_device(self, device_token, role="patient", role_token=None):
            return "user-test"

    monkeypatch.setattr(auth_route, "auth_service", FakeAuthService())
    resp = client.post(
        "/api/auth/device",
        json={"deviceId": "device-token-0123456789abcdef"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"userId": "user-test", "role": "patient"}


def test_full_auth_chain_register_then_access(session_factory, monkeypatch) -> None:
    from app.api import deps as deps_module
    from app.api.routes import auth as auth_route

    temp_auth = AuthService(session_factory)
    monkeypatch.setattr(auth_route, "auth_service", temp_auth)
    monkeypatch.setattr(deps_module, "auth_service", temp_auth)

    # Run the app lifespan so the dev DB schema (conversations.role) is
    # migrated before the companion endpoint queries it.
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/device",
            json={"deviceId": "device-token-0123456789abcdef"},
        )
        assert resp.status_code == 200

        resp = client.get("/api/companion/conversations")
        assert resp.status_code == 401

        resp = client.get(
            "/api/companion/conversations",
            headers={"Authorization": "Bearer device-token-0123456789abcdef"},
        )
        assert resp.status_code == 200
