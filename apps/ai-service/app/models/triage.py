"""Pydantic DTOs for the triage endpoints (camelCase JSON via aliases)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TriageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, alias="conversationId")


class DepartmentOut(BaseModel):
    id: str
    name: str
    category: str
    description: str


class TriageSource(BaseModel):
    file: str
    text: str
    scope: str = ""


class TriageMessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    role: str
    content: str
    sources: list[TriageSource] | None = None
    interrupted: bool = False
    created_at: datetime = Field(alias="createdAt")


class TriageHistoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    messages: list[TriageMessageOut]


class TriageConversationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    created_at: datetime = Field(alias="createdAt")
    preview: str = ""
