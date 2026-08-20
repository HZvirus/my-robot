"""iFlytek Super Smart TTS endpoint used by the browser-direct WebSocket flow.

Only ``GET /api/smart-tts/ws-url`` is exposed: it returns a signed WebSocket
URL the browser can use to connect to iFlytek directly (HMAC-SHA256, auth
method 2). The browser-side ``streamSmartTtsWs`` calls this once, then opens
the signed WebSocket itself, so no server-side streaming endpoint is needed.
"""

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.core.rbac import Principal
from app.services.smart_tts_service import smart_tts_service

router = APIRouter()


@router.get("/smart-tts/ws-url")
async def smart_tts_ws_url(principal: Principal = CurrentUser) -> dict[str, str]:
    """Return a signed WebSocket URL the browser can connect to directly.

    Browsers cannot attach an x-api-key header during the WS handshake, so
    direct connect uses an HMAC-SHA256 signed URL (auth method 2). Signing is
    done server-side: the frontend never holds iFlytek credentials, it calls
    this endpoint to get {url, app_id} and then opens the WebSocket itself.
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
