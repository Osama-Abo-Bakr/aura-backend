from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin
from app.models.user import (
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SubscriptionResponse,
    TokenRequest,
    TokenResponse,
)
from app.services.auth import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)

router = APIRouter()


def _get_auth_service() -> AuthService:
    """Factory for AuthService — makes testing easier."""
    return AuthService()


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
) -> RegisterResponse:
    """
    Register a new user via Supabase Auth.

    Returns the new user's ID, email, and full name.
    Does NOT create a profile row — call /auth/profile separately.
    """
    try:
        result = auth_service.signup(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    user_id = result.get("id") or result.get("user", {}).get("id")
    email = result.get("email", body.email)
    full_name = result.get("user_metadata", {}).get("full_name", body.full_name)

    return RegisterResponse(
        user_id=UUID(user_id),
        email=email,
        full_name=full_name,
    )


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------


@router.post(
    "/auth/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and get tokens",
)
async def token(
    body: TokenRequest,
    auth_service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """
    Authenticate with email/password and receive access + refresh tokens.
    """
    try:
        tokens = auth_service.signin(email=body.email, password=body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        token_type=tokens.token_type,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh an access token",
)
async def refresh(
    body: RefreshRequest,
    auth_service: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """
    Exchange a valid refresh token for new access + refresh tokens.
    """
    try:
        tokens = auth_service.refresh_token(refresh_token=body.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        token_type=tokens.token_type,
    )


# ---------------------------------------------------------------------------
# POST /auth/signout
# ---------------------------------------------------------------------------


@router.post(
    "/auth/signout",
    status_code=status.HTTP_200_OK,
    summary="Sign out the current user",
)
async def signout(
    current_user: dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(_get_auth_service),
) -> dict[str, str]:
    """
    Revoke the current user's session in Supabase.
    Requires a valid access token in the Authorization header.
    """
    access_token = current_user.get("access_token", "")
    auth_service.signout(access_token)
    return {"message": "Signed out successfully"}


# ---------------------------------------------------------------------------
# POST /auth/profile  (existing)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GET /me  (existing)
# ---------------------------------------------------------------------------


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