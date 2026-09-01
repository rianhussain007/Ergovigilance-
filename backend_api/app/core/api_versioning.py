"""API Versioning Middleware.

Supports three versioning strategies:
1. URL path: /api/v1/sessions, /api/v2/sessions
2. Header: Accept: application/vnd.ergovigilance.v1+json
3. Query param: /api/sessions?version=1

Version negotiation priority:
1. URL path (highest priority)
2. Header
3. Query param
4. Default to latest version
"""

import re
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Supported API versions
SUPPORTED_VERSIONS = ["v1"]
DEFAULT_VERSION = "v1"
LATEST_VERSION = "v1"


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Adds API version headers and handles version negotiation."""

    async def dispatch(self, request: Request, call_next):
        # Skip versioning for non-API paths
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip for health/metrics/docs
        if path in ("/healthz", "/readyz", "/metrics", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Negotiate version
        version = self._negotiate_version(request)

        if version not in SUPPORTED_VERSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "unsupported_version",
                    "message": f"API version '{version}' is not supported. Supported: {SUPPORTED_VERSIONS}",
                    "supported_versions": SUPPORTED_VERSIONS,
                },
            )

        # Add version to request state
        request.state.api_version = version

        # Process request
        response = await call_next(request)

        # Add version headers to response
        response.headers["X-API-Version"] = version
        response.headers["X-API-Supported-Versions"] = ",".join(SUPPORTED_VERSIONS)
        response.headers["X-API-Latest-Version"] = LATEST_VERSION

        return response

    def _negotiate_version(self, request: Request) -> str:
        """Determine API version from request."""
        path = request.url.path

        # 1. URL path versioning: /api/v1/sessions
        match = re.match(r"/api/(v\d+)/", path)
        if match:
            return match.group(1)

        # 2. Header versioning: Accept: application/vnd.ergovigilance.v1+json
        accept = request.headers.get("accept", "")
        match = re.search(r"application/vnd\.ergovigilance\.(v\d+)\+json", accept)
        if match:
            return match.group(1)

        # 3. Query parameter: ?version=1
        version_param = request.query_params.get("version")
        if version_param:
            v = f"v{version_param}" if not version_param.startswith("v") else version_param
            return v

        # 4. Default
        return DEFAULT_VERSION


def get_api_version(request: Request) -> str:
    """Get the negotiated API version from request state."""
    return getattr(request.state, "api_version", DEFAULT_VERSION)
