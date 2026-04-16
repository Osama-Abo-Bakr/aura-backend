"""Ticket support endpoints — CRUD + status state machine."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin
from app.models.ticket import TicketCreate, TicketResponse, TicketStatusUpdate

router = APIRouter(prefix="/tickets")

# Valid status transitions: {from_status: {allowed_to_statuses}}
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"closed"},
    "closed": set(),  # terminal state
}


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new support ticket",
)
async def create_ticket(
    body: TicketCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> TicketResponse:
    """Create a support ticket for the authenticated user."""
    user_id: str = current_user["sub"]

    data = body.model_dump()
    data["user_id"] = user_id

    resp = supabase_admin.table("tickets").insert(data).execute()

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ticket.",
        )

    return TicketResponse(**resp.data[0])


@router.get(
    "",
    response_model=list[TicketResponse],
    status_code=status.HTTP_200_OK,
    summary="List the current user's tickets",
)
async def list_tickets(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[TicketResponse]:
    """Return all tickets belonging to the authenticated user, newest first."""
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("tickets")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    return [TicketResponse(**row) for row in (resp.data or [])]


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific ticket",
)
async def get_ticket(
    ticket_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> TicketResponse:
    """Return a single ticket by ID (must belong to the authenticated user)."""
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("tickets")
        .select("*")
        .eq("id", str(ticket_id))
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    return TicketResponse(**resp.data)


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Transition a ticket's status",
)
async def update_ticket_status(
    ticket_id: UUID,
    body: TicketStatusUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> TicketResponse:
    """
    Transition a ticket's status according to the state machine:
      open → in_progress → resolved → closed
                              └──→ closed
    Setting the same status as current is a no-op (returns 200).
    """
    user_id: str = current_user["sub"]

    # Fetch current ticket
    resp = (
        supabase_admin.table("tickets")
        .select("*")
        .eq("id", str(ticket_id))
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    current_status = resp.data["status"]
    new_status = body.status

    # No-op: same status
    if current_status == new_status:
        return TicketResponse(**resp.data)

    # Validate transition
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "invalid_transition",
                "message": f"Cannot transition from '{current_status}' to '{new_status}'.",
                "allowed_transitions": list(allowed) if allowed else ["none (terminal state)"],
            },
        )

    # Update status
    update_resp = (
        supabase_admin.table("tickets")
        .update({"status": new_status})
        .eq("id", str(ticket_id))
        .eq("user_id", user_id)
        .execute()
    )

    if not update_resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ticket status.",
        )

    return TicketResponse(**update_resp.data[0])
