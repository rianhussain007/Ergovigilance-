"""YOLO Cloud Core — API Key Authentication.

Middleware that validates API keys from the X-API-Key header.
Falls back to allowing all requests when DATABASE_URL is not set (dev mode).

Usage in FastAPI:
    from yolo_cloud.auth import require_api_key, get_tenant_id

    @router.get("/cameras")
    async def list_cameras(tenant: dict = Depends(require_api_key)):
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

logger = logging.getLogger(__name__)

# When true, API key auth is bypassed (dev mode, no DB)
_DEV_MODE = not os.getenv("DATABASE_URL", "").strip()


def _get_api_key_from_header(x_api_key: Optional[str] = Header(None)) -> Optional[str]:
    return x_api_key


def _get_bearer_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> dict:
    """Dependency that requires a valid API key or JWT token.

    Returns:
        dict with tenant_id, name, key_id (or defaults for dev mode)

    Raises:
        HTTPException 401 if the key is invalid
    """
    # Dev mode: no DB configured, allow all
    if _DEV_MODE:
        return {"tenant_id": "default", "name": "dev-mode", "key_id": "dev"}

    api_key = x_api_key or _get_bearer_token(authorization)

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header or Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Check for dev-mode bypass key
    if api_key == "dev-mode-key-not-for-production":
        return {"tenant_id": "default", "name": "dev-mode", "key_id": "dev"}

    from yolo_cloud.storage import validate_api_key

    tenant = validate_api_key(api_key)
    if tenant is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Attach tenant info to request state for downstream use
    request.state.tenant = tenant
    return tenant


async def optional_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> dict:
    """Dependency that optionally validates an API key.

    Returns tenant info if a valid key is provided, or defaults if not.
    Useful for endpoints that work with or without auth.
    """
    if _DEV_MODE:
        return {"tenant_id": "default", "name": "dev-mode", "key_id": "dev"}

    api_key = x_api_key or _get_bearer_token(authorization)
    if not api_key:
        return {"tenant_id": "default", "name": "anonymous"}

    from yolo_cloud.storage import validate_api_key
    tenant = validate_api_key(api_key)
    if tenant is None:
        return {"tenant_id": "default", "name": "anonymous"}
    return tenant


def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from request state (set by require_api_key)."""
    tenant = getattr(request.state, "tenant", None)
    return tenant.get("tenant_id", "default") if tenant else "default"
