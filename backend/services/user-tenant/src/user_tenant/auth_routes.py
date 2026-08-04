from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from my_robot_common.auth import CurrentTenant, TokenClaims, create_access_token, hash_password
from my_robot_common.db import get_db
from my_robot_common.exceptions import AppException

from .models import Tenant, User

router = APIRouter()


class LoginIn(BaseModel):
    phone: str
    password: str
    tenant_id: str | None = None


class UserOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    phone: str
    role: str

    @classmethod
    def from_orm_user(cls, u: User) -> "UserOut":
        return cls(id=u.id, tenant_id=u.tenant_id, name=u.name, phone=u.phone, role=u.role)


class TenantOut(BaseModel):
    id: str
    name: str
    scene: str
    config: dict


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    tenant: TenantOut


def _tenant_out(t: Tenant) -> TenantOut:
    return TenantOut(id=t.id, name=t.name, scene=t.scene, config=t.config or {})


@router.post("/auth/login", response_model=LoginOut)
async def login(body: LoginIn, db: Annotated[AsyncSession, Depends(get_db)]) -> LoginOut:
    user = await db.scalar(select(User).where(User.phone == body.phone))
    if user is None:
        raise AppException(401, "invalid_credentials", "手机号或密码错误")
    from my_robot_common.auth import verify_password

    if not verify_password(body.password, user.password_hash):
        raise AppException(401, "invalid_credentials", "手机号或密码错误")
    if body.tenant_id and body.tenant_id != user.tenant_id:
        raise AppException(403, "tenant_mismatch", "用户不属于该租户")
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise AppException(500, "tenant_missing", "用户租户不存在")
    claims = TokenClaims.create(
        sub=user.id, tenant_id=tenant.id, scene=tenant.scene, role=user.role  # type: ignore[arg-type]
    )
    from my_robot_common.settings import get_settings

    token = create_access_token(claims)
    return LoginOut(
        access_token=token,
        expires_in=get_settings().jwt_expire_minutes * 60,
        user=UserOut.from_orm_user(user),
        tenant=_tenant_out(tenant),
    )


@router.post("/auth/refresh", response_model=LoginOut)
async def refresh(
    claims: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginOut:
    user = await db.get(User, claims.sub)
    if user is None:
        raise AppException(404, "user_not_found", "用户不存在")
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise AppException(500, "tenant_missing", "用户租户不存在")
    new_claims = TokenClaims.create(
        sub=user.id, tenant_id=tenant.id, scene=tenant.scene, role=user.role  # type: ignore[arg-type]
    )
    token = create_access_token(new_claims)
    return LoginOut(
        access_token=token,
        expires_in=0,
        user=UserOut.from_orm_user(user),
        tenant=_tenant_out(tenant),
    )
