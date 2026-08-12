from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Profile(BaseModel):
    nickname: str = ""


class ApiResult(BaseModel):
    code: int = 0
    data: dict[str, Any] | None = None
    message: str = "ok"
