"""Stripe Billing Integration for ErgoVigilance Cloud.

Provides endpoints for:
- Creating Stripe Checkout sessions
- Managing subscriptions
- Handling webhooks
- Checking billing status

Requires:
  STRIPE_SECRET_KEY=sk_test_... (or sk_live_...)
  STRIPE_WEBHOOK_SECRET=whsec_...
  STRIPE_PRICE_ID=price_... (your Cloud tier price)

Set these in your .env file. The system works without them (billing disabled).
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")

# Pricing tiers. Keys are the marketing/checkout ids (PricingPage.tsx);
# "plan" is the organizations-table vocabulary (migration
# 005_multi_tenant.sql: pilot/starter/professional/enterprise).
PRICING_TIERS = {
    "starter": {
        "name": "On-Premise Starter",
        "plan": "starter",
        "price": 0,
        "cameras": 4,
        "description": "Free, self-hosted, up to 4 cameras",
    },
    "cloud": {
        "name": "Cloud Professional",
        "plan": "professional",
        "price": 299,
        "cameras": 20,
        "description": "$299/mo for up to 20 cameras",
        "stripe_price_id": STRIPE_PRICE_ID,
    },
    "enterprise": {
        "name": "Enterprise",
        "plan": "enterprise",
        "price": None,  # Custom pricing
        "cameras": None,
        "description": "Custom pricing for 50+ cameras",
    },
}


def plan_limits_for_tier(tier: str) -> tuple[str, int | None]:
    """Map a checkout tier to (plan, max_cameras).

    Single source of truth for what a paying tier grants: the caps in
    PRICING_TIERS. Webhooks and tests both read this — never hard-code
    tier limits anywhere else.
    """
    info = PRICING_TIERS.get(tier)
    if info is None:
        raise ValueError(f"Unknown tier: {tier}")
    return info["plan"], info["cameras"]


def _apply_subscription_event(kind: str, obj: dict) -> None:
    """Map a Stripe event onto the org plan. Never raises.

    Webhook endpoints must return 2xx (Stripe retries error deliveries for
    days); a mapping that cannot be resolved is logged loudly instead of
    failing the delivery.
    """
    try:
        from app.core.database import (
            get_org_id_for_user,
            get_user_by_email,
            update_org_plan,
        )

        meta = obj.get("metadata", {}) or {}
        user_id = meta.get("user_id")
        org_id = None
        if user_id is not None:
            try:
                org_id = get_org_id_for_user(int(user_id))
            except (TypeError, ValueError):
                org_id = None
        if org_id is None and meta.get("user_email"):
            user = get_user_by_email(meta["user_email"])
            if user is not None:
                org_id = get_org_id_for_user(user["id"])
        if org_id is None:
            logger.warning("Billing event %s ignored: no org for metadata %s", kind, meta)
            return

        if kind == "checkout.session.completed":
            plan, cameras = plan_limits_for_tier(meta.get("tier", "cloud"))
            if update_org_plan(org_id, plan, cameras):
                logger.info("Org %s upgraded to plan %s (%s cameras)", org_id, plan, cameras)
        elif kind == "customer.subscription.deleted":
            if update_org_plan(org_id, "starter", PRICING_TIERS["starter"]["cameras"]):
                logger.info("Org %s downgraded to starter (subscription deleted)", org_id)
        elif kind == "customer.subscription.updated":
            if obj.get("status") in ("active", "trialing"):
                plan, cameras = plan_limits_for_tier(meta.get("tier", "cloud"))
                update_org_plan(org_id, plan, cameras)
    except Exception as exc:
        logger.warning("Billing event %s not applied: %s", kind, exc)


@router.get("/config")
async def billing_config():
    """Return billing configuration and pricing tiers."""
    return {
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "tiers": PRICING_TIERS,
    }


@router.post("/checkout")
async def create_checkout_session(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a Stripe Checkout session for the Cloud tier.

    Body: {"tier": "cloud"} or {"tier": "cloud", "success_url": "...", "cancel_url": "..."}
    Returns: {"checkout_url": "https://checkout.stripe.com/..."}
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Set STRIPE_SECRET_KEY in .env to enable billing.",
        )

    tier = body.get("tier", "cloud")
    if tier not in PRICING_TIERS:
        raise HTTPException(400, f"Invalid tier: {tier}")

    tier_info = PRICING_TIERS[tier]
    if tier_info["price"] is None:
        raise HTTPException(400, "Enterprise tier requires custom sales contact")

    if tier == "starter":
        raise HTTPException(400, "Starter tier is free — no checkout needed")

    price_id = tier_info.get("stripe_price_id", "")
    if not price_id:
        raise HTTPException(503, "Stripe price not configured. Set STRIPE_PRICE_ID in .env.")

    success_url = body.get("success_url", "http://localhost:3000/settings?billing=success")
    cancel_url = body.get("cancel_url", "http://localhost:3000/pricing")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            customer_email=user.email,
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "user_email": user.email,
                "tier": tier,
            },
            subscription_data={
                "trial_period_days": 14,
                "metadata": {
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "tier": tier,
                },
            },
        )

        return {"checkout_url": session.url, "session_id": session.id}

    except Exception as exc:
        logger.error("Stripe checkout failed: %s", exc)
        raise HTTPException(500, f"Failed to create checkout session: {exc}")


@router.get("/subscription")
async def get_subscription(user: AuthenticatedUser = Depends(get_current_user)):
    """Get the current user's subscription status."""
    if not STRIPE_SECRET_KEY:
        return {
            "status": "no_billing",
            "tier": "starter",
            "message": "Stripe not configured — using free tier",
        }

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        # Search for customer by email
        customers = stripe.Customer.list(email=user.email, limit=1)
        if not customers.data:
            return {
                "status": "no_subscription",
                "tier": "starter",
                "message": "No active subscription",
            }

        customer = customers.data[0]
        subscriptions = stripe.Subscription.list(customer=customer.id, status="active", limit=1)

        if not subscriptions.data:
            return {
                "status": "no_subscription",
                "tier": "starter",
                "message": "No active subscription",
            }

        sub = subscriptions.data[0]
        return {
            "status": sub.status,
            "tier": sub.metadata.get("tier", "cloud"),
            "subscription_id": sub.id,
            "current_period_end": datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat(),
            "trial_end": datetime.fromtimestamp(sub.trial_end, tz=timezone.utc).isoformat() if sub.trial_end else None,
        }

    except Exception as exc:
        logger.warning("Failed to fetch subscription: %s", exc)
        return {
            "status": "error",
            "tier": "starter",
            "message": f"Could not check subscription: {exc}",
        }


@router.post("/portal")
async def create_portal_session(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        customers = stripe.Customer.list(email=user.email, limit=1)
        if not customers.data:
            raise HTTPException(404, "No Stripe customer found")

        portal = stripe.billing_portal.Session.create(
            customer=customers.data[0].id,
            return_url="http://localhost:3000/settings",
        )

        return {"portal_url": portal.url}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to create portal session: {exc}")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events.

    Configure in Stripe Dashboard: https://dashboard.stripe.com/webhooks
    Events to listen for: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted
    """
    if not STRIPE_WEBHOOK_SECRET:
        return JSONResponse(content={"error": "Webhook not configured"}, status_code=503)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return JSONResponse(content={"error": "Invalid payload"}, status_code=400)
    except stripe.error.SignatureVerificationError:
        return JSONResponse(content={"error": "Invalid signature"}, status_code=400)

    # Handle events (plan mapping never raises — see _apply_subscription_event)
    if event["type"] == "checkout.session.completed":
        _apply_subscription_event("checkout.session.completed", event["data"]["object"])

    elif event["type"] == "customer.subscription.updated":
        _apply_subscription_event("customer.subscription.updated", event["data"]["object"])

    elif event["type"] == "customer.subscription.deleted":
        _apply_subscription_event("customer.subscription.deleted", event["data"]["object"])

    return JSONResponse(content={"received": True})
