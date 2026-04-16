"""
Tests for /api/v1/analysis/* endpoints.

Covers input validation, auth requirements, and error responses
for upload-url, skin, report, status, and history routes.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.core.deps import get_current_user

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

TEST_USER = {"sub": "00000000-0000-0000-0000-000000000001", "email": "test@example.com", "role": "authenticated"}


@pytest.fixture
def client():
    """TestClient with auth dependency overridden."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Valid auth headers."""
    token = _make_token(sub=TEST_USER["sub"])
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /analysis/upload-url
# ---------------------------------------------------------------------------


def test_upload_url_rejects_invalid_content_type(client, auth_headers):
    """Unsupported content type returns 422 with structured error."""
    response = client.post(
        "/api/v1/analysis/upload-url",
        json={"file_name": "malware.exe", "content_type": "application/x-executable"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    detail = data.get("detail", data)
    if isinstance(detail, dict):
        assert detail.get("error") == "unsupported_content_type"
        assert "allowed" in detail
        assert "image/jpeg" in detail["allowed"]
    else:
        assert "unsupported_content_type" in str(detail) or "validation" in str(detail).lower()


def test_upload_url_rejects_empty_filename(client, auth_headers):
    """Empty file_name returns 422 (Pydantic validation)."""
    response = client.post(
        "/api/v1/analysis/upload-url",
        json={"file_name": "", "content_type": "image/jpeg"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# POST /analysis/skin
# ---------------------------------------------------------------------------


def test_skin_analysis_requires_auth():
    """Without auth, returns 403."""
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.post(
            "/api/v1/analysis/skin",
            json={"file_path": "uploads/test.jpg", "language": "en"},
        )
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_skin_analysis_rejects_invalid_language(client, auth_headers):
    """Language must be 'en' or 'ar' — anything else returns 422."""
    # Patch check_quota so the quota dependency doesn't hit supabase mock
    async def _skip_quota(interaction_type, current_user):
        pass

    with patch("app.core.deps.check_quota", side_effect=_skip_quota):
        response = client.post(
            "/api/v1/analysis/skin",
            json={"file_path": "uploads/test.jpg", "language": "fr"},
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# POST /analysis/report
# ---------------------------------------------------------------------------


def test_report_analysis_requires_auth():
    """Without auth, returns 403."""
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.post(
            "/api/v1/analysis/report",
            json={"file_path": "uploads/report.pdf", "language": "en"},
        )
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# GET /analysis/{id}/status
# ---------------------------------------------------------------------------


def test_status_returns_404_for_missing_analysis(client, auth_headers):
    """Polling a non-existent analysis ID returns 404 with error key."""
    fake_id = str(uuid.uuid4())

    mock_resp = MagicMock()
    mock_resp.data = None

    with patch("app.api.v1.analysis.supabase_admin") as mock_admin:
        mock_chain = MagicMock()
        mock_chain.select.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.maybe_single.return_value = mock_chain
        mock_chain.execute.return_value = mock_resp
        mock_admin.table.return_value = mock_chain

        response = client.get(
            f"/api/v1/analysis/{fake_id}/status",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    # Our custom error handler wraps dict detail into {error, message, request_id}
    assert data.get("error") == "analysis_not_found" or "analysis_not_found" in str(data)


# ---------------------------------------------------------------------------
# GET /analysis/history
# ---------------------------------------------------------------------------


def test_history_returns_empty_for_no_analyses(client, auth_headers):
    """When no analyses exist, history returns empty list with total=0."""
    call_count = {"n": 0}

    count_resp = MagicMock()
    count_resp.count = 0
    count_resp.data = []

    rows_resp = MagicMock()
    rows_resp.data = []

    def mock_table(table_name):
        mock_chain = MagicMock()
        if call_count["n"] == 0:
            call_count["n"] += 1
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.execute.return_value = count_resp
        else:
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.order.return_value = mock_chain
            mock_chain.range.return_value = mock_chain
            mock_chain.execute.return_value = rows_resp
        return mock_chain

    with patch("app.api.v1.analysis.supabase_admin") as mock_admin:
        mock_admin.table.side_effect = mock_table

        response = client.get(
            "/api/v1/analysis/history",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["items"] == []
    assert data["total"] == 0