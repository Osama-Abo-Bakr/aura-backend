"""
Stripe billing service layer.

Week 1: function signatures and type contracts only.
Full implementations (checkout sessions, webhook handling) ship in Week 2.
"""

from __future__ import annotations

from fastapi import Request


async def create_checkout_session(
    user_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    """
    Create a Stripe Checkout Session for a subscription upgrade.

    Args:
        user_id: Supabase user UUID — stored as client_reference_id so the
                 webhook can link the Stripe customer back to our database.
        price_id: Stripe Price ID for the target plan (e.g. 'price_xxx').
        success_url: URL to redirect to after a successful payment.
        cancel_url: URL to redirect to if the user cancels.

    Returns:
        {"checkout_url": "<Stripe hosted checkout URL>"}
    """
    raise NotImplementedError("create_checkout_session will be implemented in Week 2.")


async def handle_webhook(request: Request) -> dict[str, str]:
    """
    Process an incoming Stripe webhook event.

    Validates the Stripe-Signature header against STRIPE_WEBHOOK_SECRET,
    then dispatches the event to the appropriate handler:
      - checkout.session.completed  → activate subscription
      - customer.subscription.updated → sync tier / status
      - customer.subscription.deleted → downgrade to free

    Args:
        request: The raw FastAPI Request (body must not be consumed before
                 calling this function so the signature can be verified).

    Returns:
        {"status": "ok"} on success.
    """
    raise NotImplementedError("handle_webhook will be implemented in Week 2.")
