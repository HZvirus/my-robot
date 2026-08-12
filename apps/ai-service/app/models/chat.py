"""Pydantic DTOs for the general chat endpoints (camelCase JSON via aliases)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, alias="conversationId")


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    role: str
    content: str
    interrupted: bool = False
    created_at: datetime = Field(alias="createdAt")


class ChatHistoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    messages: list[ChatMessageOut]


class ChatConversationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    created_at: datetime = Field(alias="createdAt")
    preview: str = ""
