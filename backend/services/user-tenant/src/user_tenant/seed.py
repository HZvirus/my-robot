from __future__ import annotations

import logging

from sqlalchemy import select, func

from my_robot_common.auth import hash_password
from my_robot_common.db import get_session_maker

from .models import Base, Tenant, User

logger = logging.getLogger("user_tenant.seed")

# 固定 ID，便于离线登录与前端预填
HOSPITAL_TENANT_ID = "t-hospital-0001"
HOME_TENANT_ID = "t-home-0001"
HOSPITAL_USER_ID = "u-hospital-0001"
HOME_USER_ID = "u-home-0001"

SEED_PHONE_HOSPITAL = "13800000001"
SEED_PHONE_HOME = "13800000002"
SEED_PASSWORD = "123456"


async def seed_if_empty() -> bool:
    maker = get_session_maker()
    async with maker() as session:
        count = await session.scalar(select(func.count()).select_from(User))
        if count:
            return False

        hospital = Tenant(
            id=HOSPITAL_TENANT_ID,
            name="XX医院",
            scene="hospital",
            config={"device": "24inch-screen", "depts": ["骨科", "内科", "急诊"]},
        )
        home = Tenant(
            id=HOME_TENANT_ID,
            name="张爷爷家",
            scene="home",
            config={"device": "7inch-screen", "care_mode": True},
        )
        session.add_all([hospital, home])

        u1 = User(
            id=HOSPITAL_USER_ID,
            tenant_id=HOSPITAL_TENANT_ID,
            name="医院前台",
            phone=SEED_PHONE_HOSPITAL,
            role="admin",
            password_hash=hash_password(SEED_PASSWORD),
        )
        u2 = User(
            id=HOME_USER_ID,
            tenant_id=HOME_TENANT_ID,
            name="张爷爷",
            phone=SEED_PHONE_HOME,
            role="user",
            password_hash=hash_password(SEED_PASSWORD),
        )
        session.add_all([u1, u2])
        await session.commit()
        logger.info("种子数据已写入：XX医院(hospital) + 张爷爷家(home)")
        return True
