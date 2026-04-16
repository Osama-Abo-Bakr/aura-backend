from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_supabase_jwt
from app.db.supabase import supabase_admin

bearer_scheme = HTTPBearer()

# Quota limits per subscription tier.
# None means unlimited.
TIER_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "chat": 10,
        "skin": 3,
        "report": 1,
    },
    "premium": {
        "chat": None,
        "skin": None,
        "report": None,
    },
}

UPGRADE_URL = "https://aura-health.app/upgrade"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """
    Extract and verify the Bearer JWT from the Authorization header.

    Returns the decoded JWT payload which contains at minimum:
      - sub: the Supabase user UUID
      - email: the user's email address
      - role: 'authenticated'
    """
    token = credentials.credentials
    payload = verify_supabase_jwt(token)
    return payload


async def check_quota(
    interaction_type: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    """
    Verify the user has not exceeded their monthly quota for the given
    interaction_type ('chat', 'skin', or 'report').

    Raises HTTPException 429 when the limit is reached.
    """
    user_id: str = current_user["sub"]

    # Look up the user's subscription tier.
    sub_resp = (
        supabase_admin.table("subscriptions")
        .select("tier")
        .eq("user_id", user_id)
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    tier: str = ((sub_resp.data if sub_resp else None) or {}).get("tier", "free")

    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    limit = limits.get(interaction_type)

    # Unlimited tier — nothing to check.
    if limit is None:
        return

    # Count interactions for the current calendar month.
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    count_resp = (
        supabase_admin.table("ai_interactions")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("interaction_type", interaction_type)
        .gte("created_at", month_start)
        .execute()
    )
    used: int = count_resp.count or 0

    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "interaction_type": interaction_type,
                "limit": limit,
                "used": used,
                "upgrade_url": UPGRADE_URL,
            },
        )


def make_quota_checker(interaction_type: str):
    """
    Factory that returns a FastAPI dependency for a specific interaction type.

    Usage:
        router.get("/chat", dependencies=[Depends(make_quota_checker("chat"))])
    """

    async def _checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> None:
        await check_quota(interaction_type, current_user)

    return _checker


async def get_current_user_with_tier(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> tuple[dict[str, Any], str]:
    """
    Extends get_current_user by also resolving the user's subscription tier.

    Returns:
        (jwt_payload, tier_str) where tier_str is "free", "premium", etc.
        Defaults to "free" if no active subscription row exists.
    """
    user_id: str = current_user["sub"]
    sub_resp = (
        supabase_admin.table("subscriptions")
        .select("tier")
        .eq("user_id", user_id)
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    tier: str = ((sub_resp.data if sub_resp else None) or {}).get("tier", "free")
    return current_user, tier
