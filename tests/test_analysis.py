"""
Tests for /api/v1/analysis/* endpoints.

Covers input validation, auth requirements, and error responses
for upload-url and history routes.

Standalone /analysis/skin, /analysis/report, and /analysis/{id}/status
endpoints were removed in the LangGraph migration — skin and report
analysis is now handled through the unified /chat endpoint.
"""

from __future__ import annotations

import time
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


def test_upload_url_rejects_missing_analysis_type(client, auth_headers):
    """Missing required analysis_type field returns 422 from Pydantic."""
    response = client.post(
        "/api/v1/analysis/upload-url",
        json={"file_name": "photo.jpg", "content_type": "application/x-executable"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_upload_url_rejects_empty_filename(client, auth_headers):
    """Empty file_name returns 422 (Pydantic validation)."""
    response = client.post(
        "/api/v1/analysis/upload-url",
        json={"file_name": "", "content_type": "image/jpeg", "analysis_type": "skin"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_upload_url_requires_auth():
    """Upload-url endpoint requires authentication."""
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.post(
            "/api/v1/analysis/upload-url",
            json={"file_name": "photo.jpg", "content_type": "image/jpeg", "analysis_type": "skin"},
        )
    # Should be 403 Forbidden (auth dependency raises 403 for missing auth)
    assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# POST /analysis/skin  — endpoint removed, now via /chat
# ---------------------------------------------------------------------------


def test_skin_analysis_endpoint_removed():
    """The standalone /analysis/skin endpoint was removed in the LangGraph
    migration.  Skin analysis is now routed through /api/v1/chat."""
    with TestClient(app) as unauth_client:
        response = unauth_client.post(
            "/api/v1/analysis/skin",
            json={"file_path": "uploads/test.jpg", "language": "en"},
        )
    # Endpoint no longer exists → 404
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# POST /analysis/report  — endpoint removed, now via /chat
# ---------------------------------------------------------------------------


def test_report_analysis_endpoint_removed():
    """The standalone /analysis/report endpoint was removed in the LangGraph
    migration.  Report analysis is now routed through /api/v1/chat."""
    with TestClient(app) as unauth_client:
        response = unauth_client.post(
            "/api/v1/analysis/report",
            json={"file_path": "uploads/report.pdf", "language": "en"},
        )
    # Endpoint no longer exists → 404
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# GET /analysis/{id}/status  — endpoint removed
# ---------------------------------------------------------------------------


def test_status_endpoint_removed():
    """The standalone /analysis/{id}/status endpoint was removed in the
    LangGraph migration.  Analysis status is now tracked in the conversation
    history returned by /api/v1/chat."""
    with TestClient(app) as c:
        response = c.get("/api/v1/analysis/00000000-0000-0000-0000-000000000000/status")
    # Endpoint no longer exists → 404
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# GET /analysis/history
# ---------------------------------------------------------------------------


def test_history_returns_empty_for_no_analyses(client, auth_headers):
    """When no analyses exist, history returns empty list."""
    rows_resp = MagicMock()
    rows_resp.data = []

    with patch("app.api.v1.analysis.supabase_admin") as mock_admin:
        mock_chain = MagicMock()
        mock_chain.select.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.order.return_value = mock_chain
        mock_chain.range.return_value = mock_chain
        mock_chain.execute.return_value = rows_resp
        mock_admin.table.return_value = mock_chain

        response = client.get(
            "/api/v1/analysis/history",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "analyses" in data
    assert data["analyses"] == []
    assert data["page"] == 1
    assert data["limit"] == 10