"""Tests for LangGraph node functions."""

import pytest
from app.graph.state import ConversationState, FileAttachment
from app.graph.nodes import router, response_formatter


def make_state(**overrides) -> dict:
    """Create a default state dict with sensible defaults."""
    defaults = {
        "user_id": "user-123",
        "conversation_id": "conv-456",
        "language": "en",
        "current_message": "Hello",
        "current_file": None,
        "messages": [],
        "last_analysis": None,
        "last_analysis_type": None,
        "summary_context": "",
        "response_chunks": [],
        "analysis_meta": None,
        "error": None,
    }
    defaults.update(overrides)
    return defaults


class TestRouter:
    def test_routes_text_to_chat(self):
        state = make_state(current_message="How are you?", current_file=None)
        result = router(state)
        assert result == "chat"

    def test_routes_image_to_skin(self):
        state = make_state(
            current_message="What is this?",
            current_file={"file_path": "user-123/abc_skin.jpg", "file_type": "image/jpeg"},
        )
        result = router(state)
        assert result == "skin"

    def test_routes_pdf_to_report(self):
        state = make_state(
            current_message="Explain this report",
            current_file={"file_path": "user-123/abc_report.pdf", "file_type": "application/pdf"},
        )
        result = router(state)
        assert result == "report"

    def test_routes_image_with_text_to_skin(self):
        state = make_state(
            current_message="I've had this rash for 3 days",
            current_file={"file_path": "user-123/abc_rash.png", "file_type": "image/png"},
        )
        result = router(state)
        assert result == "skin"

    def test_routes_webp_to_skin(self):
        state = make_state(
            current_message="Check this",
            current_file={"file_path": "user-123/img.webp", "file_type": "image/webp"},
        )
        result = router(state)
        assert result == "skin"

    def test_routes_unknown_file_to_chat(self):
        state = make_state(
            current_message="What's this?",
            current_file={"file_path": "user-123/doc.doc", "file_type": "application/msword"},
        )
        result = router(state)
        assert result == "chat"


class TestResponseFormatter:
    def test_formats_chunks(self):
        state = make_state(response_chunks=["Hello", " there", "!"])
        result = response_formatter(state)
        assert result == {}

    def test_formats_with_analysis_meta(self):
        state = make_state(
            response_chunks=["Analysis complete"],
            analysis_meta={"analysis_type": "skin", "analysis_id": "abc-123"},
        )
        result = response_formatter(state)
        assert result == {}