"""Endpoints for the risk digest — on-demand generation and saved-digest listing."""

import asyncio
import logging

from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.services.report_digest import generate_digest, list_digests

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/reports/digest")
async def get_digests(
    user=Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """List saved risk digests (newest first)."""
    return {"digests": list_digests()}


@router.post("/reports/digest/generate")
async def generate_now(
    user=Depends(require_roles("safety_mgr", "admin")),
):
    """Generate a risk digest of the last 24 hours right now (safety-mgr+)."""
    result = await asyncio.to_thread(generate_digest, 24.0, True)
    digest = result["digest"]
    return {
        "saved": result["saved"],
        "path": result["path"],
        "summary": digest["summary"],
        "session_count": digest["summary"]["session_count"],
    }
