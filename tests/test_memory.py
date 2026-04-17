"""Tests for the memory service."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.memory import build_summary_context


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