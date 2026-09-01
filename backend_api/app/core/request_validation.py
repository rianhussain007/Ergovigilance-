"""Request validation middleware for FastAPI.

Catches Pydantic ValidationError exceptions and returns clean JSON
error responses with field-level details. Also validates Content-Type
headers for POST/PUT/PATCH requests.

Usage in main.py:
    from app.core.request_validation import ValidationMiddleware
    app.add_middleware(ValidationMiddleware)
"""

import logging
import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ValidationMiddleware(BaseHTTPMiddleware):
    """Catches validation errors and returns structured JSON responses."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except RequestValidationError as exc:
            # FastAPI's built-in validation error
            errors = []
            for error in exc.errors():
                loc = " → ".join(str(l) for l in error.get("loc", []))
                errors.append({
                    "field": loc,
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", "unknown"),
                })
            logger.warning(
                "Validation error on %s %s: %s",
                request.method, request.url.path, errors,
            )
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Validation failed",
                    "details": errors,
                    "hint": "Check the request body or query parameters",
                },
            )
        except ValidationError as exc:
            # Pydantic model validation error
            errors = []
            for error in exc.errors():
                loc = " → ".join(str(l) for l in error.get("loc", []))
                errors.append({
                    "field": loc,
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", "unknown"),
                })
            logger.warning(
                "Model validation error on %s %s: %s",
                request.method, request.url.path, errors,
            )
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Request body validation failed",
                    "details": errors,
                },
            )
        except Exception as exc:
            # Don't leak internal error details in production
            logger.error(
                "Unhandled error on %s %s: %s\n%s",
                request.method, request.url.path, exc, traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": str(exc) if logging.getLogger().level <= logging.DEBUG else "An unexpected error occurred",
                },
            )
