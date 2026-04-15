from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin
from app.models.user import ProfileCreate, ProfileResponse, ProfileUpdate, SubscriptionResponse

router = APIRouter()


@router.post(
    "/auth/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or update the authenticated user's profile",
)
async def upsert_profile(
    payload: ProfileCreate | ProfileUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ProfileResponse:
    """
    Upsert the profile row for the currently authenticated user.

    - On first sign-in, pass a ``ProfileCreate`` body (full_name required).
    - On subsequent calls, any subset of fields can be updated.

    The ``user_id`` is always taken from the verified JWT — clients cannot
    supply or spoof it.
    """
    user_id: str = current_user["sub"]

    # Build the dict, excluding fields that were not provided.
    update_data = payload.model_dump(exclude_none=True)
    update_data["user_id"] = user_id

    response = (
        supabase_admin.table("profiles")
        .upsert(update_data, on_conflict="user_id")
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upsert profile.",
        )

    return ProfileResponse(**response.data[0])


@router.get(
    "/me",
    summary="Get the current user's profile and subscription tier",
)
async def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return the authenticated user's profile row together with their active
    subscription (defaults to the free tier if none exists).
    """
    user_id: str = current_user["sub"]

    # Fetch profile
    profile_resp = (
        supabase_admin.table("profiles")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not profile_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please complete onboarding.",
        )

    # Fetch active subscription (may be absent for brand-new users)
    sub_resp = (
        supabase_admin.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .maybe_single()
        .execute()
    )

    subscription = sub_resp.data or {"tier": "free", "status": "active"}

    return {
        "profile": profile_resp.data,
        "subscription": subscription,
    }
