"""Response compression middleware for FastAPI.

Compresses responses larger than a threshold using gzip.
Reduces bandwidth for large JSON payloads (dashboards, reports, analytics).

Configurable via environment:
- COMPRESSION_MIN_SIZE: minimum response size in bytes to compress (default 500)
- COMPRESSION_LEVEL: gzip compression level 1-9 (default 6)

Usage in main.py:
    from app.core.compression import CompressionMiddleware
    app.add_middleware(CompressionMiddleware)
"""

import gzip
import os
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

COMPRESSION_MIN_SIZE = int(os.getenv("COMPRESSION_MIN_SIZE", "500"))
COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", "6"))

# MIME types eligible for compression
COMPRESSIBLE_TYPES = {
    "application/json",
    "application/javascript",
    "text/html",
    "text/css",
    "text/plain",
    "text/xml",
    "application/xml",
    "application/vnd.api+json",
}


class CompressionMiddleware(BaseHTTPMiddleware):
    """Compress responses using gzip when client accepts it."""

    def __init__(self, app, min_size: int = COMPRESSION_MIN_SIZE, level: int = COMPRESSION_LEVEL):
        super().__init__(app)
        self.min_size = min_size
        self.level = level

    async def dispatch(self, request: Request, call_next):
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding:
            return await call_next(request)

        response = await call_next(request)

        # Skip if already compressed or streaming
        if response.headers.get("content-encoding"):
            return response
        if response.headers.get("transfer-encoding") == "chunked":
            return response

        # Check content type
        content_type = response.headers.get("content-type", "")
        is_compressible = any(ct in content_type for ct in COMPRESSIBLE_TYPES)

        if not is_compressible:
            return response

        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                body += chunk.encode("utf-8")
            else:
                body += chunk

        # Compress if large enough
        if len(body) < self.min_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        compressed = gzip.compress(body, compresslevel=self.level)
        compression_ratio = len(compressed) / len(body) * 100

        logger.debug(
            "Compressed %s response: %d → %d bytes (%.1f%%)",
            request.url.path, len(body), len(compressed), compression_ratio
        )

        # Build new headers
        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed))
        headers["vary"] = "Accept-Encoding"

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
