"""Safety Report endpoints — JSON data + PDF export."""

import json
import logging
import os
import sys
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import Response

ROOT = Path(__file__).resolve().parents[3]
if not (ROOT / "backend_api").is_dir() and (Path(__file__).resolve().parents[2] / "app").is_dir():
    ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.auth import can_view_all_sessions, get_current_user
from app.core.security import AuthenticatedUser
from backend.services.safety_report import analyze_safety
from backend.services.report_pdf import render_safety_report_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

SESSIONS_DIR = os.path.join(str(ROOT), "outputs", "sessions")


def _load_filtered_sessions(user: AuthenticatedUser) -> list[dict]:
    """Load session JSON files and filter by user visibility."""
    from app.services.session_cache import get_all_sessions
    sessions = list(get_all_sessions())
    if not can_view_all_sessions(user):
        sessions = [
            s for s in sessions
            if s.get("created_by_user_id") == user.id
        ]
    return sessions


@router.get("/reports/safety-report")
async def get_safety_report(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Alert-focused safety analysis across visible sessions with alert data."""
    sessions = _load_filtered_sessions(user)
    result = analyze_safety(sessions)
    return result


@router.get("/reports/safety-report/pdf")
async def get_safety_report_pdf(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Safety Report as PDF download."""
    sessions = _load_filtered_sessions(user)
    data = analyze_safety(sessions)
    pdf_bytes = await render_safety_report_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=safety-report.pdf",
        },
    )
