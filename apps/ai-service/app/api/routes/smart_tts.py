'''iFlytek Super Smart TTS endpoints.

- POST /api/smart-tts/stream: single text to audio (SSE)
- GET  /api/smart-tts/ws-url: signed WebSocket URL for browser direct connect
- WS   /api/smart-tts/ws: bidirectional bridge (incremental text in, audio out),
  replacing the old buffered POST /api/smart-tts/stream-text endpoint.
'''

import asyncio
import base64
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.core.logger import get_logger
from app.models.smart_tts import SmartTtsStreamRequest
from app.services.auth_service import auth_service
from app.services.smart_tts_service import smart_tts_service

router = APIRouter()

logger = get_logger(__name__)

_SSE_HEADERS = {
    'Cache-Control': 'no-cache',
    'X-Accel-Buffering': 'no',
    'Connection': 'keep-alive',
}


@router.get('/smart-tts/ws-url')
async def smart_tts_ws_url(user_id: str = CurrentUser) -> dict[str, str]:
    '''Return a signed WebSocket URL the browser can connect to directly.

    Browsers cannot attach an x-api-key header during the WS handshake, so
    direct connect uses an HMAC-SHA256 signed URL (auth method 2). Signing is
    done server-side: the frontend never holds iFlytek credentials, it calls
    this endpoint to get {url, app_id} and then opens the WebSocket itself.
    '''
    if not smart_tts_service.configured:
        raise HTTPException(status_code=400, detail='iFlytek Super Smart TTS 未配置')
    if smart_tts_service.auth_method != 2:
        raise HTTPException(
            status_code=400,
            detail='浏览器直连需要 IFLYTEK_SMART_TTS_AUTH_METHOD=2（HMAC-SHA256 签名 URL）',
        )
    try:
        url = smart_tts_service.build_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'url': url, 'app_id': smart_tts_service.app_id}



def _encode_chunk(chunk: bytes) -> str:
    payload = json.dumps(
        {'audio': base64.b64encode(chunk).decode('ascii')},
        ensure_ascii=False,
    )
    return f'data: {payload}\n\n'


def _error_event(exc: Exception) -> str:
    payload = json.dumps({'error': str(exc)}, ensure_ascii=False)
    return f'data: {payload}\n\n'


@router.post('/smart-tts/stream')
async def smart_tts_stream(
    req: SmartTtsStreamRequest, user_id: str = CurrentUser
) -> StreamingResponse:
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
            yield 'data: [DONE]\n\n'
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning('smart tts stream error: %s', exc)
            yield _error_event(exc)

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers=_SSE_HEADERS,
    )



def _verify_ws_token(token: str | None) -> str | None:
    '''Verify a device token for the WS bridge (browsers cannot send headers).'''
    if not token:
        return None
    return auth_service.verify_token(token)


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _opt_int(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


@router.websocket('/smart-tts/ws')
async def smart_tts_ws_bridge(ws: WebSocket) -> None:
    '''Bridge browser to iFlytek: incremental text frames in, MP3 audio out.

    Protocol (JSON text frames over the browser WebSocket):
    1. client sends options: {voice, speed, volume, pitch, sampleRate, oralLevel}
    2. client sends text pieces: {text: ...}
    3. client closes input: {end: true}
    server replies {audio: base64}* then {done: true}, or {error: ...}.
    '''
    await ws.accept()
    if _verify_ws_token(ws.query_params.get('token')) is None:
        await ws.close(code=4401, reason='unauthorized')
        return

    async def read_frames() -> AsyncIterator[str]:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get('end'):
                return
            text = msg.get('text')
            if isinstance(text, str) and text:
                yield text

    try:
        try:
            first = json.loads(await ws.receive_text())
        except ValueError:
            first = {}
        opts: dict[str, object] = first if isinstance(first, dict) else {}
        sample_rate = opts.get('sampleRate')
        async for chunk in smart_tts_service.synthesize_stream(
            read_frames(),
            _opt_str(opts.get('voice')),
            _opt_int(opts.get('speed'), 50),
            _opt_int(opts.get('volume'), 50),
            _opt_int(opts.get('pitch'), 50),
            sample_rate if isinstance(sample_rate, int) else None,
            _opt_str(opts.get('oralLevel')),
        ):
            await ws.send_json({'audio': base64.b64encode(chunk).decode('ascii')})
        await ws.send_json({'done': True})
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning('smart tts ws bridge error: %s', exc)
        try:
            await ws.send_json({'error': str(exc)})
        except Exception:
            pass
