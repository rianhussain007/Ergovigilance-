"""Entitlement enforcement + billing-to-plan wiring (sell-readiness S2).

Covers audit F-01..F-03: tier map is the single source, signup mints
pilot/4 orgs, Stripe events upgrade/downgrade plans without ever raising,
and admins can provision plans directly.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Real app without lifespan (same pattern as test_login_mfa)."""
    from app.core.database import init_local_database
    from app.main import app

    init_local_database()
    return TestClient(app)


def _signup(client: TestClient, tag: str) -> dict:
    email = f"ent-{tag}-{uuid.uuid4().hex[:8]}@acme-manufacturing.com"
    resp = client.post(
        "/api/auth/signup",
        json={
            "organization_name": f"Ent {tag}",
            "email": email,
            "password": "EntTestPass123!",
            "agree_terms": True,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_tier_map_is_single_source():
    from app.api.billing import PRICING_TIERS, plan_limits_for_tier

    assert plan_limits_for_tier("cloud") == ("professional", PRICING_TIERS["cloud"]["cameras"])
    assert plan_limits_for_tier("starter") == ("starter", 4)
    assert plan_limits_for_tier("enterprise") == ("enterprise", None)
    with pytest.raises(ValueError):
        plan_limits_for_tier("nope")


def test_signup_defaults_pilot_four(client: TestClient):
    data = _signup(client, "defaults")
    org = data["organization"]
    assert org["plan"] == "pilot"
    assert org["max_cameras"] == 4
    assert org["max_workers"] == 50


def test_webhook_checkout_upgrades_to_cloud(client: TestClient):
    from app.api.billing import _apply_subscription_event

    data = _signup(client, "upgrade")
    _apply_subscription_event(
        "checkout.session.completed",
        {"metadata": {"user_id": data["user"]["id"], "tier": "cloud"}},
    )
    me = client.get("/api/orgs/current", headers=_auth(data["token"]))
    assert me.status_code == 200, me.text
    assert me.json()["plan"] == "professional"
    assert me.json()["max_cameras"] == 20


def test_webhook_deleted_downgrades_to_starter(client: TestClient):
    from app.api.billing import _apply_subscription_event

    data = _signup(client, "downgrade")
    _apply_subscription_event(
        "checkout.session.completed",
        {"metadata": {"user_id": data["user"]["id"], "tier": "cloud"}},
    )
    _apply_subscription_event(
        "customer.subscription.deleted",
        {"metadata": {"user_id": data["user"]["id"]}},
    )
    me = client.get("/api/orgs/current", headers=_auth(data["token"]))
    assert me.json()["plan"] == "starter"
    assert me.json()["max_cameras"] == 4


def test_webhook_garbage_never_raises():
    from app.api.billing import _apply_subscription_event

    _apply_subscription_event("customer.subscription.deleted", {})
    _apply_subscription_event("bogus.event", {"metadata": {"user_id": "not-an-int"}})
    _apply_subscription_event("checkout.session.completed", {"metadata": {"tier": "nope"}})


def test_admin_plan_patch_and_rbac(client: TestClient):
    data = _signup(client, "patch")  # admin of their own org
    org_id = data["organization"]["id"]
    headers = _auth(data["token"])

    resp = client.patch(
        f"/api/orgs/{org_id}/plan", json={"plan": "enterprise", "max_cameras": 50}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"] == "enterprise"
    assert resp.json()["max_cameras"] == 50

    bad = client.patch(
        f"/api/orgs/{org_id}/plan", json={"plan": "platinum", "max_cameras": 1}, headers=headers
    )
    assert bad.status_code == 400

    missing = client.patch(
        "/api/orgs/999999/plan", json={"plan": "professional", "max_cameras": 20}, headers=headers
    )
    assert missing.status_code == 404

    # Seeded non-admin operator must be refused.
    login = client.post(
        "/api/auth/login", json={"email": "operator@example.local", "password": "OperatorPass123!"}
    )
    assert login.status_code == 200, login.text
    op_token = login.json()["token"]
    forbidden = client.patch(
        f"/api/orgs/{org_id}/plan",
        json={"plan": "cloud", "max_cameras": 20},
        headers=_auth(op_token),
    )
    assert forbidden.status_code == 403


def test_checkout_discounts_builder():
    from app.api.billing import _checkout_discounts

    assert _checkout_discounts(None) is None
    assert _checkout_discounts("") is None
    assert _checkout_discounts("   ") is None
    assert _checkout_discounts("promo_assess50") == [{"promotion_code": "promo_assess50"}]


def test_checkout_requires_stripe_even_with_coupon(client: TestClient):
    # No STRIPE_SECRET_KEY in the test env: 503 before any stripe import,
    # coupon or not (fail-safe ordering).
    data = _signup(client, "coupon503")
    resp = client.post(
        "/api/billing/checkout",
        json={"tier": "cloud", "coupon": "promo_assess50"},
        headers=_auth(data["token"]),
    )
    assert resp.status_code == 503


def test_trial_status_pure():
    from datetime import datetime, timezone

    from app.api.billing import TRIAL_DAYS, trial_status

    assert TRIAL_DAYS == 14
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    fresh = {"plan": "pilot", "created_at": "2026-09-26T00:00:00+00:00"}
    assert trial_status(fresh, now) == {"trial_expired": False, "trial_days_left": 14}
    old = {"plan": "pilot", "created_at": "2026-09-01T00:00:00+00:00"}
    expired = trial_status(old, now)
    assert expired["trial_expired"] is True
    assert expired["trial_days_left"] == 0
    paid = {"plan": "professional", "created_at": "2020-01-01T00:00:00+00:00"}
    assert trial_status(paid, now) == {"trial_expired": False, "trial_days_left": None}
    assert trial_status({"plan": "pilot", "created_at": "garbage"}, now) == {
        "trial_expired": False,
        "trial_days_left": None,
    }
    assert trial_status({}, now) == {"trial_expired": False, "trial_days_left": None}
    assert trial_status(None, now) == {"trial_expired": False, "trial_days_left": None}


def test_current_org_carries_trial_signal(client: TestClient):
    data = _signup(client, "trial")  # fresh pilot org
    me = client.get("/api/orgs/current", headers=_auth(data["token"]))
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["trial_expired"] is False
    assert body["trial_days_left"] == 14
