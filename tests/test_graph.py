"""Tests for LangGraph node functions."""

import pytest
from unittest.mock import patch, MagicMock
from app.graph.state import ConversationState, FileAttachment
from app.graph.nodes import router, response_formatter, memory_injection


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
            current_file={
                "file_path": "user-123/abc_skin.jpg",
                "file_type": "image/jpeg",
            },
        )
        result = router(state)
        assert result == "skin"

    def test_routes_pdf_to_report(self):
        state = make_state(
            current_message="Explain this report",
            current_file={
                "file_path": "user-123/abc_report.pdf",
                "file_type": "application/pdf",
            },
        )
        result = router(state)
        assert result == "report"

    def test_routes_image_with_text_to_skin(self):
        state = make_state(
            current_message="I've had this rash for 3 days",
            current_file={
                "file_path": "user-123/abc_rash.png",
                "file_type": "image/png",
            },
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
            current_file={
                "file_path": "user-123/doc.doc",
                "file_type": "application/msword",
            },
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


class TestMemoryInjection:
    @pytest.mark.asyncio
    async def test_injects_analysis_when_present(self):
        """memory_injection populates last_analysis when conversation has an analysis."""
        mock_analysis = {"concern": "mild acne", "severity": "mild"}

        state = {
            "user_id": "user-123",
            "conversation_id": "conv-456",
            "language": "en",
            "current_message": "Tell me more about this",
            "current_file": None,
            "messages": [],
            "last_analysis": None,
            "last_analysis_type": None,
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        async def mock_summary(user_id):
            return "Skin analysis: mild acne"

        def mock_cycle(user_id):
            return "Cycle: follicular phase"

        async def mock_conv_analysis(conv_id, uid):
            return (mock_analysis, "skin")

        with (
            patch("app.graph.nodes.build_summary_context", side_effect=mock_summary),
            patch("app.graph.nodes.build_cycle_context", side_effect=mock_cycle),
            patch(
                "app.graph.nodes.get_conversation_analysis",
                side_effect=mock_conv_analysis,
            ),
        ):
            result = await memory_injection(state)

        assert result["last_analysis"] == mock_analysis
        assert result["last_analysis_type"] == "skin"
        assert result["summary_context"] == "Skin analysis: mild acne"
        assert result["cycle_context"] == "Cycle: follicular phase"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_analysis(self):
        """memory_injection does not overwrite last_analysis if state already has one."""
        existing_analysis = {"concern": "eczema", "severity": "moderate"}

        state = {
            "user_id": "user-123",
            "conversation_id": "conv-456",
            "language": "en",
            "current_message": "Tell me more",
            "current_file": None,
            "messages": [],
            "last_analysis": existing_analysis,
            "last_analysis_type": "skin",
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        async def mock_summary(user_id):
            return ""

        def mock_cycle(user_id):
            return ""

        async def mock_conv_analysis(conv_id, uid):
            return ({"concern": "different"}, "report")

        with (
            patch("app.graph.nodes.build_summary_context", side_effect=mock_summary),
            patch("app.graph.nodes.build_cycle_context", side_effect=mock_cycle),
            patch(
                "app.graph.nodes.get_conversation_analysis",
                side_effect=mock_conv_analysis,
            ),
        ):
            result = await memory_injection(state)

        # Should NOT contain last_analysis because state already has one
        assert "last_analysis" not in result
        assert "last_analysis_type" not in result

    @pytest.mark.asyncio
    async def test_no_analysis_in_conversation(self):
        """memory_injection works fine when conversation has no analysis."""
        state = {
            "user_id": "user-123",
            "conversation_id": "conv-no-analysis",
            "language": "en",
            "current_message": "Hello",
            "current_file": None,
            "messages": [],
            "last_analysis": None,
            "last_analysis_type": None,
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        async def mock_summary(user_id):
            return "No past analyses"

        def mock_cycle(user_id):
            return ""

        async def mock_conv_analysis(conv_id, uid):
            return (None, None)

        with (
            patch("app.graph.nodes.build_summary_context", side_effect=mock_summary),
            patch("app.graph.nodes.build_cycle_context", side_effect=mock_cycle),
            patch(
                "app.graph.nodes.get_conversation_analysis",
                side_effect=mock_conv_analysis,
            ),
        ):
            result = await memory_injection(state)

        assert "last_analysis" not in result
        assert "last_analysis_type" not in result
        assert result["summary_context"] == "No past analyses"
