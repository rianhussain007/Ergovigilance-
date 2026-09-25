"""Per-IP login rate limiting (app/core/rate_limit.py).

/auth/login and /auth/demo share a dedicated bucket of AUTH_MAX requests per
IP per window (10/min in production) that is independent of the general
limiter — which exempts /auth/ entirely.
"""

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core import rate_limit
from app.core.rate_limit import RateLimitMiddleware


def _app() -> FastAPI:
    api = FastAPI()

    @api.post("/auth/login")
    async def login():  # pragma: no cover - response shape is irrelevant
        return {"ok": True}

    @api.post("/auth/demo")
    async def demo():  # pragma: no cover
        return {"ok": True}

    @api.get("/healthz")
    async def healthz():  # pragma: no cover
        return {"ok": True}

    api.add_middleware(RateLimitMiddleware)
    return api


def test_eleventh_login_attempt_is_blocked(monkeypatch):
    monkeypatch.setattr(rate_limit, "AUTH_MAX", 10)
    client = TestClient(_app())

    for _ in range(10):
        assert client.post("/auth/login").status_code == 200

    blocked = client.post("/auth/login")
    assert blocked.status_code == 429
    assert "Too many authentication attempts" in blocked.text
    assert blocked.headers["Retry-After"] == str(rate_limit.WINDOW)


def test_bucket_is_shared_by_login_and_demo(monkeypatch):
    monkeypatch.setattr(rate_limit, "AUTH_MAX", 3)
    client = TestClient(_app())

    assert client.post("/auth/login").status_code == 200
    assert client.post("/auth/demo").status_code == 200
    assert client.post("/auth/login").status_code == 200
    assert client.post("/auth/demo").status_code == 429


def test_health_check_still_served_while_login_is_throttled(monkeypatch):
    monkeypatch.setattr(rate_limit, "AUTH_MAX", 1)
    client = TestClient(_app())

    assert client.post("/auth/login").status_code == 200
    assert client.post("/auth/login").status_code == 429
    assert client.get("/healthz").status_code == 200


def test_forwarded_for_ignored_unless_proxy_trusted(monkeypatch):
    """Spoofed X-Forwarded-For must not create fresh buckets by default."""
    monkeypatch.setattr(rate_limit, "AUTH_MAX", 1)
    monkeypatch.setattr(rate_limit.settings, "TRUST_PROXY_HEADERS", False)
    client = TestClient(_app())

    assert client.post("/auth/login", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # Same socket peer, different spoofed header -> still the same bucket.
    assert client.post("/auth/login", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
