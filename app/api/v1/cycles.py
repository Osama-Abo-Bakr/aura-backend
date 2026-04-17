"""
Menstrual cycle tracker endpoints.

Routes:
  POST   /api/v1/cycles              — create a cycle entry
  GET    /api/v1/cycles              — list user's cycles (paginated, newest first)
  GET    /api/v1/cycles/prediction   — predict next period and current phase
  PUT    /api/v1/cycles/{cycle_id}  — update a cycle entry
  DELETE /api/v1/cycles/{cycle_id}  — delete a cycle entry
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin
from app.models.cycle import CycleEntryCreate

router = APIRouter(prefix="/cycles")


# ---------------------------------------------------------------------------
# POST /cycles — create cycle entry
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Create a menstrual cycle entry",
)
async def create_cycle_entry(
    body: CycleEntryCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    data = body.model_dump(exclude_none=False)
    # Convert date objects to ISO strings for Supabase
    data["start_date"] = data["start_date"].isoformat()
    if data.get("end_date"):
        data["end_date"] = data["end_date"].isoformat()
    data["user_id"] = user_id

    resp = supabase_admin.table("menstrual_cycles").insert(data).execute()

    if not resp or not resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create cycle entry.",
        )

    return resp.data[0]


# ---------------------------------------------------------------------------
# GET /cycles — list user's cycles (paginated, newest first)
# ---------------------------------------------------------------------------


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List user's menstrual cycle entries",
)
async def list_cycles(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict]:
    user_id: str = current_user["sub"]
    offset = (page - 1) * limit

    resp = (
        supabase_admin.table("menstrual_cycles")
        .select("*")
        .eq("user_id", user_id)
        .order("start_date", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return resp.data or []


# ---------------------------------------------------------------------------
# GET /cycles/prediction — predict next period and current phase
# ---------------------------------------------------------------------------


@router.get(
    "/prediction",
    status_code=status.HTTP_200_OK,
    summary="Predict next period date and current cycle phase",
)
async def get_cycle_prediction(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    # Fetch last 3 cycles to compute average cycle length
    resp = (
        supabase_admin.table("menstrual_cycles")
        .select("start_date, cycle_length, period_length")
        .eq("user_id", user_id)
        .order("start_date", desc=True)
        .limit(3)
        .execute()
    )

    cycles = resp.data or []

    if not cycles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "no_cycle_data",
                "message": "Add at least one cycle entry to get predictions.",
            },
        )

    # Calculate average cycle length from available data
    avg_cycle_length = round(sum(c["cycle_length"] for c in cycles) / len(cycles))
    avg_period_length = round(sum(c["period_length"] for c in cycles) / len(cycles))

    # Most recent cycle start date
    last_start = (
        date.fromisoformat(cycles[0]["start_date"])
        if isinstance(cycles[0]["start_date"], str)
        else cycles[0]["start_date"]
    )

    today = date.today()
    days_since_last_start = (today - last_start).days

    # Calculate next period
    next_period_start = last_start + timedelta(days=avg_cycle_length)
    next_period_end = next_period_start + timedelta(days=avg_period_length)
    days_until_next = (next_period_start - today).days

    # Determine current phase
    if days_since_last_start < avg_period_length:
        current_phase = "menstrual"
        phase_description = "Your period — rest and self-care"
    elif days_since_last_start < 13:
        current_phase = "follicular"
        phase_description = "Energy rising — great for new projects"
    elif days_since_last_start < 15:
        current_phase = "ovulation"
        phase_description = "Peak energy and focus"
    else:
        current_phase = "luteal"
        phase_description = "Wind down — prioritize rest"

    return {
        "next_period_start": next_period_start.isoformat(),
        "next_period_end": next_period_end.isoformat(),
        "days_until_next": days_until_next,
        "current_phase": current_phase,
        "phase_description": phase_description,
    }


# ---------------------------------------------------------------------------
# PUT /cycles/{cycle_id} — update cycle entry
# ---------------------------------------------------------------------------


@router.put(
    "/{cycle_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a menstrual cycle entry",
)
async def update_cycle_entry(
    cycle_id: str,
    body: dict[str, Any],
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    # Verify ownership
    existing = (
        supabase_admin.table("menstrual_cycles")
        .select("id, user_id")
        .eq("id", cycle_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not existing or not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "cycle_not_found"},
        )

    # Build update payload — only include fields that were provided
    allowed_fields = {
        "start_date",
        "end_date",
        "cycle_length",
        "period_length",
        "symptoms",
        "mood",
        "notes",
    }
    update_data = {}
    for key, value in body.items():
        if key in allowed_fields:
            # Convert date strings to ISO format
            if key in ("start_date", "end_date") and value is not None:
                update_data[key] = (
                    value.isoformat() if hasattr(value, "isoformat") else value
                )
            else:
                update_data[key] = value

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update.",
        )

    resp = (
        supabase_admin.table("menstrual_cycles")
        .update(update_data)
        .eq("id", cycle_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not resp or not resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cycle entry.",
        )

    return resp.data[0]


# ---------------------------------------------------------------------------
# DELETE /cycles/{cycle_id} — delete cycle entry
# ---------------------------------------------------------------------------


@router.delete(
    "/{cycle_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a menstrual cycle entry",
)
async def delete_cycle_entry(
    cycle_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    # Verify ownership
    existing = (
        supabase_admin.table("menstrual_cycles")
        .select("id")
        .eq("id", cycle_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not existing or not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "cycle_not_found"},
        )

    supabase_admin.table("menstrual_cycles").delete().eq("id", cycle_id).eq(
        "user_id", user_id
    ).execute()

    return {"deleted": True}
