"""Pydantic DTOs for the science-popularization endpoints (camelCase JSON via aliases)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScienceStreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, alias="conversationId")


class ScienceMessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    role: str
    content: str
    interrupted: bool = False
    created_at: datetime = Field(alias="createdAt")


class ScienceHistoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    messages: list[ScienceMessageOut]


class ScienceConversationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    created_at: datetime = Field(alias="createdAt")
    preview: str = ""
