"""Simple in-memory rate limiter for YOLO Cloud Core API."""

import time
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Default limits
WINDOW = 60  # seconds
MAX_REQUESTS = 120  # per window per IP
CAMERA_WRITE_LIMIT = 10  # camera add/delete per window


class CloudRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter for the cloud core."""

    def __init__(self, app, window: int = WINDOW, max_requests: int = MAX_REQUESTS):
        super().__init__(app)
        self.window = window
        self.max_requests = max_requests
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        ip = self._get_client_ip(request)
        path = request.url.path
        now = time.time()
        cutoff = now - self.window

        # Clean old entries
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

        # Write endpoints (POST/DELETE) on camera routes are stricter
        is_write = request.method in ("POST", "DELETE", "PUT", "PATCH")
        is_camera_write = is_write and "/cameras" in path
        limit = CAMERA_WRITE_LIMIT if is_camera_write else self.max_requests

        if len(self._requests[ip]) >= limit:
            logger.warning("Rate limited %s on %s (%d reqs in %ds)", ip, path, len(self._requests[ip]), self.window)
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window)},
            )

        self._requests[ip].append(now)
        response = await call_next(request)
        return response
