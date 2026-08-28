"""Simple in-memory rate limiter middleware for FastAPI.

Limits per-IP request rates to prevent abuse. Configurable via environment:
- RATE_LIMIT_WINDOW: seconds per window (default 60)
- RATE_LIMIT_MAX_REQUESTS: max requests per window (default 100)
- RATE_LIMIT_AUTH_MAX: max auth attempts per window (default 10)

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

logger = logging.getLogger(__name__)

WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
AUTH_MAX = int(os.getenv("RATE_LIMIT_AUTH_MAX", "10"))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter."""

    def __init__(self, app, window: int = WINDOW, max_requests: int = MAX_REQUESTS):
        super().__init__(app)
        self.window = window
        self.max_requests = max_requests
        # {ip: [(timestamp, path)]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        # Trust X-Forwarded-For when behind a proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, ip: str, path: str) -> bool:
        now = time.time()
        cutoff = now - self.window

        # Clean old entries
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

        # Auth endpoints have stricter limits
        limit = AUTH_MAX if "/auth/" in path else self.max_requests

        if len(self._requests[ip]) >= limit:
            return True

        self._requests[ip].append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static files
        path = request.url.path
        if path in ("/healthz", "/readyz", "/health", "/", "/docs", "/openapi.json"):
            return await call_next(request)

        ip = self._get_client_ip(request)

        if self._is_rate_limited(ip, path):
            logger.warning("Rate limit exceeded for %s on %s", ip, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window)},
            )

        return await call_next(request)
