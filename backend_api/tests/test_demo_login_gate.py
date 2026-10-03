"""Regression tests for the demo-login gate (sellability audit §3.1).

``POST /api/auth/demo`` mints a real ``operator`` token for an **anonymous**
caller. Two things must therefore be true:

1. The route does not exist unless ``ENABLE_DEMO=true`` (or ``DEBUG=true``).
   A customer deployment that forgets the flag gets a 404, not a backdoor.
2. An anonymous call can never stop a live monitoring session. The route used to
   call ``service.stop_session()`` unconditionally, so one unauthenticated
   request could terminate a paying customer's monitoring — proven end-to-end
   in the audit (``active: True`` -> ``active: None``).

The session-stop behaviour is now limited to deployments that are *actually*
serving synthetic data (``backend.services.demo_seeding.DEMO_MODE``, read once
at import time), which is the same signal the dashboard banner trusts.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


# ── 1. The gate ─────────────────────────────────────────────────────────


def test_demo_login_enabled_follows_enable_demo_flag(monkeypatch):
    """ENABLE_DEMO is the switch; unset falls back to DEBUG."""
    from app.api import auth as auth_module

    monkeypatch.delenv("ENABLE_DEMO", raising=False)
    monkeypatch.setattr(auth_module.settings, "DEBUG", False)
    assert auth_module.demo_login_enabled() is False

    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ENABLE_DEMO", truthy)
        assert auth_module.demo_login_enabled() is True

    # An explicit opt-out beats DEBUG (a debug box with demo disabled).
    monkeypatch.setenv("ENABLE_DEMO", "false")
    monkeypatch.setattr(auth_module.settings, "DEBUG", True)
    assert auth_module.demo_login_enabled() is False

    # DEBUG alone still enables it so local dev / the in-repo suites work.
    monkeypatch.delenv("ENABLE_DEMO", raising=False)
    assert auth_module.demo_login_enabled() is True


def test_demo_login_404s_when_not_explicitly_enabled(client, monkeypatch):
    """On a production deployment the route must not exist at all."""
    from app.api import auth as auth_module

    monkeypatch.delenv("ENABLE_DEMO", raising=False)
    monkeypatch.setattr(auth_module.settings, "DEBUG", False)

    res = client.post("/api/auth/demo")
    assert res.status_code == 404, res.text


def test_demo_login_still_works_when_enabled(client, monkeypatch):
    """Opt-in keeps the public demo working."""
    from app.api import auth as auth_module

    monkeypatch.setenv("ENABLE_DEMO", "true")

    res = client.post("/api/auth/demo")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token"]
    assert body["user"]["role"] == "operator"


# ── 2. An anonymous caller can never stop a live session ───────────────


def test_anonymous_demo_login_does_not_stop_live_session(client, monkeypatch):
    """The core availability fix: no anonymous request may end monitoring."""
    from app.api import auth as auth_module

    monkeypatch.setenv("ENABLE_DEMO", "true")

    # Simulate a running monitoring session and record whether the demo login
    # tried to stop it.
    class _FakeService:
        def __init__(self) -> None:
            self.stopped = 0

        def is_running(self) -> bool:
            return True

        def stop_session(self, *args, **kwargs) -> None:
            self.stopped += 1

    service = _FakeService()
    monkeypatch.setattr(auth_module, "get_live_service_or_none", lambda: service)
    # Pretend the process is NOT a synthetic-data deployment.
    monkeypatch.setattr(auth_module, "_demo_is_demo_deployment", lambda: False)

    assert client.post("/api/auth/demo").status_code == 200
    assert service.stopped == 0, "anonymous demo login stopped a live session"


def test_demo_deployment_still_resets_a_leftover_session(client, monkeypatch):
    """On a real demo deployment the clean-slate reset is preserved."""
    from app.api import auth as auth_module

    monkeypatch.setenv("ENABLE_DEMO", "true")

    class _FakeService:
        def __init__(self) -> None:
            self.stopped = 0

        def is_running(self) -> bool:
            return True

        def stop_session(self, *args, **kwargs) -> None:
            self.stopped += 1

    service = _FakeService()
    monkeypatch.setattr(auth_module, "get_live_service_or_none", lambda: service)
    monkeypatch.setattr(auth_module, "_demo_is_demo_deployment", lambda: True)

    assert client.post("/api/auth/demo").status_code == 200
    assert service.stopped == 1


def test_demo_reset_failure_does_not_block_login(client, monkeypatch):
    """A service that explodes on stop must not 500 the demo login."""
    from app.api import auth as auth_module

    monkeypatch.setenv("ENABLE_DEMO", "true")

    class _BrokenService:
        def is_running(self) -> bool:
            raise RuntimeError("camera hardware vanished")

    monkeypatch.setattr(auth_module, "get_live_service_or_none", lambda: _BrokenService())
    monkeypatch.setattr(auth_module, "_demo_is_demo_deployment", lambda: True)

    res = client.post("/api/auth/demo")
    assert res.status_code == 200, res.text
    assert res.json()["token"]


# ── 3. The 404 must not leak ────────────────────────────────────────────


def test_disabled_demo_login_does_not_leak_seeded_account(client, monkeypatch):
    """A 404 body must not reveal that a demo operator account exists."""
    from app.api import auth as auth_module

    monkeypatch.delenv("ENABLE_DEMO", raising=False)
    monkeypatch.setattr(auth_module.settings, "DEBUG", False)

    res = client.post("/api/auth/demo")
    body = res.text
    assert "operator@example.local" not in body
    assert "demo" not in body.lower() or "not found" in body.lower()