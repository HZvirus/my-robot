from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from my_robot_common.auth import CurrentTenant
from my_robot_common.db import get_db
from my_robot_common.exceptions import AppException

from .auth_routes import TenantOut
from .models import Tenant

router = APIRouter()


class TenantCreateIn(BaseModel):
    name: str
    scene: str  # hospital | home
    config: dict = {}


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(
    claims: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantOut]:
    # 管理员可见全部，普通用户仅本租户
    stmt = select(Tenant)
    if claims.role != "admin":
        stmt = stmt.where(Tenant.id == claims.tenant_id)
    rows = await db.scalars(stmt.order_by(Tenant.created_at))
    return [TenantOut(id=t.id, name=t.name, scene=t.scene, config=t.config or {}) for t in rows]


@router.post("/tenants", response_model=TenantOut, status_code=201)
async def create_tenant(
    body: TenantCreateIn,
    claims: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantOut:
    if claims.role != "admin":
        raise AppException(403, "forbidden", "仅管理员可创建租户")
    if body.scene not in ("hospital", "home"):
        raise AppException(400, "invalid_scene", "scene 必须为 hospital 或 home")
    existing = await db.scalar(select(Tenant).where(Tenant.name == body.name))
    if existing is not None:
        raise AppException(409, "tenant_exists", "租户名已存在")
    tenant = Tenant(name=body.name, scene=body.scene, config=body.config)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return TenantOut(id=tenant.id, name=tenant.name, scene=tenant.scene, config=tenant.config or {})
