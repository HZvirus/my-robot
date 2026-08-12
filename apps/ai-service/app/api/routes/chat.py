import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat import (
    ChatConversationOut,
    ChatHistoryResponse,
    ChatStreamRequest,
)
from app.models.schemas import ChatRequest, ChatResponse
from app.services.ai_service import ai_service
from app.services.chat_service import chat_service

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    reply, conv_id = await ai_service.chat(req.message, req.conversation_id)
    return ChatResponse(reply=reply, conversation_id=conv_id)


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in chat_service.stream_answer(req.message, req.conversation_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/chat/history/{conversation_id}", response_model=ChatHistoryResponse)
async def chat_history(conversation_id: str) -> ChatHistoryResponse:
    return chat_service.get_history(conversation_id)


@router.get("/chat/conversations", response_model=list[ChatConversationOut])
async def chat_conversations() -> list[ChatConversationOut]:
    return chat_service.list_conversations()
