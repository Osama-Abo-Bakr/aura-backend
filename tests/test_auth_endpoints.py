"""Tests for auth API endpoints (register, token, refresh, signout)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.deps import get_current_user
from app.services.auth import (
    AuthService,
    AuthTokens,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)


@pytest.fixture
def client():
    """TestClient with auth dependency overridden."""
    def _override():
        return {"sub": "test-user-uuid", "email": "test@example.com", "role": "authenticated"}

    app.dependency_overrides[get_current_user] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


@patch("app.api.v1.auth.AuthService")
def test_register_success(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.signup.return_value = {"id": "00000000-0000-0000-0000-000000000001", "email": "alice@example.com", "user_metadata": {"full_name": "Alice"}}
    resp = client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "securepassword",
        "full_name": "Alice",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data
    assert data["email"] == "alice@example.com"


@patch("app.api.v1.auth.AuthService")
def test_register_duplicate_email(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.signup.side_effect = DuplicateEmailError()
    resp = client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "securepassword",
        "full_name": "Alice",
    })
    assert resp.status_code == 400


@patch("app.api.v1.auth.AuthService")
def test_register_short_password(MockAuthService, client):
    """Passwords under 8 chars should be rejected by Pydantic validation."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "short",
        "full_name": "Alice",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/token
# ---------------------------------------------------------------------------


@patch("app.api.v1.auth.AuthService")
def test_token_success(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.signin.return_value = AuthTokens(access_token="tok_abc", refresh_token="ref_xyz", expires_in=3600)
    resp = client.post("/api/v1/auth/token", json={
        "email": "alice@example.com",
        "password": "securepassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "tok_abc"
    assert data["refresh_token"] == "ref_xyz"
    assert data["token_type"] == "bearer"


@patch("app.api.v1.auth.AuthService")
def test_token_invalid_credentials(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.signin.side_effect = InvalidCredentialsError()
    resp = client.post("/api/v1/auth/token", json={
        "email": "alice@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


@patch("app.api.v1.auth.AuthService")
def test_refresh_success(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.refresh_token.return_value = AuthTokens(access_token="new_tok", refresh_token="new_ref", expires_in=3600)
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "old_refresh_token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "new_tok"


@patch("app.api.v1.auth.AuthService")
def test_refresh_invalid_token(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.refresh_token.side_effect = InvalidRefreshTokenError()
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad_token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/signout
# ---------------------------------------------------------------------------


@patch("app.api.v1.auth.AuthService")
def test_signout_success(MockAuthService, client):
    svc = MockAuthService.return_value
    svc.signout.return_value = None
    resp = client.post("/api/v1/auth/signout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Signed out successfully"


def test_signout_requires_auth():
    """Signout endpoint should require authentication."""
    from fastapi.testclient import TestClient
    # No dependency override — should fail without auth
    with TestClient(app) as c:
        resp = c.post("/api/v1/auth/signout")
        assert resp.status_code in (401, 403)