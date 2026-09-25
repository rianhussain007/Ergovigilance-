"""API smoke tests — exercise the running FastAPI app end to end.

Covers the security-critical behavior shipped in the P0 pass plus the
operational endpoints from P1:

- /health, /healthz, /readyz, /metrics
- login success/failure (per-IP throttling is asserted in
  tests/test_login_rate_limit.py — there is no per-account lockout)
- fail-closed 503 when the live monitoring service is unavailable
  (POSE_MODEL_PATH is intentionally invalid in the test environment)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


# ── Operational endpoints ──────────────────────────────────────────────


def test_health_endpoint(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert "version" in body
    assert body["live_session"] is False  # live service never initialized in tests


def test_healthz_liveness(client: TestClient):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_readyz_fails_closed_without_live_service(client: TestClient):
    """Without the live service (and not in mock mode) readiness must be 503."""
    res = client.get("/readyz")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] is True
    assert body["checks"]["live_service"] is False


def test_metrics_endpoint(client: TestClient):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    assert "http_requests_total" in res.text
    assert "ergo_active_sessions" in res.text
    assert "ergo_uptime_seconds" in res.text


# ── Auth ───────────────────────────────────────────────────────────────


def test_login_success_returns_token_with_expiry(client: TestClient):
    res = client.post("/api/auth/login", json={"email": "admin@example.local", "password": "AdminPass123!"})
    assert res.status_code == 200
    body = res.json()
    assert body["token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600  # AUTH_JWT_TTL_SECONDS set by conftest
    assert body["expires_at"]
    assert body["user"]["email"] == "admin@example.local"
    assert body["user"]["role"] == "admin"


def test_login_wrong_password_rejected(client: TestClient):
    res = client.post("/api/auth/login", json={"email": "supervisor@example.local", "password": "wrong-password"})
    assert res.status_code == 401


# NOTE: every test-client request shares one IP, so the middleware's per-IP
# /auth bucket accumulates across this module. conftest raises
# RATE_LIMIT_AUTH_MAX to 500 for the suite; throttling against the real default
# is asserted in tests/test_login_rate_limit.py.

def test_repeated_failures_do_not_lock_the_account(client: TestClient):
    """Failed logins are audited and throttled per IP — never locked per account.

    Locking a known email would let anyone deny service to that user on purpose,
    so the correct password must still work after repeated failures.
    """
    email, password = "safety@example.local", "SafetyPass123!"
    for _ in range(5):
        res = client.post("/api/auth/login", json={"email": email, "password": "bad-password"})
        assert res.status_code == 401
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "safety_mgr"


def test_live_mode_fails_closed_with_503(client: TestClient):
    """Without the live service, repository-backed endpoints return 503 (never mock data)."""
    res = client.post("/api/auth/login", json={"email": "operator@example.local", "password": "OperatorPass123!"})
    assert res.status_code == 200
    token = res.json()["token"]

    res = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()
