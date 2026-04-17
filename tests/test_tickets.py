"""Tests for the tickets API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.deps import get_current_user


FAKE_USER = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "email": "test@example.com",
    "role": "authenticated",
}


@pytest.fixture
def client():
    """TestClient with auth dependency overridden."""

    def _override():
        return FAKE_USER

    app.dependency_overrides[get_current_user] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/tickets — Create
# ---------------------------------------------------------------------------


@patch("app.api.v1.tickets.supabase_admin")
def test_create_ticket_success(mock_admin, client):
    mock_admin.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "00000000-0000-0000-0000-000000000001",
                "subject": "Issue with app",
                "description": "The app crashes on startup",
                "status": "open",
                "priority": "medium",
                "created_at": "2026-04-16T00:00:00+00:00",
                "updated_at": "2026-04-16T00:00:00+00:00",
            }
        ]
    )
    resp = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Issue with app",
            "description": "The app crashes on startup",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["subject"] == "Issue with app"
    assert data["status"] == "open"


@patch("app.api.v1.tickets.supabase_admin")
def test_create_ticket_with_priority(mock_admin, client):
    mock_admin.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "00000000-0000-0000-0000-000000000001",
                "subject": "Urgent bug",
                "description": "Critical issue",
                "status": "open",
                "priority": "high",
                "created_at": "2026-04-16T00:00:00+00:00",
                "updated_at": "2026-04-16T00:00:00+00:00",
            }
        ]
    )
    resp = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Urgent bug",
            "description": "Critical issue",
            "priority": "high",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["priority"] == "high"


def test_create_ticket_invalid_priority(client):
    """Priority must be one of low/medium/high."""
    resp = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Test",
            "description": "Test",
            "priority": "urgent",
        },
    )
    assert resp.status_code == 422


def test_create_ticket_empty_subject(client):
    """Subject must be at least 1 character."""
    resp = client.post(
        "/api/v1/tickets",
        json={
            "subject": "",
            "description": "Test",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tickets — List
# ---------------------------------------------------------------------------


@patch("app.api.v1.tickets.supabase_admin")
def test_list_tickets(mock_admin, client):
    mock_admin.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "00000000-0000-0000-0000-000000000001",
                "subject": "Issue 1",
                "description": "Desc 1",
                "status": "open",
                "priority": "medium",
                "created_at": "2026-04-16T00:00:00+00:00",
                "updated_at": "2026-04-16T00:00:00+00:00",
            }
        ]
    )
    resp = client.get("/api/v1/tickets")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@patch("app.api.v1.tickets.supabase_admin")
def test_list_tickets_empty(mock_admin, client):
    mock_admin.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=[]
    )
    resp = client.get("/api/v1/tickets")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/{id} — Get
# ---------------------------------------------------------------------------


@patch("app.api.v1.tickets.supabase_admin")
def test_get_ticket_found(mock_admin, client):
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "subject": "Issue 1",
            "description": "Desc 1",
            "status": "open",
            "priority": "medium",
            "created_at": "2026-04-16T00:00:00+00:00",
            "updated_at": "2026-04-16T00:00:00+00:00",
        }
    )
    resp = client.get("/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 200


@patch("app.api.v1.tickets.supabase_admin")
def test_get_ticket_not_found(mock_admin, client):
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )
    resp = client.get("/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/tickets/{id}/status — Status transition
# ---------------------------------------------------------------------------


def _mock_ticket_row(status="open"):
    """Helper to create a mock Supabase row for a ticket."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "subject": "Test",
        "description": "Desc",
        "status": status,
        "priority": "medium",
        "created_at": "2026-04-16T00:00:00+00:00",
        "updated_at": "2026-04-16T00:00:00+00:00",
    }


@patch("app.api.v1.tickets.supabase_admin")
def test_transition_open_to_in_progress(mock_admin, client):
    """open -> in_progress is a valid transition."""
    ticket_data = _mock_ticket_row("open")
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=ticket_data
    )
    mock_admin.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{**ticket_data, "status": "in_progress"}]
    )

    resp = client.patch(
        "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/status",
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@patch("app.api.v1.tickets.supabase_admin")
def test_transition_same_status_noop(mock_admin, client):
    """Setting the same status is a no-op and returns 200."""
    ticket_data = _mock_ticket_row("open")
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=ticket_data
    )

    resp = client.patch(
        "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/status",
        json={"status": "open"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"


@patch("app.api.v1.tickets.supabase_admin")
def test_transition_invalid_open_to_resolved(mock_admin, client):
    """open -> resolved is NOT a valid transition. Returns 409."""
    ticket_data = _mock_ticket_row("open")
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=ticket_data
    )

    resp = client.patch(
        "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/status",
        json={"status": "resolved"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "invalid_transition"


@patch("app.api.v1.tickets.supabase_admin")
def test_transition_closed_to_open(mock_admin, client):
    """closed -> open is NOT valid (closed is terminal). Returns 409."""
    ticket_data = _mock_ticket_row("closed")
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=ticket_data
    )

    resp = client.patch(
        "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/status",
        json={"status": "open"},
    )
    assert resp.status_code == 409


@patch("app.api.v1.tickets.supabase_admin")
def test_transition_ticket_not_found(mock_admin, client):
    """Status transition on nonexistent ticket returns 404."""
    mock_admin.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    resp = client.patch(
        "/api/v1/tickets/550e8400-e29b-41d4-a716-446655440000/status",
        json={"status": "in_progress"},
    )
    assert resp.status_code == 404
