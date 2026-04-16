"""
RED phase tests for /api/v1/analysis/* endpoints.

These tests verify input validation, auth requirements,
and error response shapes for the analysis routes.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import status

# ---------------------------------------------------------------------------
# Token helper
# ---------------------------------------------------------------------------

TEST_SECRET = "test-jwt-secret-32chars-padding!!"


def _make_token(sub: str | None = None, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now - 10,
        "exp": now - 1 if expired else now + 3600,
    }
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers():
    """Valid auth headers for a test user."""
    token = _make_token(sub=str(uuid.uuid4()))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_supabase_admin():
    """Fake supabase admin client that never hits the network."""
    mock = MagicMock()
    mock.table.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=[], count=0)
    return mock


@pytest.fixture
def client(mock_supabase_admin):
    """
    FastAPI TestClient with all external deps mocked:
    - Settings env vars patched before import
    - supabase_admin table() returns a no-op chain
    """
    from fastapi.testclient import TestClient

    with patch("app.db.supabase.supabase_admin", mock_supabase_admin), \
         patch("app.core.config.settings") as mock_settings:
        # Configure the mocked settings with valid values
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test-service-role-key"
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        mock_settings.GEMINI_API_KEY = "test-gemini-key"
        mock_settings.REDIS_URL = "redis://localhost:6379"
        mock_settings.SENTRY_DSN = ""
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        mock_settings.ENVIRONMENT = "testing"

        from app.main import app
        yield TestClient(app)


# ---------------------------------------------------------------------------
# RED TEST 1: upload-url rejects invalid content type
# ---------------------------------------------------------------------------

def test_upload_url_rejects_invalid_content_type(client, auth_headers):
    """
    When a user POSTs /api/v1/analysis/upload-url with an unsupported
    content type, the endpoint must return 422 with a structured error
    payload that includes the allowed list.
    """
    response = client.post(
        "/api/v1/analysis/upload-url",
        json={
            "file_name": "malware.exe",
            "content_type": "application/x-executable",
        },
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data
    # The error may be in detail directly or nested
    detail = data["detail"]
    if isinstance(detail, dict):
        assert detail.get("error") == "unsupported_content_type"
        assert "allowed" in detail
        assert isinstance(detail["allowed"], list)
        assert "image/jpeg" in detail["allowed"]
    else:
        # Pydantic validation error format
        assert "unsupported_content_type" in str(detail)


# ---------------------------------------------------------------------------
# RED TEST 2: upload-url rejects empty filename
# ---------------------------------------------------------------------------

def test_upload_url_rejects_empty_filename(client, auth_headers):
    """
    When file_name is an empty string, the endpoint must return 422.
    """
    response = client.post(
        "/api/v1/analysis/upload-url",
        json={
            "file_name": "",
            "content_type": "image/jpeg",
        },
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# RED TEST 3: skin analysis requires auth (no token → 403)
# ---------------------------------------------------------------------------

def test_skin_analysis_requires_auth(client):
    """
    When no Authorization header is sent, the endpoint returns 403.
    """
    response = client.post(
        "/api/v1/analysis/skin",
        json={"file_path": "uploads/test.jpg", "language": "en"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# RED TEST 4: skin analysis rejects invalid language
# ---------------------------------------------------------------------------

def test_skin_analysis_rejects_invalid_language(client, auth_headers):
    """
    When language is not 'en' or 'ar', the endpoint returns 422.
    """
    response = client.post(
        "/api/v1/analysis/skin",
        json={"file_path": "uploads/test.jpg", "language": "fr"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# RED TEST 5: report analysis requires auth (no token → 403)
# ---------------------------------------------------------------------------

def test_report_analysis_requires_auth(client):
    """
    When no Authorization header is sent, the endpoint returns 403.
    """
    response = client.post(
        "/api/v1/analysis/report",
        json={"file_path": "uploads/report.pdf", "language": "en"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# RED TEST 6: status returns 404 for missing analysis
# ---------------------------------------------------------------------------

def test_status_returns_404_for_missing_analysis(client, auth_headers, mock_supabase_admin):
    """
    When polling a non-existent analysis ID, return 404 with error code.
    """
    fake_id = str(uuid.uuid4())

    # Configure mock to return no rows
    mock_resp = MagicMock()
    mock_resp.data = None
    mock_supabase_admin.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_resp

    response = client.get(
        f"/api/v1/analysis/{fake_id}/status",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    detail = data["detail"]
    if isinstance(detail, dict):
        assert detail.get("error") == "analysis_not_found"


# ---------------------------------------------------------------------------
# RED TEST 7: history paginates correctly
# ---------------------------------------------------------------------------

def test_history_paginates(client, auth_headers, mock_supabase_admin):
    """
    When no analyses exist, history returns empty list with total=0.
    """
    # Configure mock for count query
    count_resp = MagicMock()
    count_resp.count = 0

    # Configure mock for rows query
    rows_resp = MagicMock()
    rows_resp.data = []

    def table_side_effect(table_name):
        mock_tbl = MagicMock()
        if "id" in str(table_name):
            mock_tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_resp
        else:
            mock_tbl.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = rows_resp
        return mock_tbl

    mock_supabase_admin.table.side_effect = table_side_effect

    response = client.get(
        "/api/v1/analysis/history",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1