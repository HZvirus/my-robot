'''General chat endpoints: legacy non-stream, SSE stream, history, conversations.'''

import asyncio
import json
from collections.abc import AsyncIterator

from anyio import to_thread
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
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
    'Cache-Control': 'no-cache',
    'X-Accel-Buffering': 'no',
    'Connection': 'keep-alive',
}


async def _guard_conversation(conversation_id: str | None, user_id: str) -> None:
    '''Return 404 unless the conversation exists and belongs to the user.'''
    if not conversation_id:
        return
    try:
        await to_thread.run_sync(chat_service.ensure_access, conversation_id, user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='会话不存在') from None


@router.post('/chat', response_model=ChatResponse)
async def chat(req: ChatRequest, user_id: str = CurrentUser) -> ChatResponse:
    reply, conv_id = await ai_service.chat(req.message, req.conversation_id)
    return ChatResponse(reply=reply, conversation_id=conv_id)


@router.post('/chat/stream')
async def chat_stream(req: ChatStreamRequest, user_id: str = CurrentUser) -> StreamingResponse:
    await _guard_conversation(req.conversation_id, user_id)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in chat_service.stream_answer(
                req.message, req.conversation_id, user_id
            ):
                yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
            yield 'data: [DONE]\n\n'
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers=_SSE_HEADERS,
    )


@router.get('/chat/history/{conversation_id}', response_model=ChatHistoryResponse)
async def chat_history(conversation_id: str, user_id: str = CurrentUser) -> ChatHistoryResponse:
    try:
        return await to_thread.run_sync(
            chat_service.get_history, conversation_id, user_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail='会话不存在') from None


@router.get('/chat/conversations', response_model=list[ChatConversationOut])
async def chat_conversations(user_id: str = CurrentUser) -> list[ChatConversationOut]:
    return await to_thread.run_sync(chat_service.list_conversations, user_id)
