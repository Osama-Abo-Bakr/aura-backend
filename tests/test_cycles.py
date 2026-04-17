"""
Tests for /api/v1/cycles/* endpoints.

Covers CRUD operations, prediction logic, and auth requirements.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
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

TEST_USER = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "email": "test@example.com",
    "role": "authenticated",
}


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
# Helpers
# ---------------------------------------------------------------------------


def _mock_supabase_chain(return_data):
    """Build a mock Supabase query chain that returns `return_data`."""
    rows_resp = MagicMock()
    rows_resp.data = return_data

    mock_chain = MagicMock()
    mock_chain.insert.return_value = mock_chain
    mock_chain.select.return_value = mock_chain
    mock_chain.update.return_value = mock_chain
    mock_chain.delete.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.neq.return_value = mock_chain
    mock_chain.order.return_value = mock_chain
    mock_chain.range.return_value = mock_chain
    mock_chain.limit.return_value = mock_chain
    mock_chain.maybe_single.return_value = mock_chain
    mock_chain.execute.return_value = rows_resp
    return mock_chain, rows_resp


# ---------------------------------------------------------------------------
# POST /cycles — create cycle entry
# ---------------------------------------------------------------------------


def test_create_cycle_entry(client, auth_headers):
    """Creating a cycle entry returns 200 with the created entry."""
    entry_data = {
        "start_date": "2026-04-01",
        "cycle_length": 28,
        "period_length": 5,
        "symptoms": ["cramps", "bloating"],
        "mood": 6,
        "notes": "Felt tired",
    }
    returned = [
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000001",
            "user_id": TEST_USER["sub"],
            "start_date": "2026-04-01",
            "end_date": None,
            "cycle_length": 28,
            "period_length": 5,
            "symptoms": ["cramps", "bloating"],
            "mood": 6,
            "notes": "Felt tired",
            "created_at": "2026-04-01T10:00:00+00:00",
            "updated_at": "2026-04-01T10:00:00+00:00",
        }
    ]

    mock_chain, _ = _mock_supabase_chain(returned)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        response = client.post("/api/v1/cycles", json=entry_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["start_date"] == "2026-04-01"
    assert data["symptoms"] == ["cramps", "bloating"]
    assert data["mood"] == 6


def test_create_cycle_entry_with_end_date(client, auth_headers):
    """Creating a cycle entry with end_date returns correctly."""
    entry_data = {
        "start_date": "2026-04-01",
        "end_date": "2026-04-05",
    }
    returned = [
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000002",
            "user_id": TEST_USER["sub"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "cycle_length": 28,
            "period_length": 5,
            "symptoms": [],
            "mood": None,
            "notes": None,
            "created_at": "2026-04-01T10:00:00+00:00",
            "updated_at": "2026-04-01T10:00:00+00:00",
        }
    ]

    mock_chain, _ = _mock_supabase_chain(returned)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        response = client.post("/api/v1/cycles", json=entry_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["end_date"] == "2026-04-05"


# ---------------------------------------------------------------------------
# GET /cycles — list user's cycles
# ---------------------------------------------------------------------------


def test_list_cycles_returns_entries(client, auth_headers):
    """List cycles returns entries for the authenticated user."""
    cycles_data = [
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000001",
            "user_id": TEST_USER["sub"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "cycle_length": 28,
            "period_length": 5,
            "symptoms": [],
            "mood": None,
            "notes": None,
            "created_at": "2026-04-01T10:00:00+00:00",
            "updated_at": "2026-04-01T10:00:00+00:00",
        }
    ]

    mock_chain, _ = _mock_supabase_chain(cycles_data)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        response = client.get("/api/v1/cycles", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_list_cycles_empty(client, auth_headers):
    """List cycles returns empty list when no entries exist."""
    mock_chain, _ = _mock_supabase_chain([])

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        response = client.get("/api/v1/cycles", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


# ---------------------------------------------------------------------------
# PUT /cycles/{cycle_id} — update cycle entry
# ---------------------------------------------------------------------------


def test_update_cycle_entry(client, auth_headers):
    """Updating a cycle entry returns 200 with the updated entry."""
    updated_data = [
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000001",
            "user_id": TEST_USER["sub"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-06",
            "cycle_length": 30,
            "period_length": 5,
            "symptoms": ["cramps"],
            "mood": 7,
            "notes": "Updated notes",
            "created_at": "2026-04-01T10:00:00+00:00",
            "updated_at": "2026-04-02T10:00:00+00:00",
        }
    ]

    # Mock for the ownership check + the update
    mock_chain_select, _ = _mock_supabase_chain(
        {"id": "aaaaaaaa-0000-0000-0000-000000000001", "user_id": TEST_USER["sub"]}
    )
    mock_chain_update, _ = _mock_supabase_chain(updated_data)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        # First call: select for ownership check; second call: update
        mock_admin.table.return_value = mock_chain_select
        # We need the select to return the ownership data, then update returns the updated row
        mock_chain_select.select.return_value = mock_chain_select
        mock_chain_select.eq.return_value = mock_chain_select
        mock_chain_select.maybe_single.return_value = mock_chain_select
        mock_chain_select.execute.return_value = MagicMock(
            data={
                "id": "aaaaaaaa-0000-0000-0000-000000000001",
                "user_id": TEST_USER["sub"],
            }
        )

        # Reset for the update call
        mock_admin.table.return_value = mock_chain_update

        response = client.put(
            "/api/v1/cycles/aaaaaaaa-0000-0000-0000-000000000001",
            json={"mood": 7, "notes": "Updated notes"},
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_200_OK


def test_update_cycle_entry_not_found(client, auth_headers):
    """Updating a non-existent cycle entry returns 404."""
    mock_chain, _ = _mock_supabase_chain(None)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        # Ownership check returns None
        mock_chain.maybe_single.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(data=None)

        response = client.put(
            "/api/v1/cycles/nonexistent-id",
            json={"mood": 7},
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# DELETE /cycles/{cycle_id} — delete cycle entry
# ---------------------------------------------------------------------------


def test_delete_cycle_entry(client, auth_headers):
    """Deleting a cycle entry returns 200 with {deleted: true}."""
    mock_chain, _ = _mock_supabase_chain(
        {"id": "aaaaaaaa-0000-0000-0000-000000000001", "user_id": TEST_USER["sub"]}
    )

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        mock_chain.select.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.maybe_single.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(
            data={
                "id": "aaaaaaaa-0000-0000-0000-000000000001",
                "user_id": TEST_USER["sub"],
            }
        )

        response = client.delete(
            "/api/v1/cycles/aaaaaaaa-0000-0000-0000-000000000001",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"deleted": True}


def test_delete_cycle_entry_not_found(client, auth_headers):
    """Deleting a non-existent cycle entry returns 404."""
    mock_chain, _ = _mock_supabase_chain(None)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        mock_chain.select.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.maybe_single.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(data=None)

        response = client.delete(
            "/api/v1/cycles/nonexistent-id",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# GET /cycles/prediction — predict next period and current phase
# ---------------------------------------------------------------------------


def test_prediction_returns_phase(client, auth_headers):
    """Prediction endpoint returns cycle phase info."""
    today = date.today()
    cycles_data = [
        {
            "id": "cccccccc-0000-0000-0000-000000000001",
            "user_id": TEST_USER["sub"],
            "start_date": (today - timedelta(days=5)).isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
            "cycle_length": 28,
            "period_length": 5,
            "symptoms": [],
            "mood": None,
            "notes": None,
            "created_at": "2026-03-27T10:00:00+00:00",
            "updated_at": "2026-03-27T10:00:00+00:00",
        },
        {
            "id": "cccccccc-0000-0000-0000-000000000002",
            "user_id": TEST_USER["sub"],
            "start_date": (today - timedelta(days=33)).isoformat(),
            "end_date": (today - timedelta(days=29)).isoformat(),
            "cycle_length": 28,
            "period_length": 5,
            "symptoms": [],
            "mood": None,
            "notes": None,
            "created_at": "2026-02-22T10:00:00+00:00",
            "updated_at": "2026-02-22T10:00:00+00:00",
        },
    ]

    mock_chain, _ = _mock_supabase_chain(cycles_data)

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        response = client.get("/api/v1/cycles/prediction", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "current_phase" in data
    assert "days_until_next" in data
    assert "next_period_start" in data
    assert "phase_description" in data


def test_prediction_no_cycles_returns_404(client, auth_headers):
    """Prediction with no cycle data returns 404."""
    mock_chain, _ = _mock_supabase_chain([])

    with patch("app.api.v1.cycles.supabase_admin") as mock_admin:
        mock_admin.table.return_value = mock_chain
        response = client.get("/api/v1/cycles/prediction", headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


def test_cycles_endpoints_require_auth():
    """All cycle endpoints require authentication (no token → 403/401)."""
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        # POST
        r = unauth_client.post("/api/v1/cycles", json={"start_date": "2026-04-01"})
        assert r.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )

        # GET list
        r = unauth_client.get("/api/v1/cycles")
        assert r.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )

        # GET prediction
        r = unauth_client.get("/api/v1/cycles/prediction")
        assert r.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )

        # PUT
        r = unauth_client.put("/api/v1/cycles/some-id", json={"mood": 5})
        assert r.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )

        # DELETE
        r = unauth_client.delete("/api/v1/cycles/some-id")
        assert r.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_create_cycle_invalid_mood(client, auth_headers):
    """Mood outside 1-10 range returns 422."""
    entry_data = {
        "start_date": "2026-04-01",
        "mood": 15,
    }
    response = client.post("/api/v1/cycles", json=entry_data, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_cycle_invalid_cycle_length(client, auth_headers):
    """Cycle length outside 14-45 range returns 422."""
    entry_data = {
        "start_date": "2026-04-01",
        "cycle_length": 5,
    }
    response = client.post("/api/v1/cycles", json=entry_data, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_cycle_missing_start_date(client, auth_headers):
    """Missing required start_date field returns 422."""
    entry_data = {
        "cycle_length": 28,
    }
    response = client.post("/api/v1/cycles", json=entry_data, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
