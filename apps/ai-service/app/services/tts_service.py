"""iFlytek TTS service: synthesize speech via the Xfyun WebSocket API.

Implements the v2 TTS protocol:
- HMAC-SHA256 signed handshake URL (per-request, date-dependent)
- the whole text is sent in ONE frame (status=2); the v2 API does not accept
  incremental multi-frame text
- `aue=lame` (MP3) audio frames returned over the same WebSocket
"""

import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import quote

import websockets

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_IFLYTEK_HOST = "tts-api.xfyun.cn"
_IFLYTEK_PATH = "/v2/tts"


class TTSService:
    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        base_url: str,
    ) -> None:
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.api_key and self.api_secret)

    def build_url(self) -> str:
        if not self.configured:
            raise RuntimeError("iFlytek TTS is not configured")
        date = format_datetime(datetime.now(UTC), usegmt=True)
        signature_origin = (
            f"host: {_IFLYTEK_HOST}\ndate: {date}\nGET {_IFLYTEK_PATH} HTTP/1.1"
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
        return (
            f"{self.base_url}?authorization={quote(authorization)}"
            f"&date={quote(date)}&host={_IFLYTEK_HOST}"
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: int = 50,
        volume: int = 50,
        pitch: int = 50,
    ) -> AsyncIterator[bytes]:
        """Synthesize the whole `text` in one request and stream back MP3 audio.

        The text is sent as a single frame (status=2). Text longer than the
        API limit is truncated to `IFLYTEK_TTS_MAX_BYTES` bytes instead of
        being split across multiple requests.
        """
        if not self.configured:
            raise RuntimeError("iFlytek TTS is not configured")

        max_bytes = settings.IFLYTEK_TTS_MAX_BYTES
        if len(text.encode("utf-8")) > max_bytes:
            logger.warning(
                "tts text too long (%d bytes), truncating to %d bytes",
                len(text.encode("utf-8")),
                max_bytes,
            )
            text = _truncate_to_bytes(text, max_bytes)

        request = {
            "common": {"app_id": self.app_id},
            "business": {
                "aue": "lame",
                "sfl": 1,
                "tte": "UTF8",
                "vcn": voice or settings.IFLYTEK_TTS_VOICE,
                "speed": speed,
                "volume": volume,
                "pitch": pitch,
            },
            "data": {
                "status": 2,
                "text": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        }

        url = self.build_url()
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps(request, ensure_ascii=False))
            while True:
                raw = await ws.recv()
                message = json.loads(raw)
                code = message.get("code")
                if code != 0:
                    raise RuntimeError(
                        f"iFlytek TTS error {code}: {message.get('message')} "
                        f"sid={message.get('sid')}"
                    )
                data = message.get("data") or {}
                audio = data.get("audio")
                if audio:
                    yield base64.b64decode(audio)
                if data.get("status") == 2:
                    break


def _truncate_to_bytes(text: str, max_bytes: int) -> str:
    size = 0
    for i, ch in enumerate(text):
        size += len(ch.encode("utf-8"))
        if size > max_bytes:
            return text[:i]
    return text


def _build_default_service() -> TTSService:
    return TTSService(
        app_id=settings.IFLYTEK_APP_ID,
        api_key=settings.IFLYTEK_API_KEY,
        api_secret=settings.IFLYTEK_API_SECRET,
        base_url=settings.IFLYTEK_TTS_URL,
    )


tts_service = _build_default_service()
