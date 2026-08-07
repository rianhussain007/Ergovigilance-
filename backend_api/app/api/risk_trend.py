"""Risk Trend Report endpoints — JSON data + PDF export."""

import json
import logging
import math
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
from backend.services.trend_analysis import analyze_risk_trend
from backend.services.report_pdf import render_risk_trend_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

SESSIONS_DIR = os.path.join(str(ROOT), "outputs", "sessions")


def _sanitize(val, default=0.0):
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return default
    return val


def _sanitize_session(s: dict) -> dict:
    for key in ("avg_neck_flexion", "avg_trunk_flexion", "avg_shoulder_symmetry",
                "avg_knee_angle", "avg_upper_arm_angle", "avg_elbow_flexion_angle"):
        if key in s:
            s[key] = _sanitize(s[key])
    rp = s.get("risk_percentages", {})
    for k in rp:
        rp[k] = _sanitize(rp[k])
    return s


def _load_filtered_sessions(user: AuthenticatedUser) -> list[dict]:
    """Load session JSON files and filter by user visibility.

    Same role-based rules as _get_session_files in reports.py:
      - supervisor / safety_mgr / admin → all sessions (including legacy unowned)
      - operator → only sessions where created_by_user_id matches
    """
    from app.services.session_cache import get_all_sessions
    sessions = [_sanitize_session(s) for s in get_all_sessions()]
    if not can_view_all_sessions(user):
        sessions = [
            s for s in sessions
            if s.get("created_by_user_id") == user.id
        ]
    return sessions


@router.get("/reports/risk-trend")
async def get_risk_trend(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Cross-session risk trend analysis across all visible sessions."""
    sessions = _load_filtered_sessions(user)
    result = analyze_risk_trend(sessions)
    return result


@router.get("/reports/risk-trend/pdf")
async def get_risk_trend_pdf(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Risk Trend Report as PDF download."""
    sessions = _load_filtered_sessions(user)
    data = analyze_risk_trend(sessions)
    pdf_bytes = await render_risk_trend_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=risk-trend-report.pdf",
        },
    )
