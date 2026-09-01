"""Request ID middleware for distributed tracing.

Adds a unique X-Request-ID to every request/response for tracing
across frontend → backend → cloud core → webhooks.

Usage in main.py:
    from app.core.request_id import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)
"""

import uuid
import logging
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable for accessing request ID anywhere in the request lifecycle
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Get the current request's ID. Returns '-' if outside a request context."""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and response."""

    async def dispatch(self, request: Request, call_next):
        # Use existing X-Request-ID header if present (for distributed tracing)
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # Set in context variable for logging
        token = request_id_var.set(req_id)

        # Store on request state for access in endpoints
        request.state.request_id = req_id

        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        # Add to response headers
        response.headers["x-request-id"] = req_id

        return response
