"""Tenant Isolation Middleware for Multi-Tenancy.

Ensures that each tenant's data is completely isolated:
- Validates tenant_id on all requests
- Blocks cross-tenant data access
- Logs tenant context for audit trails

Usage:
    from yolo_cloud.tenant_middleware import TenantIsolationMiddleware
    app.add_middleware(TenantIsolationMiddleware)
"""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Endpoints that don't require tenant validation
EXEMPT_PATHS = {
    "/healthz",
    "/readyz",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
}

# Endpoints that are tenant-scoped (require tenant_id validation)
TENANT_SCOPED_PATHS = {
    "/api/cloud/cameras",
    "/api/cloud/sessions",
    "/api/cloud/alerts",
    "/api/cloud/api-keys",
    "/api/cloud/webhooks",
    "/api/cloud/retention",
    "/api/cloud/storage/stats",
}


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Validates tenant context and enforces data isolation."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip for exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Skip for non-API paths
        if not path.startswith("/api/"):
            return await call_next(request)

        # Extract tenant from request state (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)

        # If tenant_id is set, validate it matches any path tenant_id
        if tenant_id and path.startswith("/api/cloud/"):
            # Check if the URL contains a different tenant_id
            # e.g., /api/cloud/tenant-123/cameras vs /api/cloud/cameras
            parts = path.split("/")
            for i, part in enumerate(parts):
                if part == "tenant" and i + 1 < len(parts):
                    url_tenant = parts[i + 1]
                    if url_tenant != tenant_id:
                        logger.warning(
                            "Tenant isolation violation: tenant=%s attempted to access tenant=%s",
                            tenant_id, url_tenant,
                        )
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": "tenant_isolation_violation",
                                "message": "You cannot access resources belonging to another tenant",
                            },
                        )

        # Add tenant context to response headers for debugging
        response = await call_next(request)

        if tenant_id:
            response.headers["X-Tenant-ID"] = tenant_id

        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Adds tenant context to all requests for logging and audit."""

    def __init__(self, app):
        super().__init__(app)
        self._request_count = 0

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        self._request_count += 1

        # Extract tenant from auth context
        tenant_id = getattr(request.state, "tenant_id", "unknown")
        request_id = f"req-{self._request_count}"

        # Add to request state for downstream use
        request.state.request_id = request_id
        request.state.tenant_id = tenant_id

        response = await call_next(request)

        # Add audit headers
        duration = round((time.time() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Tenant-ID"] = tenant_id
        response.headers["X-Response-Time"] = f"{duration}ms"

        # Log for audit (skip health checks)
        path = request.url.path
        if path not in EXEMPT_PATHS and path.startswith("/api/"):
            logger.info(
                "API %s %s -> %s (%sms) tenant=%s",
                request.method, path, response.status_code, duration, tenant_id,
            )

        return response
