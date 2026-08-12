"""Triage RAG endpoints: SSE chat, history, and conversation list."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

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


@router.post("/triage/chat")
async def triage_chat(req: TriageRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in triage_service.stream_answer(req.message, req.conversation_id):
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
async def triage_history(conversation_id: str) -> TriageHistoryResponse:
    return triage_service.get_history(conversation_id)


@router.get("/triage/departments", response_model=list[DepartmentOut])
async def triage_departments() -> list[DepartmentOut]:
    return [DepartmentOut(**item) for item in list_departments()]


@router.get("/triage/conversations", response_model=list[TriageConversationOut])
async def triage_conversations() -> list[TriageConversationOut]:
    return triage_service.list_conversations()
