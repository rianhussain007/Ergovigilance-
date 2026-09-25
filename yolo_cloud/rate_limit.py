"""Per-IP sliding-window rate limiter for the YOLO Cloud Core API.

Two independent buckets per client IP:

  * **all requests** — ``RATE_LIMIT_REQUESTS`` per ``RATE_LIMIT_WINDOW_S``
  * **camera writes** (add / start / stop / identity scans) —
    ``RATE_LIMIT_CAMERA_WRITES`` per window

Previously the camera-write check was compared against the *total* request
count, so ordinary polling exhausted the write budget and a busy dashboard could
lock an operator out of starting a camera. The buckets are now separate.

The client IP comes from ``X-Forwarded-For`` **only** when ``TRUST_PROXY`` is
enabled (taking the Nth hop from the right, ``TRUSTED_PROXY_HOPS``); otherwise
the socket peer is used. Trusting the header unconditionally would let a client
choose its own bucket and bypass the limit entirely.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from yolo_cloud.config import settings

logger = logging.getLogger(__name__)

# Historic module-level defaults, kept for reference by operators/tests that
# still import them. Live limits come from settings (env-overridable).
WINDOW = 60
MAX_REQUESTS = 120
CAMERA_WRITE_LIMIT = 10


def client_ip(request: Request) -> str:
    """Resolve the client IP, honouring the proxy chain only when trusted."""
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if hops:
                idx = max(0, len(hops) - max(1, settings.TRUSTED_PROXY_HOPS))
                return hops[idx]
    return request.client.host if request.client else "unknown"


class CloudRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window limiter with separate read and camera-write buckets."""

    def __init__(self, app, window=None, max_requests=None, camera_write_limit=None):
        super().__init__(app)
        self.window = int(window or settings.RATE_LIMIT_WINDOW_S)
        self.max_requests = int(max_requests or settings.RATE_LIMIT_REQUESTS)
        self.camera_write_limit = int(camera_write_limit or settings.RATE_LIMIT_CAMERA_WRITES)
        self._all: dict[str, list[float]] = defaultdict(list)
        self._writes: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    @staticmethod
    def _prune(bucket: list[float], cutoff: float) -> list[float]:
        return [t for t in bucket if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        ip = client_ip(request)
        path = request.url.path
        now = time.time()
        cutoff = now - self.window
        is_write = request.method in ("POST", "PUT", "PATCH", "DELETE")
        is_camera_write = is_write and "/cameras" in path

        with self._lock:
            self._all[ip] = self._prune(self._all[ip], cutoff)
            self._writes[ip] = self._prune(self._writes[ip], cutoff)
            over_all = len(self._all[ip]) >= self.max_requests
            over_write = is_camera_write and len(self._writes[ip]) >= self.camera_write_limit
            if not over_all and not over_write:
                self._all[ip].append(now)
                if is_camera_write:
                    self._writes[ip].append(now)
            used = len(self._writes[ip]) if over_write else len(self._all[ip])

        if over_all or over_write:
            limit = self.camera_write_limit if over_write else self.max_requests
            logger.warning(
                "Rate limited %s on %s (%d/%d in %ds)", ip, path, used, limit, self.window,
            )
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window)},
            )

        return await call_next(request)


def limits_snapshot() -> dict:
    """Current effective limits (surfaced on /healthz for ops sanity)."""
    return {
        "window_s": settings.RATE_LIMIT_WINDOW_S,
        "requests": settings.RATE_LIMIT_REQUESTS,
        "camera_writes": settings.RATE_LIMIT_CAMERA_WRITES,
        "trust_proxy": settings.TRUST_PROXY,
        "trusted_proxy_hops": settings.TRUSTED_PROXY_HOPS,
        "require_tls": settings.REQUIRE_TLS,
    }
