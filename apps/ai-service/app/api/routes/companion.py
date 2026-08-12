"""Health companion endpoints: SSE chat, history, and conversation list."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.companion import (
    CompanionConversationOut,
    CompanionHistoryResponse,
    CompanionStreamRequest,
)
from app.services.companion_service import companion_service

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/companion/chat")
async def companion_chat(req: CompanionStreamRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in companion_service.stream_answer(
                req.message, req.conversation_id
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


@router.get("/companion/history/{conversation_id}", response_model=CompanionHistoryResponse)
async def companion_history(conversation_id: str) -> CompanionHistoryResponse:
    return companion_service.get_history(conversation_id)


@router.get("/companion/conversations", response_model=list[CompanionConversationOut])
async def companion_conversations() -> list[CompanionConversationOut]:
    return companion_service.list_conversations()
