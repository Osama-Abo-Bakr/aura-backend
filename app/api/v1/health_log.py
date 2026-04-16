"""
Health log endpoints — Week 6 implementation.

Routes:
  POST   /api/v1/health-log          — create or update today's log entry
  GET    /api/v1/health-log          — list recent log entries (last 30 days)
  GET    /api/v1/health-log/{date}   — get entry for a specific date (YYYY-MM-DD)
  DELETE /api/v1/health-log/{date}   — delete entry for a specific date
  GET    /api/v1/health-log/summary  — aggregated chart data for the last N days
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin

router = APIRouter(prefix="/health-log")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class HealthLogUpsert(BaseModel):
    log_date: date = Field(default_factory=date.today)
    mood: int | None = Field(default=None, ge=1, le=10)
    energy: int | None = Field(default=None, ge=1, le=10)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    water_ml: int | None = Field(default=None, ge=0)
    exercise_minutes: int | None = Field(default=None, ge=0)
    symptoms: list[str] = Field(default_factory=list)
    notes: str | None = None


# ---------------------------------------------------------------------------
# POST /health-log — upsert today's (or given date's) entry
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Create or update a health log entry",
)
async def upsert_health_log(
    body: HealthLogUpsert,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    data = body.model_dump(exclude_none=False)
    data["log_date"] = data["log_date"].isoformat()
    data["user_id"] = user_id

    resp = (
        supabase_admin.table("health_logs")
        .upsert(data, on_conflict="user_id,log_date")
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save health log.",
        )

    return resp.data[0]


# ---------------------------------------------------------------------------
# GET /health-log — last 30 days
# ---------------------------------------------------------------------------


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List health log entries for the last N days",
)
async def list_health_logs(
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict]:
    user_id: str = current_user["sub"]
    since = (date.today() - timedelta(days=days)).isoformat()

    resp = (
        supabase_admin.table("health_logs")
        .select("*")
        .eq("user_id", user_id)
        .gte("log_date", since)
        .order("log_date", desc=True)
        .execute()
    )

    return resp.data or []


# ---------------------------------------------------------------------------
# GET /health-log/summary — chart-ready aggregations
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    status_code=status.HTTP_200_OK,
    summary="Aggregated health data for charts",
)
async def health_summary(
    days: int = Query(default=30, ge=7, le=90),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Returns chart-ready data:
    - mood_trend: [{date, value}]
    - energy_trend: [{date, value}]
    - sleep_trend: [{date, value}]
    - symptom_frequency: [{symptom, count}]
    - exercise_total_minutes: int
    - water_avg_ml: float
    """
    user_id: str = current_user["sub"]
    since = (date.today() - timedelta(days=days)).isoformat()

    resp = (
        supabase_admin.table("health_logs")
        .select("log_date, mood, energy, sleep_hours, water_ml, exercise_minutes, symptoms")
        .eq("user_id", user_id)
        .gte("log_date", since)
        .order("log_date", desc=False)
        .execute()
    )

    rows = resp.data or []

    mood_trend = [{"date": r["log_date"], "value": r["mood"]} for r in rows if r.get("mood")]
    energy_trend = [{"date": r["log_date"], "value": r["energy"]} for r in rows if r.get("energy")]
    sleep_trend = [{"date": r["log_date"], "value": r["sleep_hours"]} for r in rows if r.get("sleep_hours") is not None]

    # Symptom frequency
    symptom_counts: dict[str, int] = {}
    for r in rows:
        for s in (r.get("symptoms") or []):
            symptom_counts[s] = symptom_counts.get(s, 0) + 1
    symptom_frequency = sorted(
        [{"symptom": k, "count": v} for k, v in symptom_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    exercise_total = sum(r.get("exercise_minutes") or 0 for r in rows)
    water_values = [r["water_ml"] for r in rows if r.get("water_ml") is not None]
    water_avg = round(sum(water_values) / len(water_values)) if water_values else 0

    return {
        "mood_trend": mood_trend,
        "energy_trend": energy_trend,
        "sleep_trend": sleep_trend,
        "symptom_frequency": symptom_frequency,
        "exercise_total_minutes": exercise_total,
        "water_avg_ml": water_avg,
        "days": days,
        "entry_count": len(rows),
    }


# ---------------------------------------------------------------------------
# GET /health-log/{log_date}
# ---------------------------------------------------------------------------


@router.get(
    "/{log_date}",
    status_code=status.HTTP_200_OK,
    summary="Get health log entry for a specific date",
)
async def get_health_log(
    log_date: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("health_logs")
        .select("*")
        .eq("user_id", user_id)
        .eq("log_date", log_date)
        .maybe_single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "log_not_found"},
        )

    return resp.data


# ---------------------------------------------------------------------------
# DELETE /health-log/{log_date}
# ---------------------------------------------------------------------------


@router.delete(
    "/{log_date}",
    status_code=status.HTTP_200_OK,
    summary="Delete health log entry for a specific date",
)
async def delete_health_log(
    log_date: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("health_logs")
        .select("id")
        .eq("user_id", user_id)
        .eq("log_date", log_date)
        .maybe_single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "log_not_found"},
        )

    supabase_admin.table("health_logs").delete().eq("user_id", user_id).eq("log_date", log_date).execute()

    return {"deleted": True}
