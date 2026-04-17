"""
Admin analytics and data management endpoints.

Routes:
  GET    /api/v1/admin/stats         — platform overview statistics
  GET    /api/v1/admin/users         — user list with activity info
  GET    /api/v1/admin/interactions  — AI interaction analytics
  DELETE /api/v1/admin/data/{user_id}— delete all data for a user (testing)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import require_admin
from app.db.supabase import supabase_admin

router = APIRouter(prefix="/admin")


# ---------------------------------------------------------------------------
# GET /admin/stats — platform overview statistics
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    summary="Platform overview statistics",
)
async def admin_stats(
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Return aggregate counts across all major tables."""

    # Helper to count rows from a table
    def _count(table: str) -> int:
        resp = supabase_admin.table(table).select("id", count="exact").execute()
        return resp.count if resp.count is not None else len(resp.data or [])

    # Individual table counts
    users = _count("profiles")
    conversations = _count("conversations")
    messages = _count("messages")
    analyses = _count("analyses")
    cycle_entries = _count("menstrual_cycles")
    health_logs = _count("health_logs")

    # AI interactions — grouped by interaction_type
    interactions_resp = (
        supabase_admin.table("ai_interactions").select("interaction_type").execute()
    )
    interaction_rows = interactions_resp.data or []
    interactions_by_type: dict[str, int] = {}
    for row in interaction_rows:
        itype = row.get("interaction_type", "unknown")
        interactions_by_type[itype] = interactions_by_type.get(itype, 0) + 1

    interactions_total = sum(interactions_by_type.values())

    # Subscriptions — count by tier (active only)
    subs_resp = (
        supabase_admin.table("subscriptions")
        .select("tier")
        .eq("status", "active")
        .execute()
    )
    sub_rows = subs_resp.data or []
    subs_by_tier: dict[str, int] = {}
    for row in sub_rows:
        tier = row.get("tier", "free")
        subs_by_tier[tier] = subs_by_tier.get(tier, 0) + 1

    return {
        "users": users,
        "conversations": conversations,
        "messages": messages,
        "analyses": analyses,
        "cycle_entries": cycle_entries,
        "health_logs": health_logs,
        "ai_interactions": {
            **interactions_by_type,
            "total": interactions_total,
        },
        "subscriptions": subs_by_tier,
    }


# ---------------------------------------------------------------------------
# GET /admin/users — user list with activity
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    summary="List users with activity info",
)
async def admin_list_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Paginated user list from profiles, with interaction counts."""
    offset = (page - 1) * limit

    query = supabase_admin.table("profiles").select("*")

    if search:
        query = query.ilike("email", f"%{search}%")

    resp = (
        query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    )

    users = resp.data or []

    # For each user, fetch their ai_interactions count
    for user in users:
        uid = user.get("id") or user.get("user_id")
        if uid:
            count_resp = (
                supabase_admin.table("ai_interactions")
                .select("id", count="exact")
                .eq("user_id", uid)
                .execute()
            )
            user["interaction_count"] = (
                count_resp.count if count_resp.count is not None else 0
            )
        else:
            user["interaction_count"] = 0

    return {
        "users": users,
        "page": page,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# GET /admin/interactions — AI interaction analytics
# ---------------------------------------------------------------------------


@router.get(
    "/interactions",
    summary="AI interaction analytics",
)
async def admin_interactions(
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Daily AI interaction counts for the last N days, grouped by type."""
    since = (date.today() - timedelta(days=days)).isoformat()

    resp = (
        supabase_admin.table("ai_interactions")
        .select("created_at, interaction_type")
        .gte("created_at", since)
        .order("created_at", desc=False)
        .execute()
    )

    rows = resp.data or []

    # Group by date and type
    daily: dict[str, dict[str, int]] = {}
    for row in rows:
        created = row.get("created_at", "")
        # created_at is ISO string; extract date portion
        day = created[:10] if created else "unknown"
        itype = row.get("interaction_type", "unknown")

        if day not in daily:
            daily[day] = {}
        daily[day][itype] = daily[day].get(itype, 0) + 1

    # Build the response as a list of day entries
    result = [
        {"date": day, "types": types, "total": sum(types.values())}
        for day, types in sorted(daily.items())
    ]

    return {
        "days": days,
        "daily": result,
    }


# ---------------------------------------------------------------------------
# DELETE /admin/data/{user_id} — delete all data for a user (testing)
# ---------------------------------------------------------------------------


@router.delete(
    "/data/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete all data for a user (admin)",
)
async def admin_delete_user_data(
    user_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict:
    """
    Delete all application data for a user (for testing purposes).
    Does NOT delete the auth.users account or their subscription.
    """
    tables_to_clear = [
        "messages",
        "conversations",
        "menstrual_cycles",
        "health_logs",
        "analyses",
        "ai_interactions",
        "wellness_plans",
    ]

    cleared: list[str] = []

    for table in tables_to_clear:
        try:
            supabase_admin.table(table).delete().eq("user_id", user_id).execute()
            cleared.append(table)
        except Exception:
            # Table may not have data for this user — that's fine
            pass

    return {
        "deleted": True,
        "user_id": user_id,
        "tables_cleared": cleared,
    }
