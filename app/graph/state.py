from __future__ import annotations

from typing import TypedDict


class FileAttachment(TypedDict):
    """Represents a file attached to a chat message."""

    file_path: str  # Path in Supabase Storage
    file_type: str  # MIME type (e.g. "image/jpeg", "application/pdf")


class ConversationState(TypedDict):
    """State flowing through the LangGraph conversation graph."""

    # Identity
    user_id: str
    conversation_id: str
    language: str  # "en" | "ar"

    # Current request
    current_message: str  # The user's text message
    current_file: FileAttachment | None  # Attached file (path + mime type)

    # Conversation context
    messages: list[dict]  # Last 20 messages in the conversation
    last_analysis: dict | None  # Most recent analysis result in this conversation
    last_analysis_type: str | None  # "skin" | "report"

    # Ambient memory from past interactions
    summary_context: str  # Digest of past analyses/conversations
    cycle_context: str  # Menstrual cycle phase and prediction context

    # Output
    response_chunks: list[str]  # Accumulated response text chunks
    analysis_meta: dict | None  # analysis_type + analysis_id if analysis was triggered
    error: str | None  # Error message if something went wrong
