"""iFlytek Super Smart TTS service (超拟人语音合成 WebSocket API).

Independent from the v2 online TTS in ``tts_service``. Key differences:
- protocol body uses ``header`` / ``parameter`` / ``payload`` sections
- supports bidirectional streaming: text can be sent incrementally
  (status 0/1/2 frames) while audio streams back in the same session
- voices are the x4/x5/x6 series (e.g. ``x6_lingxiaoxuan_flow``)
- two auth modes: ``x-api-key`` header with APIPassword (method 1), or
  HMAC-SHA256 signed handshake URL (method 2)
"""

import asyncio
import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import quote, urlsplit, urlunsplit

import websockets
from websockets.asyncio.client import ClientConnection

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class SuperSmartTTSService:
    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        api_password: str,
        base_url: str,
        auth_method: int = 1,
    ) -> None:
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_password = api_password
        self.base_url = base_url
        self.auth_method = auth_method

    @property
    def configured(self) -> bool:
        if self.auth_method == 1:
            return bool(self.app_id and self.api_password)
        return bool(self.app_id and self.api_key and self.api_secret)

    def build_headers(self) -> dict[str, str] | None:
        if self.auth_method == 1:
            return {"x-api-key": self.api_password}
        return None

    def build_url(self) -> str:
        if not self.configured:
            raise RuntimeError("iFlytek Super Smart TTS is not configured")
        if self.auth_method == 1:
            return self.base_url
        parts = urlsplit(self.base_url)
        date = format_datetime(datetime.now(UTC), usegmt=True)
        signature_origin = (
            f"host: {parts.netloc}\ndate: {date}\nGET {parts.path} HTTP/1.1"
        )
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode("utf-8"),
                signature_origin.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")
        query = (
            f"authorization={quote(authorization)}"
            f"&date={quote(date)}&host={parts.netloc}"
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: int = 50,
        volume: int = 50,
        pitch: int = 50,
        sample_rate: int | None = None,
        oral_level: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize the whole ``text`` in a single frame and stream audio back."""
        if not self.configured:
            raise RuntimeError("iFlytek Super Smart TTS is not configured")

        text = _prepare_text(text, settings.IFLYTEK_SMART_TTS_MAX_BYTES)
        frame = _build_frame(
            app_id=self.app_id,
            text=text,
            status=2,
            seq=0,
            voice=voice or settings.IFLYTEK_SMART_TTS_VOICE,
            speed=speed,
            volume=volume,
            pitch=pitch,
            sample_rate=sample_rate or settings.IFLYTEK_SMART_TTS_SAMPLE_RATE,
            oral_level=oral_level,
        )
        async with websockets.connect(
            self.build_url(), additional_headers=self.build_headers()
        ) as ws:
            await ws.send(json.dumps(frame, ensure_ascii=False))
            async for chunk in _recv_audio(ws):
                yield chunk

    async def synthesize_stream(
        self,
        chunks: AsyncIterator[str],
        voice: str | None = None,
        speed: int = 50,
        volume: int = 50,
        pitch: int = 50,
        sample_rate: int | None = None,
        oral_level: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize incrementally: text frames (status 0/1) then a status=2
        end frame, while audio is streamed back over the same session."""
        if not self.configured:
            raise RuntimeError("iFlytek Super Smart TTS is not configured")

        voice = voice or settings.IFLYTEK_SMART_TTS_VOICE
        sample_rate = sample_rate or settings.IFLYTEK_SMART_TTS_SAMPLE_RATE
        max_bytes = settings.IFLYTEK_SMART_TTS_MAX_BYTES

        audio_q: asyncio.Queue[bytes | None] = asyncio.Queue()

        async with websockets.connect(
            self.build_url(), additional_headers=self.build_headers()
        ) as ws:
            receiver = asyncio.create_task(_pump_audio(ws, audio_q))
            try:
                seq = 0
                frame_status = 0
                pending: str | None = None
                async for piece in chunks:
                    if not piece:
                        continue
                    if pending is not None:
                        await ws.send(
                            json.dumps(
                                _build_frame(
                                    app_id=self.app_id,
                                    text=_prepare_text(pending, max_bytes),
                                    status=frame_status,
                                    seq=seq,
                                    voice=voice,
                                    speed=speed,
                                    volume=volume,
                                    pitch=pitch,
                                    sample_rate=sample_rate,
                                    oral_level=oral_level,
                                ),
                                ensure_ascii=False,
                            )
                        )
                        seq += 1
                        frame_status = 1
                    pending = piece
                await ws.send(
                    json.dumps(
                        _build_frame(
                            app_id=self.app_id,
                            text=_prepare_text(pending or "", max_bytes),
                            status=2,
                            seq=seq,
                            voice=voice,
                            speed=speed,
                            volume=volume,
                            pitch=pitch,
                            sample_rate=sample_rate,
                            oral_level=oral_level,
                        ),
                        ensure_ascii=False,
                    )
                )
                while True:
                    item = await audio_q.get()
                    if item is None:
                        break
                    yield item
            finally:
                receiver.cancel()


async def _pump_audio(
    ws: ClientConnection,
    audio_q: asyncio.Queue[bytes | None],
) -> None:
    try:
        async for chunk in _recv_audio(ws):
            await audio_q.put(chunk)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("smart tts receive failed: %s", exc)
        await audio_q.put(None)
    else:
        await audio_q.put(None)


async def _recv_audio(ws: ClientConnection) -> AsyncIterator[bytes]:
    while True:
        message = json.loads(await ws.recv())
        header = message.get("header") or {}
        code = header.get("code", 0)
        if code != 0:
            raise RuntimeError(
                f"iFlytek Super Smart TTS error {code}: {header.get('message')} "
                f"sid={header.get('sid')}"
            )
        payload = message.get("payload") or {}
        audio = payload.get("audio") or {}
        data = audio.get("audio")
        if data:
            yield base64.b64decode(data)
        if audio.get("status") == 2:
            break


def _build_frame(
    *,
    app_id: str,
    text: str,
    status: int,
    seq: int,
    voice: str,
    speed: int,
    volume: int,
    pitch: int,
    sample_rate: int,
    oral_level: str | None,
) -> dict[str, object]:
    tts: dict[str, object] = {
        "vcn": voice,
        "speed": speed,
        "volume": volume,
        "pitch": pitch,
        "bgs": 0,
        "reg": 0,
        "rdn": 0,
        "rhy": 0,
        "audio": {
            "encoding": "lame",
            "sample_rate": sample_rate,
            "channels": 1,
            "bit_depth": 16,
            "frame_size": 0,
        },
    }
    parameter: dict[str, object] = {"tts": tts}
    if oral_level:
        parameter["oral"] = {
            "oral_level": oral_level,
            "spark_assist": 1,
            "stop_split": 0,
            "remain": 0,
        }
    return {
        "header": {"app_id": app_id, "status": status},
        "parameter": parameter,
        "payload": {
            "text": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "plain",
                "status": status,
                "seq": seq,
                "text": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            }
        },
    }


def _prepare_text(text: str, max_bytes: int) -> str:
    if len(text.encode("utf-8")) > max_bytes:
        logger.warning(
            "smart tts text too long (%d bytes), truncating to %d bytes",
            len(text.encode("utf-8")),
            max_bytes,
        )
        return _truncate_to_bytes(text, max_bytes)
    return text


def _truncate_to_bytes(text: str, max_bytes: int) -> str:
    size = 0
    for i, ch in enumerate(text):
        size += len(ch.encode("utf-8"))
        if size > max_bytes:
            return text[:i]
    return text


def _build_default_service() -> SuperSmartTTSService:
    return SuperSmartTTSService(
        app_id=settings.IFLYTEK_SMART_TTS_APP_ID,
        api_key=settings.IFLYTEK_SMART_TTS_API_KEY,
        api_secret=settings.IFLYTEK_SMART_TTS_API_SECRET,
        api_password=settings.IFLYTEK_SMART_TTS_API_PASSWORD,
        base_url=settings.IFLYTEK_SMART_TTS_URL,
        auth_method=settings.IFLYTEK_SMART_TTS_AUTH_METHOD,
    )


smart_tts_service = _build_default_service()
