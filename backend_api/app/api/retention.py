"""Data retention endpoints (admin only)."""

import asyncio

from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.services.retention import run_retention, storage_stats

router = APIRouter()


@router.get("/retention/stats")
async def retention_stats(
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Current disk usage and retention policy (admin only)."""
    return storage_stats()


@router.post("/retention/run")
async def trigger_retention(
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Trigger a retention pass immediately (admin only)."""
    stats = await asyncio.to_thread(run_retention)
    return {"status": "ok", "stats": stats}
