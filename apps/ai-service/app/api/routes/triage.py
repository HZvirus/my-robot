"""Triage RAG endpoints: SSE chat, history, and conversation list."""

import asyncio
import json
from collections.abc import AsyncIterator

from anyio import to_thread
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.core.rbac import Principal
from app.models.triage import (
    DepartmentOut,
    TriageConversationOut,
    TriageHistoryResponse,
    TriageRequest,
)
from app.services.departments import list_departments
from app.services.triage_service import triage_service

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


async def _guard_conversation(
    conversation_id: str | None, principal: Principal
) -> None:
    """Return 404 unless the conversation exists and belongs to the user."""
    if not conversation_id:
        return
    try:
        await to_thread.run_sync(
            triage_service.ensure_access, conversation_id, principal
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="会话不存在") from None


@router.post("/triage/chat")
async def triage_chat(
    req: TriageRequest, principal: Principal = CurrentUser
) -> StreamingResponse:
    await _guard_conversation(req.conversation_id, principal)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in triage_service.stream_answer(
                req.message, req.conversation_id, principal
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/triage/history/{conversation_id}", response_model=TriageHistoryResponse)
async def triage_history(
    conversation_id: str, principal: Principal = CurrentUser
) -> TriageHistoryResponse:
    try:
        return await to_thread.run_sync(
            triage_service.get_history, conversation_id, principal
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="会话不存在") from None


@router.get("/triage/departments", response_model=list[DepartmentOut])
async def triage_departments() -> list[DepartmentOut]:
    return [DepartmentOut(**item) for item in list_departments()]


@router.get("/triage/conversations", response_model=list[TriageConversationOut])
async def triage_conversations(
    principal: Principal = CurrentUser
) -> list[TriageConversationOut]:
    return await to_thread.run_sync(triage_service.list_conversations, principal)
