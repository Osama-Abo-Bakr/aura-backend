"""
Wellness plan endpoints — Week 6 implementation.

Routes:
  POST /api/v1/wellness/plan    — generate AI wellness plan (premium only)
  GET  /api/v1/wellness/plans   — list user's saved plans
  GET  /api/v1/wellness/plans/{id} — get a specific plan
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import get_current_user, get_current_user_with_tier
from app.db.supabase import supabase_admin

router = APIRouter(prefix="/wellness")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class WellnessPlanRequest(BaseModel):
    language: str = "en"


# ---------------------------------------------------------------------------
# POST /wellness/plan — premium only
# ---------------------------------------------------------------------------


@router.post(
    "/plan",
    status_code=status.HTTP_200_OK,
    summary="Generate a personalised AI wellness plan (Premium only)",
)
async def generate_plan(
    body: WellnessPlanRequest,
    user_and_tier: tuple[dict[str, Any], str] = Depends(get_current_user_with_tier),
) -> dict:
    current_user, tier = user_and_tier

    if tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "premium_required",
                "message": "Wellness plans are a Premium feature. Please upgrade to access them.",
            },
        )

    user_id: str = current_user["sub"]

    # Fetch user profile
    profile_resp = (
        supabase_admin.table("profiles")
        .select("full_name, health_goals, conditions, language")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    profile = (profile_resp.data if profile_resp else None) or {}

    # Fetch last 14 days of health logs
    from datetime import date, timedelta

    since = (date.today() - timedelta(days=14)).isoformat()
    logs_resp = (
        supabase_admin.table("health_logs")
        .select("log_date, mood, energy, sleep_hours, symptoms, notes")
        .eq("user_id", user_id)
        .gte("log_date", since)
        .order("log_date", desc=False)
        .execute()
    )
    logs = logs_resp.data or []

    # Generate plan via Gemini
    from app.services.gemini import generate_wellness_plan

    plan_data = await generate_wellness_plan(
        user_profile=profile,
        health_logs=logs,
        language=body.language,
    )

    # Persist to wellness_plans table
    import uuid

    plan_id = str(uuid.uuid4())
    supabase_admin.table("wellness_plans").insert(
        {
            "id": plan_id,
            "user_id": user_id,
            "title": plan_data.get("title", "Your Wellness Plan"),
            "description": plan_data.get("summary", ""),
            "tasks": plan_data.get("tasks", []),
            "language": body.language,
            "generated_by_ai": True,
        }
    ).execute()

    return {"plan_id": plan_id, **plan_data}


# ---------------------------------------------------------------------------
# GET /wellness/plans
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    summary="List the user's saved wellness plans",
)
async def list_plans(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict]:
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("wellness_plans")
        .select("id, title, description, tasks, language, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    return resp.data or []


# ---------------------------------------------------------------------------
# GET /wellness/plans/{plan_id}
# ---------------------------------------------------------------------------


@router.get(
    "/plans/{plan_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a specific wellness plan",
)
async def get_plan(
    plan_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("wellness_plans")
        .select("*")
        .eq("id", plan_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    plan_data = resp.data if resp else None

    if not plan_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "plan_not_found"},
        )

    return plan_data
