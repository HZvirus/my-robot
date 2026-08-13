"""iFlytek Super Smart TTS endpoints: stream MP3 audio chunks over SSE.

- ``POST /api/smart-tts/stream``: single text -> audio
- ``POST /api/smart-tts/stream-text``: incremental text frames -> audio
- ``GET /api/smart-tts/ws-url``: signed WebSocket URL for browser direct connect
"""

import asyncio
import base64
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.logger import get_logger
from app.models.smart_tts import SmartTtsStreamRequest
from app.services.smart_tts_service import smart_tts_service

router = APIRouter()

logger = get_logger(__name__)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}

_SMART_ORDER = ("text", "voice", "speed", "volume", "pitch", "sample_rate", "oral_level")


@router.get("/smart-tts/ws-url")
async def smart_tts_ws_url() -> dict[str, str]:
    """返回浏览器可直接连通的签名 WebSocket 地址。

    浏览器在 WebSocket 握手时无法附加 ``x-api-key`` 头，因此直连只能使用
    HMAC-SHA256 签名 URL（鉴权方式二）。签名统一由后端完成：前端不持有
    任何讯飞凭据，调用本接口拿到 ``{url, app_id}`` 后自行建立 WS 连接。
    """
    if not smart_tts_service.configured:
        raise HTTPException(status_code=400, detail="iFlytek Super Smart TTS 未配置")
    if smart_tts_service.auth_method != 2:
        raise HTTPException(
            status_code=400,
            detail="浏览器直连需要 IFLYTEK_SMART_TTS_AUTH_METHOD=2（HMAC-SHA256 签名 URL）",
        )
    try:
        url = smart_tts_service.build_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"url": url, "app_id": smart_tts_service.app_id}


def _encode_chunk(chunk: bytes) -> str:
    payload = json.dumps(
        {"audio": base64.b64encode(chunk).decode("ascii")},
        ensure_ascii=False,
    )
    return f"data: {payload}\n\n"


def _error_event(exc: Exception) -> str:
    payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
    return f"data: {payload}\n\n"


@router.post("/smart-tts/stream")
async def smart_tts_stream(req: SmartTtsStreamRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in smart_tts_service.synthesize(
                req.text,
                req.voice,
                req.speed,
                req.volume,
                req.pitch,
                req.sample_rate,
                req.oral_level,
            ):
                yield _encode_chunk(chunk)
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("smart tts stream error: %s", exc)
            yield _error_event(exc)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/smart-tts/stream-text")
async def smart_tts_stream_text(request: Request) -> StreamingResponse:
    """Incremental synthesis: the request body is a newline-delimited stream
    of text pieces (one JSON-encoded string per line), matching the upstream
    LLM's token-by-token output. Audio chunks are streamed back over SSE.

    The body is buffered before the SSE response starts: reading
    ``request.stream()`` from inside the StreamingResponse generator
    deadlocks on this FastAPI/uvicorn stack, so the request body never
    reaches the synthesizer.
    """

    body = await request.body()

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in smart_tts_service.synthesize_stream(
                _iter_body_lines(body),
                None,
                50,
                50,
                50,
                None,
                None,
            ):
                yield _encode_chunk(chunk)
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("smart tts stream-text error: %s", exc)
            yield _error_event(exc)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _iter_body_lines(body: bytes) -> AsyncIterator[str]:
    for raw in body.split(b"\n"):
        line = raw.strip()
        if not line:
            continue
        yield _decode_text_line(line)


def _decode_text_line(line: bytes) -> str:
    if not line.startswith(b"{"):
        return line.decode("utf-8", errors="replace")
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return line.decode("utf-8", errors="replace")
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict) and "text" in obj:
        return str(obj["text"])
    return line.decode("utf-8", errors="replace")
