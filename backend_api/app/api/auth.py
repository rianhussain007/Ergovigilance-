"""Authentication endpoints."""

import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.database import (
    clear_login_failures,
    count_recent_login_failures,
    get_user_by_email,
    insert_audit_log,
    record_login_attempt,
)
from app.core.security import (
    AuthenticatedUser,
    DUMMY_PASSWORD_HASH,
    JWT_TTL_SECONDS,
    create_access_token,
    verify_password,
)
from app.core.config import settings

router = APIRouter()

# Brute-force protection thresholds
LOGIN_MAX_FAILURES_PER_IP = 10
LOGIN_MAX_FAILURES_PER_EMAIL = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60


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


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    email = body.email.strip()
    ip = _client_ip(request)

    # Brute-force protection — reject before verifying credentials
    if count_recent_login_failures(ip=ip, window_seconds=LOGIN_FAILURE_WINDOW_SECONDS) >= LOGIN_MAX_FAILURES_PER_IP:
        _audit(None, "", "login_locked", "ip", ip, details="IP rate limit exceeded")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts from this address. Try again later.",
            headers={"Retry-After": str(LOGIN_LOCKOUT_SECONDS)},
        )
    if count_recent_login_failures(email=email, window_seconds=LOGIN_FAILURE_WINDOW_SECONDS) >= LOGIN_MAX_FAILURES_PER_EMAIL:
        _audit(None, email, "login_locked", "user", email, details="Account temporarily locked")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed attempts. Try again later.",
            headers={"Retry-After": str(LOGIN_LOCKOUT_SECONDS)},
        )

    row = get_user_by_email(email)
    # Compare against a fixed dummy hash for unknown emails so both paths run
    # bcrypt with the same cost (prevents account enumeration via timing).
    # Note: verify_password must run unconditionally — short-circuiting on
    # `row is None` would skip the bcrypt work and reintroduce the oracle.
    password_hash = row["password_hash"] if row is not None else DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, password_hash)
    if row is None or not password_ok:
        record_login_attempt(email, ip, success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    record_login_attempt(email, ip, success=True)
    clear_login_failures(email=email)  # unlock the account on success; IP history expires on its own
    user = AuthenticatedUser(id=row["id"], email=row["email"], role=row["role"])

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
