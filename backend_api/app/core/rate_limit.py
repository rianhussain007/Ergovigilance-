"""Per-IP and per-role rate limiter middleware for FastAPI.

Limits per-IP request rates with role-based multipliers:
- admin: 3x default limit (1500 req/min)
- safety_mgr: 2x default limit (1000 req/min)
- supervisor: 1.5x default limit (750 req/min)
- operator: 1x default limit (500 req/min)

Configurable via environment:
- RATE_LIMIT_WINDOW: seconds per window (default 60)
- RATE_LIMIT_MAX_REQUESTS: base max requests per window (default 500)
- RATE_LIMIT_AUTH_MAX: max auth attempts per IP per window on the
  token-issuing endpoints (/auth/login, /auth/demo) (default 10)

Usage in main.py:
    from app.core.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
"""

import os
import time
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "500"))
AUTH_MAX = int(os.getenv("RATE_LIMIT_AUTH_MAX", "10"))

# Token-issuing endpoints get their own tighter per-IP bucket so the generic
# 500/min budget (from which /auth/ is exempt) can never be spent guessing
# credentials.
AUTH_PATHS = ("/auth/login", "/auth/demo")

# Role-based multipliers: admins get more headroom, operators are stricter
ROLE_MULTIPLIERS: dict[str, float] = {
    "admin": 3.0,
    "safety_mgr": 2.0,
    "supervisor": 1.5,
    "operator": 1.0,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter."""

    def __init__(self, app, window: int = WINDOW, max_requests: int = MAX_REQUESTS):
        super().__init__(app)
        self.window = window
        self.max_requests = max_requests
        # {ip: [(timestamp, path)]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        # Separate bucket for auth endpoints: {ip: [timestamp]}
        self._auth_requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        # X-Forwarded-For is only honored behind a trusted reverse proxy
        # (TRUST_PROXY_HEADERS=true). Otherwise a client could spoof the header
        # to dodge per-IP limits — including login throttling.
        if settings.TRUST_PROXY_HEADERS:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, ip: str, path: str, role: str = "operator") -> bool:
        now = time.time()
        cutoff = now - self.window

        # Clean old entries
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

        # Auth, search, settings, billing, health, and docs endpoints are exempt
        exempt = ["/auth/", "/search", "/settings", "/billing", "/healthz",
                  "/readyz", "/metrics", "/health", "/docs", "/redoc"]
        if any(e in path for e in exempt):
            return False

        # Apply role-based multiplier
        multiplier = ROLE_MULTIPLIERS.get(role, 1.0)
        limit = int(self.max_requests * multiplier)

        if len(self._requests[ip]) >= limit:
            return True

        self._requests[ip].append(now)
        return False

    def _is_auth_rate_limited(self, ip: str, path: str) -> bool:
        """Tighter per-IP limit for token-issuing endpoints (login, demo).

        Independent of the global budget so credential guessing is throttled
        even though /auth/ is exempt from the general limiter.
        """
        if not any(p in path for p in AUTH_PATHS):
            return False

        now = time.time()
        cutoff = now - self.window
        self._auth_requests[ip] = [t for t in self._auth_requests[ip] if t > cutoff]

        if len(self._auth_requests[ip]) >= AUTH_MAX:
            return True

        self._auth_requests[ip].append(now)
        return False

    def _extract_role_from_token(self, request: Request) -> str:
        """Extract user role from JWT token in Authorization header."""
        try:
            auth_header = request.headers.get("authorization", "")
            if not auth_header.startswith("Bearer "):
                return "operator"
            token = auth_header[7:]
            # Decode JWT payload (base64) to get role
            import base64
            import json
            parts = token.split(".")
            if len(parts) != 3:
                return "operator"
            payload = parts[1]
            # Add padding
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            data = json.loads(base64.urlsafe_b64decode(payload))
            return data.get("role", "operator")
        except Exception:
            return "operator"

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks, docs, and static files
        path = request.url.path
        if path in ("/healthz", "/readyz", "/health", "/", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        ip = self._get_client_ip(request)
        role = self._extract_role_from_token(request)

        if self._is_auth_rate_limited(ip, path):
            logger.warning("Auth rate limit exceeded for %s on %s", ip, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many authentication attempts. Try again later."},
                headers={"Retry-After": str(self.window)},
            )

        if self._is_rate_limited(ip, path, role):
            logger.warning("Rate limit exceeded for %s (role=%s) on %s", ip, role, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window)},
            )

        response = await call_next(request)

        # Add rate limit headers to response
        import base64 as _b64
        multiplier = ROLE_MULTIPLIERS.get(role, 1.0)
        limit = int(self.max_requests * multiplier)
        now = time.time()
        cutoff = now - self.window
        used = sum(1 for t in self._requests.get(ip, []) if t > cutoff)
        remaining = max(0, limit - used)
        reset_time = int(cutoff + self.window)

        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        response.headers["X-RateLimit-Role"] = role

        return response
