"""Pydantic DTOs for the iFlytek TTS endpoint (camelCase JSON via aliases)."""

from pydantic import BaseModel, ConfigDict, Field

TTS_SPEED_MIN = 0
TTS_SPEED_MAX = 100


class TtsStreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(..., min_length=1, max_length=20000)
    voice: str | None = Field(default=None)
    speed: int = Field(default=50, ge=TTS_SPEED_MIN, le=TTS_SPEED_MAX)
    volume: int = Field(default=50, ge=TTS_SPEED_MIN, le=TTS_SPEED_MAX)
    pitch: int = Field(default=50, ge=TTS_SPEED_MIN, le=TTS_SPEED_MAX)
