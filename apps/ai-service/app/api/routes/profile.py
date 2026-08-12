from fastapi import APIRouter

from app.models.schemas import ApiResult, Profile

router = APIRouter()

_profile = Profile(nickname="guest")


@router.get("/profile", response_model=ApiResult)
async def get_profile() -> ApiResult:
    return ApiResult(data=_profile.model_dump())


@router.put("/profile", response_model=ApiResult)
async def update_profile(payload: Profile) -> ApiResult:
    global _profile
    _profile = payload
    return ApiResult(data=_profile.model_dump())
