"""
Stripe billing service layer — Week 5 implementation.
"""

from __future__ import annotations

import logging

import stripe
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_stripe() -> stripe:
    """Return configured stripe module, raise 503 if key not set."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Please add STRIPE_SECRET_KEY.",
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


async def create_checkout_session(
    user_id: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    """
    Create a Stripe Checkout Session for a premium subscription upgrade.

    Returns:
        {"checkout_url": "<Stripe hosted checkout URL>"}
    """
    s = _get_stripe()

    if not settings.STRIPE_PRICE_ID_PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe price ID not configured. Please add STRIPE_PRICE_ID_PREMIUM.",
        )

    session = s.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID_PREMIUM, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,  # used in webhook to link back to our user
        metadata={"user_id": user_id},
    )

    return {"checkout_url": session.url}


async def handle_webhook(request: Request) -> dict[str, str]:
    """
    Process an incoming Stripe webhook event.

    Validates the Stripe-Signature header, then handles:
      - checkout.session.completed  → activate premium subscription
      - customer.subscription.updated → sync tier / status
      - customer.subscription.deleted → downgrade to free
    """
    s = _get_stripe()

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret not configured.",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = s.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        )
    except Exception as exc:
        logger.error("Webhook parse error: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    else:
        logger.info("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


async def _handle_checkout_completed(session: dict) -> None:
    """Activate premium subscription after successful checkout."""
    from app.db.supabase import supabase_admin

    user_id = session.get("client_reference_id") or session.get("metadata", {}).get(
        "user_id"
    )
    if not user_id:
        logger.error(
            "checkout.session.completed missing user_id: %s", session.get("id")
        )
        return

    stripe_customer_id = session.get("customer")
    stripe_subscription_id = session.get("subscription")

    # Upsert subscription row → premium active
    supabase_admin.table("subscriptions").upsert(
        {
            "user_id": user_id,
            "tier": "premium",
            "status": "active",
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
        },
        on_conflict="user_id",
    ).execute()

    logger.info("Activated premium for user %s", user_id)


async def _handle_subscription_updated(subscription: dict) -> None:
    """Sync subscription status when Stripe updates it."""
    from app.db.supabase import supabase_admin

    stripe_subscription_id = subscription.get("id")
    stripe_status = subscription.get("status")  # active, past_due, canceled, etc.

    # Map Stripe statuses to our schema
    status_map = {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "canceled": "cancelled",
        "unpaid": "past_due",
    }
    our_status = status_map.get(stripe_status, "cancelled")
    tier = "premium" if our_status in ("active", "trialing") else "free"

    # Find by stripe_subscription_id
    resp = (
        supabase_admin.table("subscriptions")
        .select("id")
        .eq("stripe_subscription_id", stripe_subscription_id)
        .maybe_single()
        .execute()
    )
    if not resp or not resp.data:
        logger.warning("subscription.updated: no row for %s", stripe_subscription_id)
        return

    current_period_end = None
    if subscription.get("current_period_end"):
        import datetime

        current_period_end = datetime.datetime.fromtimestamp(
            subscription["current_period_end"], tz=datetime.timezone.utc
        ).isoformat()

    supabase_admin.table("subscriptions").update(
        {
            "tier": tier,
            "status": our_status,
            "current_period_end": current_period_end,
        }
    ).eq("stripe_subscription_id", stripe_subscription_id).execute()

    logger.info(
        "Updated subscription %s → %s / %s", stripe_subscription_id, tier, our_status
    )


async def _handle_subscription_deleted(subscription: dict) -> None:
    """Downgrade user to free when subscription is cancelled."""
    from app.db.supabase import supabase_admin

    stripe_subscription_id = subscription.get("id")

    supabase_admin.table("subscriptions").update(
        {"tier": "free", "status": "cancelled"}
    ).eq("stripe_subscription_id", stripe_subscription_id).execute()

    logger.info("Cancelled subscription %s → free", stripe_subscription_id)
