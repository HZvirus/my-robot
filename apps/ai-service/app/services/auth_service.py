'''Anonymous device-token auth: register devices, verify tokens via stored hashes.'''

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import User
from app.db.session import SessionLocal

MIN_TOKEN_LENGTH = 16
MAX_TOKEN_LENGTH = 128


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthService:
    '''Issues stable user ids for anonymous devices.

    Only the SHA-256 hash of the device token is stored, so a database leak
    does not leak usable credentials. The raw token stays on the client.
    '''

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def register_device(self, device_token: str) -> str:
        '''Register (or look up) a device token and return its stable user id.'''
        if not (MIN_TOKEN_LENGTH <= len(device_token) <= MAX_TOKEN_LENGTH):
            raise ValueError('device token length must be 16-128 chars')
        token_hash = _hash_token(device_token)
        with self._session_scope() as db:
            user = db.scalars(select(User).where(User.token_hash == token_hash)).first()
            if user is not None:
                return user.id
            user = User(id=str(uuid4()), token_hash=token_hash, created_at=_utcnow())
            db.add(user)
            db.commit()
            return user.id

    def verify_token(self, device_token: str) -> str | None:
        '''Return the user id for a valid device token, else None.'''
        token_hash = _hash_token(device_token)
        with self._session_scope() as db:
            user = db.scalars(select(User).where(User.token_hash == token_hash)).first()
            return user.id if user is not None else None

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()


auth_service = AuthService(SessionLocal)
