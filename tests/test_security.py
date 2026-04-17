"""
Unit tests for JWT verification logic (app/core/security.py).
No network calls — we sign tokens locally with the same secret.
"""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from fastapi import HTTPException

# Use a predictable secret for tests
TEST_SECRET = "test-jwt-secret-32chars-padding!!"


def _make_token(
    sub: str | None = None,
    role: str = "authenticated",
    expired: bool = False,
    audience: str = "authenticated",
    secret: str = TEST_SECRET,
) -> str:
    now = int(time.time())
    payload: dict = {
        "aud": audience,
        "role": role,
        "iat": now - 10,
        "exp": now - 1 if expired else now + 3600,
    }
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Override settings so tests don't need a real .env."""
    import app.core.security as sec_module
    import app.core.config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    # Re-import to pick up patched settings
    import importlib

    importlib.reload(sec_module)
    yield


def test_valid_token_returns_payload():
    from app.core.security import verify_supabase_jwt

    user_id = str(uuid.uuid4())
    token = _make_token(sub=user_id)
    payload = verify_supabase_jwt(token)
    assert payload["sub"] == user_id


def test_expired_token_raises_401():
    from app.core.security import verify_supabase_jwt

    token = _make_token(sub=str(uuid.uuid4()), expired=True)
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_wrong_audience_raises_401():
    from app.core.security import verify_supabase_jwt

    token = _make_token(sub=str(uuid.uuid4()), audience="anon")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_wrong_secret_raises_401():
    from app.core.security import verify_supabase_jwt

    token = _make_token(sub=str(uuid.uuid4()), secret="wrong-secret-padding-xxxxxxxxx!")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_missing_sub_raises_401():
    from app.core.security import verify_supabase_jwt

    token = _make_token(sub=None)  # no sub claim
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_non_uuid_sub_raises_401():
    from app.core.security import verify_supabase_jwt

    token = _make_token(sub="not-a-uuid")
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_malformed_token_raises_401():
    from app.core.security import verify_supabase_jwt

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt("this.is.garbage")
    assert exc_info.value.status_code == 401
