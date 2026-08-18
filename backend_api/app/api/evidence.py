"""Incident evidence package endpoint — one-click zip for OSHA/insurance review."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.auth import require_roles
from app.services.evidence_package import build_evidence_package

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions/{session_id}/evidence")
async def get_evidence_package(
    session_id: str,
    user=Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Download a zip of the session's evidence (summary, alerts, timeline, video)."""
    try:
        result = build_evidence_package(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface a clean 500, not a traceback
        logger.error("Evidence package build failed for %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to build evidence package") from exc

    return FileResponse(
        result["path"],
        media_type="application/zip",
        filename=f"evidence_{session_id}.zip",
    )
