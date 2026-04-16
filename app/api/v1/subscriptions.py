"""
Subscription endpoints — Week 5 implementation.

Routes:
  POST /api/v1/subscribe/checkout   — create Stripe Checkout Session
  POST /api/v1/webhooks/stripe      — Stripe webhook receiver
  GET  /api/v1/subscribe/status     — current user's subscription status
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin
from app.services.stripe_svc import create_checkout_session, handle_webhook

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /subscribe/checkout
# ---------------------------------------------------------------------------


@router.post(
    "/subscribe/checkout",
    status_code=status.HTTP_200_OK,
    summary="Create a Stripe Checkout Session for premium upgrade",
)
async def checkout(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """
    Returns a Stripe-hosted Checkout URL. The client redirects to this URL.
    On success, Stripe sends a webhook to /webhooks/stripe which activates the subscription.
    """
    from app.core.config import settings

    user_id: str = current_user["sub"]
    base = settings.FRONTEND_URL

    return await create_checkout_session(
        user_id=user_id,
        success_url=f"{base}/en/subscribe/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/en/subscribe",
    )


# ---------------------------------------------------------------------------
# POST /webhooks/stripe  (no auth — Stripe signs the payload)
# ---------------------------------------------------------------------------


@router.post(
    "/webhooks/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook receiver",
    include_in_schema=False,
)
async def stripe_webhook(request: Request) -> dict[str, str]:
    return await handle_webhook(request)


# ---------------------------------------------------------------------------
# GET /subscribe/status
# ---------------------------------------------------------------------------


@router.get(
    "/subscribe/status",
    status_code=status.HTTP_200_OK,
    summary="Get the current user's subscription status",
)
async def subscription_status(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns tier and status. Defaults to free/active if no subscription row exists."""
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("subscriptions")
        .select("tier, status, current_period_end, stripe_subscription_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .maybe_single()
        .execute()
    )

    if resp.data:
        return resp.data

    return {"tier": "free", "status": "active", "current_period_end": None}
