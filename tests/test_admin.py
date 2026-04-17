"""
Tests for /api/v1/admin/* endpoints.

Covers:
  - Stats, users, interactions, data-delete with admin auth
  - Non-admin rejection (403)
  - Unauthenticated rejection (403/401)
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.core.deps import get_current_user, require_admin
from app.core.config import settings

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
# Test users
# ---------------------------------------------------------------------------

TEST_ADMIN_USER = {
    "sub": "00000000-0000-0000-0000-00000000999",
    "email": "admin@aura.health",
    "role": "authenticated",
}

TEST_USER = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "email": "test@example.com",
    "role": "authenticated",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client():
    """TestClient with admin auth dependency overridden."""
    app.dependency_overrides[get_current_user] = lambda: TEST_ADMIN_USER
    app.dependency_overrides[require_admin] = lambda: TEST_ADMIN_USER
    # Also set ADMIN_EMAILS to include our test admin
    original = settings.ADMIN_EMAILS
    settings.ADMIN_EMAILS = "admin@aura.health"
    with TestClient(app) as c:
        yield c
    settings.ADMIN_EMAILS = original
    app.dependency_overrides.clear()


@pytest.fixture
def non_admin_client():
    """TestClient with a regular (non-admin) user."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    # require_admin is NOT overridden — should reject non-admin
    original = settings.ADMIN_EMAILS
    settings.ADMIN_EMAILS = "admin@aura.health"
    with TestClient(app) as c:
        yield c
    settings.ADMIN_EMAILS = original
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    """Valid auth headers for admin user."""
    token = _make_token(sub=TEST_ADMIN_USER["sub"])
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_supabase_chain(return_data, count=None):
    """Build a mock Supabase query chain that returns `return_data`."""
    rows_resp = MagicMock()
    rows_resp.data = return_data
    rows_resp.count = count

    mock_chain = MagicMock()
    mock_chain.insert.return_value = mock_chain
    mock_chain.select.return_value = mock_chain
    mock_chain.update.return_value = mock_chain
    mock_chain.delete.return_value = mock_chain
    mock_chain.upsert.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.neq.return_value = mock_chain
    mock_chain.ilike.return_value = mock_chain
    mock_chain.gte.return_value = mock_chain
    mock_chain.order.return_value = mock_chain
    mock_chain.range.return_value = mock_chain
    mock_chain.limit.return_value = mock_chain
    mock_chain.maybe_single.return_value = mock_chain
    mock_chain.execute.return_value = rows_resp
    return mock_chain, rows_resp


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


def test_admin_stats_returns_counts(admin_client):
    """Admin stats endpoint returns aggregate counts."""
    # We need multiple mock calls for each table.
    # We'll track call sequence via side_effect.
    with patch("app.api.v1.admin.supabase_admin") as mock_admin:
        # profiles count
        mock_admin.table.return_value = _mock_supabase_chain([], count=42)[0]
        # The stats endpoint queries multiple tables, so we need the chain
        # to return appropriate data for each query.
        # Since all queries go through mock_admin.table().select().execute(),
        # we can just use one chain that works for all.

        # For ai_interactions select(interaction_type)
        interactions_chain = _mock_supabase_chain(
            [
                {"interaction_type": "chat"},
                {"interaction_type": "chat"},
                {"interaction_type": "skin"},
                {"interaction_type": "report"},
            ],
            count=4,
        )[0]

        # For subscriptions select(tier) where status=active
        subs_chain = _mock_supabase_chain(
            [{"tier": "free"}, {"tier": "free"}, {"tier": "premium"}],
            count=3,
        )[0]
        # need .eq("status", "active") to return itself
        subs_chain.eq.return_value = subs_chain

        # General count chain for simple table counts
        count_chain = _mock_supabase_chain([], count=0)[0]

        # Track which table is being queried
        table_calls = []

        def table_side_effect(table_name):
            table_calls.append(table_name)
            if table_name == "ai_interactions":
                return interactions_chain
            if table_name == "subscriptions":
                return subs_chain
            # For simple count tables, return a chain with count
            chain = _mock_supabase_chain([], count=5)[0]
            return chain

        mock_admin.table.side_effect = table_side_effect

        response = admin_client.get("/api/v1/admin/stats")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "users" in data
    assert "conversations" in data
    assert "messages" in data
    assert "analyses" in data
    assert "cycle_entries" in data
    assert "health_logs" in data
    assert "ai_interactions" in data
    assert "subscriptions" in data
    # ai_interactions should have total
    assert "total" in data["ai_interactions"]


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------


def test_admin_users_returns_paginated_list(admin_client):
    """Admin users endpoint returns paginated user list."""
    users_data = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "email": "user1@example.com",
            "created_at": "2026-01-15T10:00:00+00:00",
        }
    ]

    with patch("app.api.v1.admin.supabase_admin") as mock_admin:
        # profiles query
        profile_chain = _mock_supabase_chain(users_data)[0]
        profile_chain.ilike.return_value = profile_chain

        # interaction count query
        interaction_chain = _mock_supabase_chain([], count=5)[0]

        call_count = [0]

        def table_side_effect(table_name):
            if table_name == "profiles":
                return profile_chain
            if table_name == "ai_interactions":
                return interaction_chain
            return _mock_supabase_chain([])[0]

        mock_admin.table.side_effect = table_side_effect

        response = admin_client.get("/api/v1/admin/users")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "users" in data
    assert "page" in data
    assert "limit" in data
    assert data["page"] == 1
    assert data["limit"] == 20


def test_admin_users_with_search(admin_client):
    """Admin users endpoint supports search filter."""
    with patch("app.api.v1.admin.supabase_admin") as mock_admin:
        profile_chain = _mock_supabase_chain([])[0]
        profile_chain.ilike.return_value = profile_chain

        mock_admin.table.return_value = profile_chain

        response = admin_client.get("/api/v1/admin/users?search=test@example.com")

    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# GET /admin/interactions
# ---------------------------------------------------------------------------


def test_admin_interactions_returns_daily_counts(admin_client):
    """Admin interactions endpoint returns daily interaction counts."""
    interaction_data = [
        {"created_at": "2026-04-15T10:00:00+00:00", "interaction_type": "chat"},
        {"created_at": "2026-04-15T11:00:00+00:00", "interaction_type": "chat"},
        {"created_at": "2026-04-15T12:00:00+00:00", "interaction_type": "skin"},
        {"created_at": "2026-04-16T10:00:00+00:00", "interaction_type": "chat"},
    ]

    with patch("app.api.v1.admin.supabase_admin") as mock_admin:
        chain = _mock_supabase_chain(interaction_data)[0]
        mock_admin.table.return_value = chain

        response = admin_client.get("/api/v1/admin/interactions?days=30")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "days" in data
    assert "daily" in data
    assert data["days"] == 30


# ---------------------------------------------------------------------------
# DELETE /admin/data/{user_id}
# ---------------------------------------------------------------------------


def test_admin_delete_user_data(admin_client):
    """Admin data delete clears user data from all tables."""
    test_user_id = "00000000-0000-0000-0000-000000000001"

    with patch("app.api.v1.admin.supabase_admin") as mock_admin:
        delete_chain = _mock_supabase_chain([])[0]

        mock_admin.table.return_value = delete_chain

        response = admin_client.delete(f"/api/v1/admin/data/{test_user_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["deleted"] is True
    assert data["user_id"] == test_user_id
    assert "tables_cleared" in data
    # All tables should be in the cleared list
    expected_tables = [
        "messages",
        "conversations",
        "menstrual_cycles",
        "health_logs",
        "analyses",
        "ai_interactions",
        "wellness_plans",
    ]
    for table in expected_tables:
        assert table in data["tables_cleared"]


# ---------------------------------------------------------------------------
# Non-admin rejection (403)
# ---------------------------------------------------------------------------


def test_admin_stats_rejects_non_admin(non_admin_client):
    """Admin stats endpoint rejects non-admin users with 403."""
    response = non_admin_client.get("/api/v1/admin/stats")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_users_rejects_non_admin(non_admin_client):
    """Admin users endpoint rejects non-admin users with 403."""
    response = non_admin_client.get("/api/v1/admin/users")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_interactions_rejects_non_admin(non_admin_client):
    """Admin interactions endpoint rejects non-admin users with 403."""
    response = non_admin_client.get("/api/v1/admin/interactions")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_delete_rejects_non_admin(non_admin_client):
    """Admin data delete endpoint rejects non-admin users with 403."""
    response = non_admin_client.delete("/api/v1/admin/data/some-user-id")
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Auth required (403/401)
# ---------------------------------------------------------------------------


def test_admin_endpoints_require_auth():
    """All admin endpoints require authentication (no token -> 403/401)."""
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        assert unauth_client.get("/api/v1/admin/stats").status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )
        assert unauth_client.get("/api/v1/admin/users").status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )
        assert unauth_client.get("/api/v1/admin/interactions").status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )
        assert unauth_client.delete("/api/v1/admin/data/some-id").status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )