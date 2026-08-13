from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.api.routes import tts as tts_route
from app.main import app
from app.services.tts_service import TTSService, _truncate_to_bytes

client = TestClient(app)


class FakeTTSService:
    def __init__(self, chunks: list[bytes] | None = None, error: str | None = None) -> None:
        self.chunks = chunks or [b"\xff\xfb\x01\x02\x03"]
        self.error = error

    async def synthesize(
        self, text: str, voice: str | None = None, speed: int = 50,
        volume: int = 50, pitch: int = 50,
    ) -> AsyncIterator[bytes]:
        if self.error:
            raise RuntimeError(self.error)
        for chunk in self.chunks:
            yield chunk


def _patch_service(monkeypatch, fake: FakeTTSService) -> None:
    monkeypatch.setattr(tts_route, "tts_service", fake)


def _service() -> TTSService:
    return TTSService(app_id="a", api_key="b", api_secret="c", base_url="wss://tts-api.xfyun.cn/v2/tts")


def test_truncate_to_bytes_respects_limit() -> None:
    text = "汉字汉字汉字"
    assert _truncate_to_bytes(text, 7) == "汉字"


def test_build_url_includes_auth_params() -> None:
    url = _service().build_url()
    assert url.startswith("wss://tts-api.xfyun.cn/v2/tts?authorization=")
    assert "&date=" in url
    assert "&host=tts-api.xfyun.cn" in url


def test_tts_stream_yields_audio(monkeypatch) -> None:
    _patch_service(monkeypatch, FakeTTSService(chunks=[b"\xff\xfb\x01", b"\x02\x03"]))
    response = client.post(
        "/api/tts/stream",
        json={"text": "你好", "voice": "xiaoyan"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "data: " in body
    assert "data: [DONE]" in body


def test_tts_stream_error_yields_error_event(monkeypatch) -> None:
    _patch_service(monkeypatch, FakeTTSService(error="boom"))
    response = client.post(
        "/api/tts/stream",
        json={"text": "你好"},
    )
    assert response.status_code == 200
    assert '"error": "boom"' in response.text


def test_tts_stream_rejects_empty_text() -> None:
    response = client.post("/api/tts/stream", json={"text": ""})
    assert response.status_code == 422
