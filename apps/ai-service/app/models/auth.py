'''Pydantic DTOs for device auth (camelCase JSON via aliases).'''

from pydantic import BaseModel, ConfigDict, Field


class DeviceAuthRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(..., min_length=16, max_length=128, alias='deviceId')


class DeviceAuthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias='userId')
