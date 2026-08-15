'''Anonymous device auth: exchange a client-generated device token for a user id.'''

from anyio import to_thread
from fastapi import APIRouter, HTTPException

from app.models.auth import DeviceAuthRequest, DeviceAuthResponse
from app.services.auth_service import auth_service

router = APIRouter()


@router.post('/auth/device', response_model=DeviceAuthResponse)
async def auth_device(req: DeviceAuthRequest) -> DeviceAuthResponse:
    try:
        user_id = await to_thread.run_sync(auth_service.register_device, req.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeviceAuthResponse(userId=user_id)
