"""Tests for the memory service."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.memory import build_summary_context, get_conversation_analysis


@pytest.fixture
def mock_supabase():
    """Mock the supabase_admin client for testing."""
    with patch("app.services.memory.supabase_admin") as mock:
        yield mock


@pytest.mark.asyncio
async def test_build_summary_context_with_skin_analysis(mock_supabase):
    """Test building context when user has a skin analysis."""
    # Mock analyses response
    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=[
        {"analysis_type": "skin", "result": {"concern": "mild acne"}, "created_at": "2026-04-15"},
    ])
    mock_supabase.table.return_value = mock_query

    result = await build_summary_context(user_id="user-123")
    assert "mild acne" in result
    assert "Skin analysis" in result


@pytest.mark.asyncio
async def test_build_summary_context_empty(mock_supabase):
    """Test building context when user has no history."""
    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value = mock_query

    result = await build_summary_context(user_id="user-123")
    assert result == ""


@pytest.mark.asyncio
async def test_get_conversation_analysis_with_analysis(mock_supabase):
    """Test fetching analysis from a conversation that has one."""
    # Mock messages query: find message with analysis_id
    msg_query = MagicMock()
    msg_query.select.return_value = msg_query
    msg_query.eq.return_value = msg_query
    msg_query.is_.return_value = msg_query
    msg_query.order.return_value = msg_query
    msg_query.limit.return_value = msg_query
    msg_query.execute.return_value = MagicMock(
        data=[{"analysis_id": "analysis-789"}]
    )

    # Mock analyses query: fetch the analysis record
    analysis_query = MagicMock()
    analysis_query.select.return_value = analysis_query
    analysis_query.eq.return_value = analysis_query
    analysis_query.execute.return_value = MagicMock(
        data=[{
            "analysis_type": "skin",
            "result": {"concern": "mild acne", "severity": "mild"},
        }]
    )

    # Route table calls: first call = messages, second call = analyses
    mock_supabase.table.side_effect = [
        msg_query,
        analysis_query,
    ]

    result, analysis_type = await get_conversation_analysis("conv-456", user_id="user-123")
    assert result == {"concern": "mild acne", "severity": "mild"}
    assert analysis_type == "skin"


@pytest.mark.asyncio
async def test_get_conversation_analysis_no_analysis(mock_supabase):
    """Test fetching analysis from a conversation that has none."""
    msg_query = MagicMock()
    msg_query.select.return_value = msg_query
    msg_query.eq.return_value = msg_query
    msg_query.is_.return_value = msg_query
    msg_query.order.return_value = msg_query
    msg_query.limit.return_value = msg_query
    msg_query.execute.return_value = MagicMock(data=[])

    mock_supabase.table.return_value = msg_query

    result, analysis_type = await get_conversation_analysis("conv-no-analysis", user_id="user-123")
    assert result is None
    assert analysis_type is None


@pytest.mark.asyncio
async def test_get_conversation_analysis_with_json_string_result(mock_supabase):
    """Test that JSON string result is parsed correctly."""
    msg_query = MagicMock()
    msg_query.select.return_value = msg_query
    msg_query.eq.return_value = msg_query
    msg_query.is_.return_value = msg_query
    msg_query.order.return_value = msg_query
    msg_query.limit.return_value = msg_query
    msg_query.execute.return_value = MagicMock(
        data=[{"analysis_id": "analysis-999"}]
    )

    analysis_query = MagicMock()
    analysis_query.select.return_value = analysis_query
    analysis_query.eq.return_value = analysis_query
    analysis_query.execute.return_value = MagicMock(
        data=[{
            "analysis_type": "report",
            "result": '{"summary": "Blood test results", "abnormal_flags": ["cholesterol"]}',
        }]
    )

    mock_supabase.table.side_effect = [msg_query, analysis_query]

    result, analysis_type = await get_conversation_analysis("conv-789", user_id="user-456")
    assert result == {"summary": "Blood test results", "abnormal_flags": ["cholesterol"]}
    assert analysis_type == "report"