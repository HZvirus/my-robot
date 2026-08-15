'''Science-popularization endpoints: SSE chat, history, and conversation list.'''

import asyncio
import json
from collections.abc import AsyncIterator

from anyio import to_thread
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.models.science import (
    ScienceConversationOut,
    ScienceHistoryResponse,
    ScienceStreamRequest,
)
from app.services.science_service import science_service

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
        await to_thread.run_sync(
            science_service.ensure_access, conversation_id, user_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail='会话不存在') from None


@router.post('/science/chat')
async def science_chat(
    req: ScienceStreamRequest, user_id: str = CurrentUser
) -> StreamingResponse:
    await _guard_conversation(req.conversation_id, user_id)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in science_service.stream_answer(
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


@router.get('/science/history/{conversation_id}', response_model=ScienceHistoryResponse)
async def science_history(
    conversation_id: str, user_id: str = CurrentUser
) -> ScienceHistoryResponse:
    try:
        return await to_thread.run_sync(
            science_service.get_history, conversation_id, user_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail='会话不存在') from None


@router.get('/science/conversations', response_model=list[ScienceConversationOut])
async def science_conversations(
    user_id: str = CurrentUser
) -> list[ScienceConversationOut]:
    return await to_thread.run_sync(science_service.list_conversations, user_id)
