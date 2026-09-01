"""Enterprise Security Headers Middleware for FastAPI.

Adds industry-standard security headers to all HTTP responses:
- Strict-Transport-Security (HSTS)
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
- Content-Security-Policy
- Cache-Control for API responses
"""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds enterprise security headers to all responses."""

    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.enable_hsts = os.getenv("ENABLE_HSTS", "false").lower() == "true"
        self.csp_report_uri = os.getenv("CSP_REPORT_URI", "")

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # HSTS — only when behind TLS termination (nginx/cloudflare)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy — leak no path info to third parties
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — disable unused browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
            "magnetometer=(), gyroscope=(), accelerometer=()"
        )

        # Content Security Policy
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob: https:",
            "font-src 'self' data:",
            "connect-src 'self' ws: wss: http://localhost:*",
            "media-src 'self' blob:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "upgrade-insecure-requests",
        ]
        if self.csp_report_uri:
            csp_parts.append(f"report-uri {self.csp_report_uri}")
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        # Cache control for API responses — never cache auth/data
        path = request.url.path
        if path.startswith("/api/") or path.startswith("/ws/"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Remove server identification
        if "server" in response.headers:
            del response.headers["server"]
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]

        return response
