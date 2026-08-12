"""iFlytek TTS endpoint: stream MP3 audio chunks over SSE."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.logger import get_logger
from app.models.tts import TtsStreamRequest
from app.services.tts_service import tts_service

router = APIRouter()

logger = get_logger(__name__)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/tts/stream")
async def tts_stream(req: TtsStreamRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in tts_service.synthesize(
                req.text, req.voice, req.speed, req.volume, req.pitch
            ):
                payload = json.dumps(
                    {"audio": base64.b64encode(chunk).decode("ascii")},
                    ensure_ascii=False,
                )
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("tts stream error: %s", exc)
            payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
