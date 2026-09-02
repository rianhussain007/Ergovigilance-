"""Organization-scoped API key authentication for the YOLO cloud core.

Validates API keys against the organizations table and provides
tenant context for all cloud core requests.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_org_by_api_key(api_key: str) -> Optional[dict]:
    """Look up organization by API key."""
    try:
        import sys
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
        from backend_api.app.core.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, slug, plan, max_cameras, max_workers FROM organizations WHERE api_key = ?",
                (api_key,)
            ).fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "slug": row[2],
                    "plan": row[3],
                    "max_cameras": row[4],
                    "max_workers": row[5],
                }
    except Exception as e:
        logger.warning("Failed to validate API key: %s", e)
    return None


def require_org_api_key(api_key: str = Security(api_key_header)) -> dict:
    """Dependency that validates the API key and returns org context.

    Usage:
        @router.get("/cameras")
        async def list_cameras(org: dict = Depends(require_org_api_key)):
            org_id = org["id"]
            ...
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    org = _get_org_by_api_key(api_key)
    if org is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return org


def optional_org_api_key(api_key: str = Security(api_key_header)) -> Optional[dict]:
    """Optional dependency — returns org context if valid key provided, None otherwise."""
    if not api_key:
        return None
    return _get_org_api_key(api_key)
