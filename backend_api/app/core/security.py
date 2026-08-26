"""Authentication primitives for local SQLite-backed auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import warnings
from dataclasses import dataclass
from typing import Any

try:
    import bcrypt
except ImportError as exc:  # pragma: no cover - startup configuration error
    raise RuntimeError("bcrypt is required for local authentication. Install backend_api requirements.") from exc

from app.core.config import settings


# Well-known development default — kept ONLY so production startup can reject
# it explicitly if someone sets it by hand. Debug mode never signs with it.
_DEV_JWT_SECRET = "dev-local-ergo-vigilance-secret-change-me"


def _resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret, failing fast in production.

    Outside debug mode the secret must be explicitly provided and must not be
    the well-known development default — otherwise tokens would be forgeable.
    """
    secret = os.getenv("AUTH_JWT_SECRET", "").strip()
    if secret:
        if not settings.DEBUG and len(secret) < 32:
            raise RuntimeError(
                "AUTH_JWT_SECRET is too short. Use at least 32 characters when DEBUG=false. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if secret == _DEV_JWT_SECRET and not settings.DEBUG:
            raise RuntimeError(
                "AUTH_JWT_SECRET is set to the known development default. "
                "Provide a strong, unique secret when DEBUG=false."
            )
        return secret
    if not settings.DEBUG:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be set when DEBUG=false (production). "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    # Debug mode: sign with an EPHEMERAL per-process secret instead of the
    # committed constant. A secret that lives in the repo is not a secret;
    # a random one that dies with the process can never leak from source.
    warnings.warn(
        "AUTH_JWT_SECRET not set — using an ephemeral per-process secret "
        "(tokens invalidate on restart). Set a strong AUTH_JWT_SECRET for any "
        "non-local deployment.",
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


JWT_SECRET = _resolve_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = int(os.getenv("AUTH_JWT_TTL_SECONDS", "28800"))

# Short-lived tokens scoped to the MJPEG video stream only. These are what
# the frontend puts in the <img> URL (query strings end up in browser history
# and access logs — they must never carry the 8-hour API JWT).
STREAM_TOKEN_TTL_SECONDS = int(os.getenv("STREAM_TOKEN_TTL_SECONDS", "600"))

# Fixed dummy hash compared against when the account does not exist, so that
# unknown emails take the same bcrypt time as known ones (anti-enumeration).
DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"ergo-vigilance-dummy-password", bcrypt.gensalt()).decode("utf-8")


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    role: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_access_token(user: AuthenticatedUser) -> str:
    now = int(time.time())
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
    }
    signing_input = ".".join([
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def create_stream_token(user_id: int, role: str) -> str:
    """Mint a short-lived token that grants ONLY video-stream access."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "purpose": "stream",
        "iat": now,
        "exp": now + STREAM_TOKEN_TTL_SECONDS,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(JWT_SECRET.encode("utf-8"), b"stream." + body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(signature)}"


def verify_stream_token(token: str) -> dict[str, Any] | None:
    """Validate a stream-scoped token. Returns its payload, or None if invalid/expired."""
    try:
        body, signature_b64 = token.split(".", 1)
        expected = hmac.new(JWT_SECRET.encode("utf-8"), b"stream." + body.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected, actual):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if payload.get("purpose") != "stream":
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError):
        return None


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    actual = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    return payload
