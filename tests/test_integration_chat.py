"""Integration tests for the unified chat endpoint."""

import pytest
from app.models.chat import ChatMessageRequest
from app.graph.nodes import router


class TestChatMessageRequest:
    """Test ChatMessageRequest model validation."""

    def test_text_only_message(self):
        req = ChatMessageRequest(content="Hello", language="en")
        assert not req.has_file()
        assert req.get_file_type_category() is None

    def test_message_with_image(self):
        req = ChatMessageRequest(
            content="Analyze this",
            language="en",
            file_path="user-123/test.jpg",
            file_type="image/jpeg",
        )
        assert req.has_file()
        assert req.get_file_type_category() == "image"

    def test_message_with_pdf(self):
        req = ChatMessageRequest(
            content="Explain this report",
            language="en",
            file_path="user-123/report.pdf",
            file_type="application/pdf",
        )
        assert req.has_file()
        assert req.get_file_type_category() == "pdf"

    def test_message_with_png(self):
        req = ChatMessageRequest(
            content="Check this spot",
            language="en",
            file_path="user-123/spot.png",
            file_type="image/png",
        )
        assert req.get_file_type_category() == "image"

    def test_message_with_unknown_file_type(self):
        req = ChatMessageRequest(
            content="What's this?",
            language="en",
            file_path="user-123/doc.docx",
            file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert req.has_file()
        assert req.get_file_type_category() is None

    def test_arabic_language_default(self):
        req = ChatMessageRequest(content="مرحبا")
        assert req.language == "ar"

    def test_english_language_explicit(self):
        req = ChatMessageRequest(content="Hello", language="en")
        assert req.language == "en"


class TestRouterLogic:
    """Test the deterministic router node."""

    def test_routes_text_to_chat(self):
        state = {"current_file": None, "current_message": "Hello"}
        assert router(state) == "chat"

    def test_routes_jpeg_to_skin(self):
        state = {
            "current_file": {"file_path": "x.jpg", "file_type": "image/jpeg"},
            "current_message": "What is this?",
        }
        assert router(state) == "skin"

    def test_routes_png_to_skin(self):
        state = {
            "current_file": {"file_path": "x.png", "file_type": "image/png"},
            "current_message": "Check this",
        }
        assert router(state) == "skin"

    def test_routes_webp_to_skin(self):
        state = {
            "current_file": {"file_path": "x.webp", "file_type": "image/webp"},
            "current_message": "Look",
        }
        assert router(state) == "skin"

    def test_routes_pdf_to_report(self):
        state = {
            "current_file": {"file_path": "x.pdf", "file_type": "application/pdf"},
            "current_message": "Explain this",
        }
        assert router(state) == "report"

    def test_routes_unknown_file_to_chat(self):
        state = {
            "current_file": {"file_path": "x.doc", "file_type": "application/msword"},
            "current_message": "What's this?",
        }
        assert router(state) == "chat"

    def test_routes_text_with_image_to_skin(self):
        state = {
            "current_file": {"file_path": "rash.jpg", "file_type": "image/jpeg"},
            "current_message": "I've had this rash for 3 days",
        }
        assert router(state) == "skin"


class TestSSEEventModels:
    """Test SSE event model serialization."""

    def test_content_event(self):
        from app.models.chat import ContentEvent

        event = ContentEvent(text="Hello there")
        assert event.type == "content"
        assert event.text == "Hello there"
        json_str = event.model_dump_json()
        assert "content" in json_str
        assert "Hello there" in json_str

    def test_analysis_meta_event(self):
        from app.models.chat import AnalysisMetaEvent

        event = AnalysisMetaEvent(analysis_type="skin", analysis_id="abc-123")
        assert event.type == "analysis_meta"
        assert event.analysis_type == "skin"

    def test_quota_error_event(self):
        from app.models.chat import QuotaErrorEvent

        event = QuotaErrorEvent(message="Quota exceeded", interaction_type="skin")
        assert event.type == "quota_error"
        assert event.interaction_type == "skin"

    def test_analysis_error_event(self):
        from app.models.chat import AnalysisErrorEvent

        event = AnalysisErrorEvent(message="Analysis failed")
        assert event.type == "analysis_error"
        assert event.message == "Analysis failed"
