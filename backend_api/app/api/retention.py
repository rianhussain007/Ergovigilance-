"""Data retention endpoints (admin only)."""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.services.retention import run_retention, set_retention_config, storage_stats

router = APIRouter()


class RetentionConfigUpdate(BaseModel):
    """Partial update of the retention policy (all fields optional)."""
    session_retention_days: int | None = None
    recording_retention_days: int | None = None
    recordings_max_gb: float | None = None


@router.get("/retention/stats")
async def retention_stats(
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Current disk usage and retention policy (admin only)."""
    return storage_stats()


@router.put("/retention/config")
async def update_retention_config(
    body: RetentionConfigUpdate,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Update the retention policy (admin only). Partial updates supported."""
    from fastapi import HTTPException
    policy, persisted = set_retention_config(body.model_dump(exclude_none=True))
    if not persisted:
        raise HTTPException(
            status_code=500,
            detail="Retention policy could not be persisted (read-only filesystem?) — the change will not survive a restart.",
        )
    return {"status": "ok", "policy": policy}


@router.post("/retention/run")
async def trigger_retention(
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Trigger a retention pass immediately (admin only)."""
    stats = await asyncio.to_thread(run_retention)
    return {"status": "ok", "stats": stats}
