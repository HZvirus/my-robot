"""iFlytek Super Smart TTS service (超拟人语音合成 WebSocket API).

Holds credentials and produces HMAC-SHA256 signed WebSocket URLs the
frontend can connect to directly. Streaming (text-in/audio-out) is done
client-side; no synthesis helper is exposed because no server-side
endpoint consumes it.
"""

import base64
import hashlib
import hmac
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import quote, urlsplit, urlunsplit

from app.core.config import settings


class SuperSmartTTSService:
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
        # WebSocket direct connect always uses HMAC-SHA256 signed URLs.
        self.auth_method = 2

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.api_key and self.api_secret)

    def build_url(self) -> str:
        if not self.configured:
            raise RuntimeError("iFlytek Super Smart TTS is not configured")
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


def _build_default_service() -> SuperSmartTTSService:
    return SuperSmartTTSService(
        app_id=settings.IFLYTEK_SMART_TTS_APP_ID,
        api_key=settings.IFLYTEK_SMART_TTS_API_KEY,
        api_secret=settings.IFLYTEK_SMART_TTS_API_SECRET,
        base_url=settings.IFLYTEK_SMART_TTS_URL,
    )


smart_tts_service = _build_default_service()
