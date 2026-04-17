from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="The user's message text")
    conversation_id: UUID | None = Field(None, description="Existing conversation ID (creates new if null)")
    language: Literal["ar", "en"] = Field("ar", description="Response language")
    file_path: str | None = Field(None, description="Path from signed URL upload (obtained via /analysis/upload-url)")
    file_type: str | None = Field(None, description="MIME type of the uploaded file (required if file_path is provided)")

    def has_file(self) -> bool:
        return self.file_path is not None

    def get_file_type_category(self) -> str | None:
        if not self.file_type:
            return None
        if self.file_type.startswith("image/"):
            return "image"
        if self.file_type == "application/pdf":
            return "pdf"
        return None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    message_id: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    file_path: str | None = None
    file_type: str | None = None
    analysis_id: str | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime


# SSE event models for structured streaming
class SSEEvent(BaseModel):
    """Base model for SSE events."""
    type: str


class ContentEvent(SSEEvent):
    type: str = "content"
    text: str


class AnalysisMetaEvent(SSEEvent):
    type: str = "analysis_meta"
    analysis_type: str  # "skin" | "report"
    analysis_id: str


class QuotaErrorEvent(SSEEvent):
    type: str = "quota_error"
    message: str
    interaction_type: str  # "skin" | "report" | "chat"


class AnalysisErrorEvent(SSEEvent):
    type: str = "analysis_error"
    message: str


class DoneEvent(SSEEvent):
    type: str = "done"
