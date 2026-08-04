from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from my_robot_common.auth import CurrentTenant
from my_robot_common.db import get_db

from .db import Feedback

router = APIRouter(prefix="/api")


class FeedbackIn(BaseModel):
    session_id: str
    message_id: str
    score: int = Field(ge=-1, le=1)


@router.post("/feedback", status_code=201)
async def submit_feedback(
    body: FeedbackIn,
    claims: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    fb = Feedback(
        session_id=body.session_id,
        user_id=claims.sub,
        tenant_id=claims.tenant_id,
        message_id=body.message_id,
        score=body.score,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return {"ok": True, "id": fb.id, "score": fb.score}
