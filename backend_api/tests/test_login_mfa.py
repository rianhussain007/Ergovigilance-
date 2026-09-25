"""MFA second factor on /auth/login (app/api/auth.py + app/core/mfa.py).

Covers the challenge flow and, more importantly, the fail-CLOSED rule:

* ``pyotp`` missing + MFA enabled  -> 503, login refused
* ``pyotp`` missing + MFA not set  -> ordinary login, unchanged (MFA is opt-in)

A dedicated account is used rather than a seeded one because the auth DB is
shared by the whole test session: enabling MFA on e.g. ``safety@example.local``
would leak a challenge into unrelated tests that log in with a password only.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

MFA_EMAIL = "mfa-subject@example.local"
MFA_PASSWORD = "MfaSubjectPass123!"
PLAIN_EMAIL = "operator@example.local"  # seeded, no MFA
PLAIN_PASSWORD = "OperatorPass123!"


@pytest.fixture(scope="module")
def client():
    """The real app, without entering its lifespan.

    ``init_local_database()`` is called directly because it is what seeds the
    login accounts. Going through ``with TestClient(app)`` would also start the
    assistant corpus load + auto-recovery and then emit the pre-existing
    ``RuntimeError: generator didn't stop`` on teardown (one per module that
    enters the lifespan), which these tests have no business adding to.
    """
    from app.core.database import init_local_database
    from app.main import app

    init_local_database()
    return TestClient(app)


def _new_totp_codes(secret: str) -> list[str]:
    """Codes the server will currently accept (now, now-30s, now+30s)."""
    import pyotp

    totp = pyotp.TOTP(secret)
    now = int(time.time())
    return [totp.at(now + 30 * delta) for delta in (-1, 0, 1)]


def _wrong_code(secret: str) -> str:
    """A 6-digit code guaranteed outside the accepted window."""
    accepted = _new_totp_codes(secret)
    for i in range(1_000_000):
        candidate = f"{i:06d}"
        if candidate not in accepted:
            return candidate
    raise AssertionError("no unused 6-digit code found")  # pragma: no cover


@pytest.fixture()
def mfa_user():
    """A dedicated account with MFA enabled; removed on teardown."""
    from app.core import mfa as mfa_core
    from app.core.database import get_connection, get_user_by_email
    from app.core.security import hash_password

    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE email = ?", (MFA_EMAIL,))
        conn.execute(
            "INSERT INTO users (email, password_hash, role, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                MFA_EMAIL,
                hash_password(MFA_PASSWORD),
                "safety_mgr",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (MFA_EMAIL,)
        ).fetchone()
        user_id = int(row["id"])

    # Enroll: write a secret, then flip enabled directly so the fixture does not
    # depend on the /mfa/* API being reachable from this test module.
    result = mfa_core.generate_mfa_secret(user_id)
    assert "error" not in result, result
    with mfa_core._get_db() as conn:
        conn.execute(
            "UPDATE mfa_settings SET enabled = 1 WHERE user_id = ?", (user_id,)
        )
        conn.commit()

    try:
        yield {"user_id": user_id, "secret": result["secret"]}
    finally:
        with mfa_core._get_db() as conn:
            conn.execute("DELETE FROM mfa_settings WHERE user_id = ?", (user_id,))
            conn.commit()
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE email = ?", (MFA_EMAIL,))


def _password_login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )


def _mfa_login(client: TestClient, pending_token: str, code: str):
    return client.post(
        "/api/auth/login/mfa",
        json={"pending_token": pending_token, "code": code},
    )


# ── The challenge ──────────────────────────────────────────────────────


def test_password_only_returns_challenge_not_token(client, mfa_user):
    """(c) Right password, MFA on -> mfa_required, and NO access token."""
    res = _password_login(client, MFA_EMAIL, MFA_PASSWORD)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body.get("mfa_required") is True
    assert "token" not in body, "an MFA-enrolled account must not get a token yet"
    assert body["pending_token"]
    assert body["expires_in"] > 0


def test_correct_code_issues_token(client, mfa_user):
    """(a) password + valid TOTP -> normal LoginResponse."""
    challenge = _password_login(client, MFA_EMAIL, MFA_PASSWORD).json()
    assert challenge.get("mfa_required") is True

    res = _mfa_login(client, challenge["pending_token"], _new_totp_codes(mfa_user["secret"])[0])
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == MFA_EMAIL
    assert body["user"]["role"] == "safety_mgr"
    assert "pending_token" not in body


def test_wrong_code_is_401_and_issues_no_token(client, mfa_user):
    """(b) valid password + wrong TOTP -> 401, no token anywhere."""
    challenge = _password_login(client, MFA_EMAIL, MFA_PASSWORD).json()

    res = _mfa_login(client, challenge["pending_token"], _wrong_code(mfa_user["secret"]))
    assert res.status_code == 401, res.text
    assert "token" not in res.json()


def test_missing_code_is_401(client, mfa_user):
    """A missing code reaches the auth path as a 401, not a 422."""
    challenge = _password_login(client, MFA_EMAIL, MFA_PASSWORD).json()

    res = client.post(
        "/api/auth/login/mfa", json={"pending_token": challenge["pending_token"]}
    )
    assert res.status_code == 401, res.text
    assert "token" not in res.json()


def test_pending_token_is_single_use(client, mfa_user):
    """(f) redeeming the same challenge twice -> 401 on the second try."""
    challenge = _password_login(client, MFA_EMAIL, MFA_PASSWORD).json()
    pending = challenge["pending_token"]
    code = _new_totp_codes(mfa_user["secret"])[0]

    first = _mfa_login(client, pending, code)
    assert first.status_code == 200, first.text

    replay = _mfa_login(client, pending, code)
    assert replay.status_code == 401, replay.text
    assert "token" not in replay.json()


def test_pending_token_is_not_a_session_token(client, mfa_user):
    """(g) the challenge must be rejected by get_current_user."""
    challenge = _password_login(client, MFA_EMAIL, MFA_PASSWORD).json()
    pending = challenge["pending_token"]

    res = client.get(
        "/api/mfa/status", headers={"Authorization": f"Bearer {pending}"}
    )
    assert res.status_code == 401, res.text

    # Sanity: once MFA completes, the real token IS accepted.
    code = _new_totp_codes(mfa_user["secret"])[0]
    real = _mfa_login(client, pending, code)
    assert real.status_code == 200, real.text
    ok = client.get(
        "/api/mfa/status",
        headers={"Authorization": f"Bearer {real.json()['token']}"},
    )
    assert ok.status_code == 200, ok.text


def test_replayed_challenge_is_rejected_even_with_a_valid_code(client, mfa_user):
    """A stolen-and-used challenge is dead regardless of a correct code."""
    challenge = _password_login(client, MFA_EMAIL, MFA_PASSWORD).json()
    pending = challenge["pending_token"]
    code = _new_totp_codes(mfa_user["secret"])[0]

    assert _mfa_login(client, pending, code).status_code == 200
    assert _mfa_login(client, pending, code).status_code == 401


# ── Fail-closed dependency handling ────────────────────────────────────


def test_pyotp_missing_with_mfa_enabled_refuses_login(client, mfa_user, monkeypatch):
    """(d) enabled MFA + no TOTP library -> 503, never a silent one-factor login."""
    from app.core import mfa as mfa_core

    monkeypatch.setattr(mfa_core, "pyotp", None)

    res = _password_login(client, MFA_EMAIL, MFA_PASSWORD)
    assert res.status_code == 503, res.text
    assert "MFA unavailable" in res.json()["detail"]
    assert "token" not in res.json()


def test_pyotp_missing_with_mfa_enabled_fails_closed_in_verify_totp(mfa_user, monkeypatch):
    """The core rule: verify_totp raises instead of returning True."""
    from app.core import mfa as mfa_core

    monkeypatch.setattr(mfa_core, "pyotp", None)

    with pytest.raises(mfa_core.MFAUnavailableError):
        mfa_core.verify_totp(mfa_user["user_id"], "000000")


def test_pyotp_missing_without_mfa_logs_in_normally(client, monkeypatch):
    """(e) MFA is opt-in, so a missing library must not block ordinary users."""
    from app.core import mfa as mfa_core

    monkeypatch.setattr(mfa_core, "pyotp", None)

    res = _password_login(client, PLAIN_EMAIL, PLAIN_PASSWORD)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token"]
    assert "mfa_required" not in body


def test_verify_totp_passes_through_when_mfa_is_not_enabled(monkeypatch):
    """Unenrolled users keep working with pyotp absent (unchanged behavior)."""
    from app.core import mfa as mfa_core

    monkeypatch.setattr(mfa_core, "pyotp", None)
    # user_id 999999 has no mfa_settings row at all.
    assert mfa_core.verify_totp(999999, "000000") is True
