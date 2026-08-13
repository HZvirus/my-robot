from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.api.routes import smart_tts as smart_tts_route
from app.api.routes.smart_tts import _decode_text_line
from app.main import app
from app.services.smart_tts_service import (
    SuperSmartTTSService,
    _truncate_to_bytes,
)

client = TestClient(app)


class FakeSmartTTSService:
    def __init__(
        self,
        chunks: list[bytes] | None = None,
        error: str | None = None,
        audio_frames: dict | None = None,
    ) -> None:
        self.chunks = chunks or [b"\xff\xfb\x01\x02\x03"]
        self.error = error
        self.audio_frames = audio_frames

    async def synthesize(
        self, text: str, voice: str | None = None, speed: int = 50,
        volume: int = 50, pitch: int = 50, sample_rate: int | None = None,
        oral_level: str | None = None,
    ) -> AsyncIterator[bytes]:
        if self.error:
            raise RuntimeError(self.error)
        for chunk in self.chunks:
            yield chunk

    async def synthesize_stream(
        self, chunks: AsyncIterator[str], voice: str | None = None, speed: int = 50,
        volume: int = 50, pitch: int = 50, sample_rate: int | None = None,
        oral_level: str | None = None,
    ) -> AsyncIterator[bytes]:
        if self.error:
            raise RuntimeError(self.error)
        for chunk in self.chunks:
            yield chunk


def _patch_service(monkeypatch, fake: FakeSmartTTSService) -> None:
    monkeypatch.setattr(smart_tts_route, "smart_tts_service", fake)


def _service(auth_method: int = 1) -> SuperSmartTTSService:
    return SuperSmartTTSService(
        app_id="a",
        api_key="b",
        api_secret="c",
        api_password="pw",
        base_url="wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6",
        auth_method=auth_method,
    )


def test_truncate_to_bytes_respects_limit() -> None:
    text = "汉字汉字汉字"
    assert _truncate_to_bytes(text, 7) == "汉字"


def test_auth_method1_uses_raw_url_and_api_key_header() -> None:
    svc = _service(auth_method=1)
    assert svc.build_url() == "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
    assert svc.build_headers() == {"x-api-key": "pw"}


def test_auth_method2_signs_url_without_header() -> None:
    svc = _service(auth_method=2)
    url = svc.build_url()
    assert url.startswith("wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6?")
    assert "authorization=" in url
    assert "&date=" in url
    assert "&host=cbm01.cn-huabei-1.xf-yun.com" in url
    assert svc.build_headers() is None


def test_smart_tts_stream_yields_audio(monkeypatch) -> None:
    _patch_service(monkeypatch, FakeSmartTTSService(chunks=[b"\xff\xfb\x01", b"\x02\x03"]))
    response = client.post(
        "/api/smart-tts/stream",
        json={"text": "你好", "voice": "x6_lingxiaoxuan_flow"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "data: " in body
    assert "data: [DONE]" in body


def test_smart_tts_stream_error_yields_error_event(monkeypatch) -> None:
    _patch_service(monkeypatch, FakeSmartTTSService(error="boom"))
    response = client.post("/api/smart-tts/stream", json={"text": "你好"})
    assert response.status_code == 200
    assert '"error": "boom"' in response.text


def test_smart_tts_stream_rejects_empty_text() -> None:
    response = client.post("/api/smart-tts/stream", json={"text": ""})
    assert response.status_code == 422


def test_smart_tts_stream_text_yields_audio(monkeypatch) -> None:
    _patch_service(monkeypatch, FakeSmartTTSService(chunks=[b"\xff\xfb\x01"]))
    response = client.post(
        "/api/smart-tts/stream-text",
        content='{"text": "你"}\n{"text": "好"}\n'.encode(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert "data: " in response.text
    assert "data: [DONE]" in response.text


def test_decode_text_line_handles_plain_and_json() -> None:
    assert _decode_text_line(b"hello") == "hello"
    assert _decode_text_line('{"text": "你好"}'.encode()) == "你好"
    assert _decode_text_line(b'"raw string"') == '"raw string"'
