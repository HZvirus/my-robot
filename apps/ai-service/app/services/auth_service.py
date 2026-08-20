"""Anonymous device-token auth with role-based knowledge-base access.

Only the SHA-256 hash of the device token is stored. Elevated roles
(nurse/doctor/admin) require a role token signed with RBAC_SIGNING_SECRET;
when that secret is empty, only the default patient role may be registered.
"""

import hashlib
import hmac
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.rbac import DEFAULT_ROLE, Principal, is_elevated, is_valid_role
from app.db.models import User
from app.db.session import SessionLocal

MIN_TOKEN_LENGTH = 16
MAX_TOKEN_LENGTH = 128


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sign_role(role: str) -> str:
    secret = settings.RBAC_SIGNING_SECRET.encode("utf-8")
    return hmac.new(secret, role.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_role_token(role: str, role_token: str | None) -> bool:
    if not settings.RBAC_SIGNING_SECRET or not role_token:
        return False
    return hmac.compare_digest(_sign_role(role), role_token)


class AuthService:
    """Issues stable user ids for anonymous devices."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def register_device(
        self,
        device_token: str,
        role: str = DEFAULT_ROLE,
        role_token: str | None = None,
    ) -> str:
        """Register (or look up) a device token and return its stable user id."""
        if not (MIN_TOKEN_LENGTH <= len(device_token) <= MAX_TOKEN_LENGTH):
            raise ValueError("device token length must be 16-128 chars")
        if not is_valid_role(role):
            raise ValueError(f"unknown role: {role}")
        if is_elevated(role) and not _verify_role_token(role, role_token):
            raise PermissionError(f"elevated role {role} requires a valid role token")

        token_hash = _hash_token(device_token)
        with self._session_scope() as db:
            user = db.scalars(select(User).where(User.token_hash == token_hash)).first()
            if user is not None:
                if user.role != role:
                    user.role = role
                    db.commit()
                return user.id
            user = User(
                id=str(uuid4()),
                token_hash=token_hash,
                role=role,
                created_at=_utcnow(),
            )
            db.add(user)
            db.commit()
            return user.id

    def verify_token(self, device_token: str) -> str | None:
        """Return the user id for a valid device token, else None."""
        token_hash = _hash_token(device_token)
        with self._session_scope() as db:
            user = db.scalars(select(User).where(User.token_hash == token_hash)).first()
            return user.id if user is not None else None

    def resolve_principal(self, device_token: str) -> Principal | None:
        """Return the Principal for a valid device token, else None."""
        token_hash = _hash_token(device_token)
        with self._session_scope() as db:
            user = db.scalars(select(User).where(User.token_hash == token_hash)).first()
            if user is None:
                return None
            return Principal(user_id=user.id, role=user.role or DEFAULT_ROLE)

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()


auth_service = AuthService(SessionLocal)
