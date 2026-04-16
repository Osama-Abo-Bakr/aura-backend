from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: UUID | None = Field(
        default=None,
        description="Omit to start a new conversation.",
    )
    language: Literal["ar", "en"] = "ar"


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    role: Literal["assistant"]
    content: str
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str | None = None
    language: Literal["ar", "en"]
    message_count: int = 0
    last_message_at: datetime | None = None
    created_at: datetime
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}
