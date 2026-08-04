from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from my_robot_common.auth import CurrentTenant, hash_password
from my_robot_common.db import get_db
from my_robot_common.exceptions import AppException

from .auth_routes import UserOut
from .models import User

router = APIRouter()


class UserCreateIn(BaseModel):
    name: str
    phone: str
    password: str
    role: str = "user"


@router.get("/users/me", response_model=UserOut)
async def me(claims: CurrentTenant, db: Annotated[AsyncSession, Depends(get_db)]) -> UserOut:
    user = await db.get(User, claims.sub)
    if user is None:
        raise AppException(404, "user_not_found", "用户不存在")
    return UserOut.from_orm_user(user)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    claims: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    rows = await db.scalars(
        select(User).where(User.tenant_id == claims.tenant_id).order_by(User.created_at)
    )
    return [UserOut.from_orm_user(u) for u in rows]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreateIn,
    claims: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    if claims.role != "admin":
        raise AppException(403, "forbidden", "仅管理员可创建用户")
    existing = await db.scalar(select(User).where(User.phone == body.phone))
    if existing is not None:
        raise AppException(409, "phone_exists", "手机号已存在")
    user = User(
        tenant_id=claims.tenant_id,
        name=body.name,
        phone=body.phone,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.from_orm_user(user)
