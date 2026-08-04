from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ValidationError

from .settings import get_settings

Scene = Literal["hospital", "home"]


class TokenClaims(BaseModel):
    sub: str
    tenant_id: str
    scene: Scene
    role: str = "user"
    exp: int

    @classmethod
    def create(
        cls,
        sub: str,
        tenant_id: str,
        scene: Scene,
        role: str = "user",
    ) -> "TokenClaims":
        settings = get_settings()
        exp_dt = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            minutes=settings.jwt_expire_minutes
        )
        return cls(sub=sub, tenant_id=tenant_id, scene=scene, role=role, exp=int(exp_dt.timestamp()))


def create_access_token(claims: TokenClaims) -> str:
    settings = get_settings()
    payload = claims.model_dump(mode="json")
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return TokenClaims(**payload)
    except (jwt.PyJWTError, ValidationError) as exc:
        raise HTTPException(status_code=401, detail="无效或过期的 token") from exc


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


async def get_current_tenant(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenClaims:
    """依赖：从 Authorization: Bearer <token> 解析当前租户/用户。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")
    return decode_token(authorization.split(" ", 1)[1].strip())


CurrentTenant = Annotated[TokenClaims, Depends(get_current_tenant)]
