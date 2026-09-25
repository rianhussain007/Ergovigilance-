"""Authentication endpoints."""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.database import (
    clear_login_failures,
    get_user_by_email,
    insert_audit_log,
    record_login_attempt,
)
from app.core.mfa import (
    MFAUnavailableError,
    get_mfa_status,
    pyotp_available,
    verify_totp,
)
from app.core.security import (
    AuthenticatedUser,
    DUMMY_PASSWORD_HASH,
    JWT_TTL_SECONDS,
    MFA_PENDING_TTL_SECONDS,
    consume_pending_mfa_token,
    create_access_token,
    create_pending_mfa_token,
    verify_password,
)
from app.core.config import settings

import os
import logging

from app.services.live_monitor import get_live_service_or_none

router = APIRouter()

logger = logging.getLogger(__name__)

# Brute-force protection lives in the rate-limit middleware: per-IP throttling
# of the token-issuing endpoints (/auth/login, /auth/demo), 10 attempts/min by
# default — see app/core/rate_limit.py.
#
# There is deliberately no per-account lockout here. Locking a known email let
# anyone deny service to that user on purpose, so failures are recorded for the
# audit trail (record_login_attempt below) and throttled by IP instead.


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginUser(BaseModel):
    id: int
    email: str
    role: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: str
    user: LoginUser


class MFAChallenge(BaseModel):
    """Password half succeeded; a TOTP code is still required.

    Carries no access token — ``pending_token`` can only be redeemed by
    POST /auth/login/mfa and is rejected by ``get_current_user``.
    """

    mfa_required: bool = True
    pending_token: str
    expires_in: int
    email: str


class MFALoginRequest(BaseModel):
    pending_token: str
    # Optional so a MISSING code produces our 401 + audit entry rather than a
    # 422 validation error that never reaches the auth path.
    code: str = ""


def _client_ip(request: Request) -> str:
    """Best-effort client IP.

    X-Forwarded-For is only honored when TRUST_PROXY_HEADERS=true (i.e. the API
    sits behind a reverse proxy that overwrites the header). Otherwise a client
    could spoof it to bypass per-IP rate limiting.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _audit(actor_id, actor_email, action_type, target_type, target_id, details=None):
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=actor_id,
        actor_email=actor_email,
        actor_role="system",
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )


@router.post("/auth/login", response_model=LoginResponse | MFAChallenge)
async def login(request: Request, body: LoginRequest):
    email = body.email.strip()
    ip = _client_ip(request)

    # Per-IP login throttling (10 attempts/min) is enforced by
    # RateLimitMiddleware._is_auth_rate_limited in app/core/rate_limit.py;
    # every attempt is also recorded below for the security audit trail.

    row = get_user_by_email(email)
    # Compare against a fixed dummy hash for unknown emails so both paths run
    # bcrypt with the same cost (prevents account enumeration via timing).
    # Note: verify_password must run unconditionally — short-circuiting on
    # `row is None` would skip the bcrypt work and reintroduce the oracle.
    password_hash = row["password_hash"] if row is not None else DUMMY_PASSWORD_HASH
    # bcrypt at cost 12 costs ~400 ms of CPU — run it off the event loop so a
    # login can never freeze the dashboard/WS polling for other clients.
    password_ok = await asyncio.to_thread(verify_password, body.password, password_hash)
    if row is None or not password_ok:
        record_login_attempt(email, ip, success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    record_login_attempt(email, ip, success=True)
    clear_login_failures(email=email)  # user proved ownership — drop their failed rows
    user = AuthenticatedUser(id=row["id"], email=row["email"], role=row["role"])

    # ── Second factor (opt-in) ──────────────────────────────────────────
    # The password is proved at this point, but an MFA-enrolled account must not
    # receive an access token until the TOTP code is verified.
    if get_mfa_status(user.id).get("enabled"):
        if not pyotp_available():
            # Fail CLOSED: an enabled second factor that cannot be checked must
            # block the login rather than silently downgrade it to one factor.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MFA unavailable",
            )
        return MFAChallenge(
            mfa_required=True,
            pending_token=create_pending_mfa_token(user),
            expires_in=MFA_PENDING_TTL_SECONDS,
            email=user.email,
        )

    # Log to audit trail
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="user_login",
        target_type=None,
        target_id=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=None,
    )

    now = int(time.time())
    return LoginResponse(
        token=create_access_token(user),
        expires_in=JWT_TTL_SECONDS,
        expires_at=datetime.fromtimestamp(now + JWT_TTL_SECONDS, tz=timezone.utc).isoformat(),
        user=LoginUser(id=user.id, email=user.email, role=user.role),
    )


@router.post("/auth/login/mfa", response_model=LoginResponse)
async def login_with_mfa(request: Request, body: MFALoginRequest):
    """Complete a login by presenting the TOTP code for a pending challenge.

    The pending token is consumed on FIRST presentation, so a challenge can be
    used exactly once — otherwise a holder could grind 6-digit codes for the
    whole 300 s window.
    """
    ip = _client_ip(request)

    try:
        payload = consume_pending_mfa_token(body.pending_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA challenge",
        ) from exc

    user = AuthenticatedUser(
        id=int(payload["sub"]), email=payload["email"], role=payload["role"]
    )

    def _audit_mfa_failure(reason: str) -> None:
        insert_audit_log(
            id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            actor_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            action_type="mfa_login_failed",
            target_type=None,
            target_id=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=reason,
        )
        record_login_attempt(user.email, ip, success=False)

    code = body.code.strip()
    if not code:
        _audit_mfa_failure("missing TOTP code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
        )

    try:
        code_ok = verify_totp(user.id, code)
    except MFAUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MFA unavailable"
        ) from exc

    if not code_ok:
        _audit_mfa_failure("invalid TOTP code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
        )

    record_login_attempt(user.email, ip, success=True)
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="user_login",
        target_type=None,
        target_id=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details="MFA verified",
    )

    now = int(time.time())
    return LoginResponse(
        token=create_access_token(user),
        expires_in=JWT_TTL_SECONDS,
        expires_at=datetime.fromtimestamp(now + JWT_TTL_SECONDS, tz=timezone.utc).isoformat(),
        user=LoginUser(id=user.id, email=user.email, role=user.role),
    )


@router.post("/auth/demo", response_model=LoginResponse)
async def demo_login():
    """One-click demo login — returns a token for the built-in demo operator.

    No credentials required. Enables DEMO_MODE so the dashboard shows
    synthetic sessions, alerts, and recommendations.
    """
    # Activate demo mode so the repository layer serves synthetic data
    os.environ["DEMO_MODE"] = "true"

    # Reset any in-flight monitoring session so every Try Demo starts clean
    # (an active session from a previous visitor would otherwise keep running
    # and leak stale frames/alerts into the new demo).
    try:
        service = get_live_service_or_none()
        if service is not None and service.is_running():
            logger.info("Stopping leftover session before demo login")
            service.stop_session()
    except Exception:
        logger.exception("Failed to reset active session during demo login")

    # Use the seeded operator account
    row = get_user_by_email("operator@example.local")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo mode unavailable — seed data not initialized.",
        )

    user = AuthenticatedUser(id=row["id"], email=row["email"], role=row["role"])

    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="demo_login",
        target_type=None,
        target_id=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details="Demo mode activated",
    )

    now = int(time.time())
    return LoginResponse(
        token=create_access_token(user),
        expires_in=JWT_TTL_SECONDS,
        expires_at=datetime.fromtimestamp(now + JWT_TTL_SECONDS, tz=timezone.utc).isoformat(),
        user=LoginUser(id=user.id, email=user.email, role=user.role),
    )
