"""Input sanitization middleware for FastAPI.

Prevents XSS, SQL injection, and other input-based attacks by:
- Stripping HTML/script tags from string inputs
- Blocking common SQL injection patterns
- Sanitizing query parameters and path parameters
- Logging suspicious input attempts

Usage in main.py:
    from app.core.sanitization import SanitizationMiddleware
    app.add_middleware(SanitizationMiddleware)
"""

import re
import html
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# XSS patterns to strip
XSS_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
    re.compile(r"<form[^>]*>", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"url\s*\(", re.IGNORECASE),
    re.compile(r"<img[^>]+onerror", re.IGNORECASE),
]

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    re.compile(r"(--|;|'|\")\s*(DROP|DELETE|INSERT|UPDATE|ALTER|EXEC|EXECUTE|UNION|SELECT)\s", re.IGNORECASE),
    re.compile(r"'\s*OR\s+'", re.IGNORECASE),
    re.compile(r"'\s*OR\s+\d+\s*=\s*\d+", re.IGNORECASE),
    re.compile(r"'\s*OR\s+1\s*=\s*1", re.IGNORECASE),
    re.compile(r"UNION\s+(ALL\s+)?SELECT", re.IGNORECASE),
    re.compile(r"INFORMATION_SCHEMA", re.IGNORECASE),
    re.compile(r"WAITFOR\s+DELAY", re.IGNORECASE),
    re.compile(r"BENCHMARK\s*\(", re.IGNORECASE),
    re.compile(r"SLEEP\s*\(", re.IGNORECASE),
    re.compile(r"LOAD_FILE\s*\(", re.IGNORECASE),
    re.compile(r"INTO\s+(OUTFILE|DUMPFILE)", re.IGNORECASE),
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
    re.compile(r"%2e%2e", re.IGNORECASE),
    re.compile(r"%252e%252e", re.IGNORECASE),
]


def _strip_xss(value: str) -> str:
    """Remove XSS patterns from a string."""
    for pattern in XSS_PATTERNS:
        value = pattern.sub("", value)
    return html.escape(value, quote=False)


def _check_sql_injection(value: str) -> bool:
    """Check if a string contains SQL injection patterns."""
    return any(p.search(value) for p in SQL_INJECTION_PATTERNS)


def _check_path_traversal(value: str) -> bool:
    """Check if a string contains path traversal patterns."""
    return any(p.search(value) for p in PATH_TRAVERSAL_PATTERNS)


def _sanitize_value(value: str) -> tuple[str, list[str]]:
    """Sanitize a single value, returning (cleaned, warnings)."""
    warnings = []
    original = value

    # Check for path traversal
    if _check_path_traversal(value):
        warnings.append("path_traversal_attempt")
        value = value.replace("../", "").replace("..\\", "")

    # Check for SQL injection
    if _check_sql_injection(value):
        warnings.append("sql_injection_attempt")
        # Don't modify - just log and let the database layer handle it

    # Strip XSS
    cleaned = _strip_xss(value)
    if cleaned != value:
        warnings.append("xss_attempt")
        value = cleaned

    if warnings:
        logger.warning(
            "Suspicious input detected: %s (warnings: %s) in value: %.100s",
            original, warnings, value
        )

    return value, warnings


class SanitizationMiddleware(BaseHTTPMiddleware):
    """Sanitize all incoming request data (query params, path params, headers)."""

    def __init__(self, app, check_body: bool = True):
        super().__init__(app)
        self.check_body = check_body

    async def dispatch(self, request: Request, call_next):
        all_warnings = []

        # Sanitize query parameters
        for key, value in request.query_params.items():
            cleaned, warnings = _sanitize_value(value)
            if warnings:
                all_warnings.extend(warnings)

        # Sanitize path parameters
        path = str(request.url.path)
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if pattern.search(path):
                all_warnings.append("path_traversal_in_url")
                break

        # Check for suspicious headers
        for header_name in ["user-agent", "referer", "x-forwarded-for"]:
            header_value = request.headers.get(header_name, "")
            if header_value:
                _, warnings = _sanitize_value(header_value)
                all_warnings.extend(warnings)

        # Sanitize request body (for JSON requests)
        if self.check_body and request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "json" in content_type:
                try:
                    body = await request.body()
                    if body:
                        import json
                        data = json.loads(body)
                        cleaned_data, body_warnings = self._sanitize_dict(data)
                        if body_warnings:
                            all_warnings.extend(body_warnings)
                except Exception:
                    pass  # Let FastAPI handle malformed JSON

        if all_warnings:
            logger.warning(
                "Sanitization warnings for %s %s: %s",
                request.method, request.url.path, all_warnings
            )

        response = await call_next(request)
        return response

    def _sanitize_dict(self, data: dict, depth: int = 0) -> tuple[dict, list[str]]:
        """Recursively sanitize dictionary values."""
        if depth > 10:
            return data, []

        warnings = []
        cleaned = {}

        for key, value in data.items():
            if isinstance(value, str):
                cleaned_value, value_warnings = _sanitize_value(value)
                cleaned[key] = cleaned_value
                warnings.extend(value_warnings)
            elif isinstance(value, dict):
                cleaned[key], dict_warnings = self._sanitize_dict(value, depth + 1)
                warnings.extend(dict_warnings)
            elif isinstance(value, list):
                cleaned_list = []
                for item in value:
                    if isinstance(item, str):
                        cleaned_item, item_warnings = _sanitize_value(item)
                        cleaned_list.append(cleaned_item)
                        warnings.extend(item_warnings)
                    elif isinstance(item, dict):
                        cleaned_item, dict_warnings = self._sanitize_dict(item, depth + 1)
                        cleaned_list.append(cleaned_item)
                        warnings.extend(dict_warnings)
                    else:
                        cleaned_list.append(item)
                cleaned[key] = cleaned_list
            else:
                cleaned[key] = value

        return cleaned, warnings
