"""Pydantic DTOs for the iFlytek Super Smart TTS endpoints."""

from pydantic import BaseModel, Field

from app.models.tts import TTS_SPEED_MAX, TTS_SPEED_MIN

ORAL_LEVELS = ("high", "mid", "low")


class SmartTtsStreamRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    voice: str | None = Field(default=None)
    speed: int = Field(default=50, ge=TTS_SPEED_MIN, le=TTS_SPEED_MAX)
    volume: int = Field(default=50, ge=TTS_SPEED_MIN, le=TTS_SPEED_MAX)
    pitch: int = Field(default=50, ge=TTS_SPEED_MIN, le=TTS_SPEED_MAX)
    sample_rate: int | None = Field(default=None, ge=8000, le=24000)
    oral_level: str | None = Field(default=None, pattern="^(high|mid|low)$")
