"""Pydantic DTOs for device auth (camelCase JSON via aliases)."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.rbac import DEFAULT_ROLE


class DeviceAuthRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(..., min_length=16, max_length=128, alias="deviceId")
    role: str = Field(default=DEFAULT_ROLE)
    role_token: str | None = Field(default=None, alias="roleToken")


class DeviceAuthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    role: str = Field(default=DEFAULT_ROLE)
