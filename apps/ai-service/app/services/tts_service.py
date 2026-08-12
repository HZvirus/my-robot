"""iFlytek TTS service: synthesize speech via the Xfyun WebSocket API.

Implements the v2 TTS protocol:
- HMAC-SHA256 signed handshake URL (per-request, date-dependent)
- UTF-8 text split into frames of at most 8000 bytes
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
_SENTENCE_END = "。！？…；!?;"


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

    @staticmethod
    def split_text(text: str, max_bytes: int) -> list[str]:
        """Split text into frames of at most `max_bytes` UTF-8 bytes.

        Prefers cutting at sentence-ending punctuation; falls back to a
        byte-safe hard cut for sentences longer than the limit.
        """
        if not text:
            return []
        if len(text.encode("utf-8")) <= max_bytes:
            return [text]

        sentences: list[str] = []
        buf = ""
        for ch in text:
            buf += ch
            if ch in _SENTENCE_END:
                sentences.append(buf)
                buf = ""
        if buf:
            sentences.append(buf)

        frames: list[str] = []
        current = ""
        for sentence in sentences:
            if (
                current
                and len(current.encode("utf-8")) + len(sentence.encode("utf-8"))
                <= max_bytes
            ):
                current += sentence
                continue
            if current:
                frames.append(current)
                current = ""
            while len(sentence.encode("utf-8")) > max_bytes:
                cut = _truncate_to_bytes(sentence, max_bytes)
                frames.append(cut)
                sentence = sentence[len(cut) :]
            current = sentence
        if current:
            frames.append(current)
        return frames

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: int = 50,
        volume: int = 50,
        pitch: int = 50,
    ) -> AsyncIterator[bytes]:
        """Stream MP3 audio bytes for `text`, yielding chunks as they arrive."""
        if not self.configured:
            raise RuntimeError("iFlytek TTS is not configured")

        frames = self.split_text(text, settings.IFLYTEK_TTS_MAX_BYTES)
        url = self.build_url()

        async with websockets.connect(url) as ws:
            total = len(frames)
            for idx, frame in enumerate(frames):
                status = 2 if total == 1 else (1 if idx == total - 1 else 0)
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
                        "status": status,
                        "text": base64.b64encode(frame.encode("utf-8")).decode("ascii"),
                    },
                }
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
