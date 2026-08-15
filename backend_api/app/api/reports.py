"""Report endpoints — reads real session data from persistence."""

import logging
import os
import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends
from datetime import datetime

from app.core.deps import get_repository
from app.core.auth import can_view_all_sessions, get_current_user
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository
from app.schemas.api import ReportRecord, ReportGenerateRequest, ReportGenerateResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Sessions directory
ROOT = Path(__file__).resolve().parents[3]
if not (ROOT / "backend_api").is_dir() and (Path(__file__).resolve().parents[2] / "app").is_dir():
    ROOT = Path(__file__).resolve().parents[2]
# Honor SESSIONS_DIR env override (container mode mounts /data/sessions) before
# falling back to the source-tree outputs/sessions path.
SESSIONS_DIR = os.environ.get("SESSIONS_DIR") or os.path.join(str(ROOT), "outputs", "sessions")


def _get_session_files(current_user: AuthenticatedUser | None = None) -> List[dict]:
    """Read all session files from shared cache instead of individual disk reads."""
    from app.services.session_cache import get_all_sessions

    sessions = []
    for data in get_all_sessions():
        sess_id = data.get("session_id") or (f"SESH-{data.get('session_timestamp', '')}" if data.get("session_timestamp") else "unknown")
        sessions.append({
            "id": sess_id,
            "started_at": data.get("started_at", ""),
            "ended_at": data.get("ended_at", ""),
            "worker_id": data.get("worker_id", "unknown"),
            "created_by_user_id": data.get("created_by_user_id"),
            "is_legacy": "created_by_user_id" not in data,
            "statistics": data.get("statistics", {}),
            "snapshots_count": len(data.get("snapshots", [])),
            "alerts_count": len(data.get("alerts", [])),
            "recommendations_count": len(data.get("recommendations", [])),
            "file": "",
        })

    if current_user is not None and not can_view_all_sessions(current_user):
        sessions = [
            session for session in sessions
            if session.get("created_by_user_id") == current_user.id
        ]

    # Sort by ended_at (newest first)
    sessions.sort(key=lambda x: x.get("ended_at", ""), reverse=True)
    return sessions


@router.get("/reports", response_model=List[ReportRecord])
async def get_reports(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """List all generated reports from real session data."""
    sessions = _get_session_files(current_user=user)
    reports = []

    for session in sessions:
        # Create a report record for each session
        stats = session.get("statistics", {})
        history_stats = stats.get("history", {})

        # Calculate report date
        ended_at = session.get("ended_at", "")
        try:
            if ended_at:
                dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                report_date = dt.strftime("%Y-%m-%d")
            else:
                report_date = datetime.now().strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            report_date = datetime.now().strftime("%Y-%m-%d")

        # Determine report type based on session data
        alerts_count = session.get("alerts_count", 0)
        recommendations_count = session.get("recommendations_count", 0)

        if alerts_count > 0:
            report_type = "safety"
            title = f"Safety Report — {session['id']}"
        elif recommendations_count > 0:
            report_type = "session"
            title = f"Session Report — {session['id']}"
        else:
            report_type = "summary"
            title = f"Summary Report — {session['id']}"

        reports.append(ReportRecord(
            id=f"RPT-{session['id']}",
            title=title,
            type=report_type,
            date=report_date,
            status="completed",
            size=f"{session.get('snapshots_count', 0)} snapshots",
        ))

    return reports


@router.post("/report/generate", response_model=ReportGenerateResponse)
async def generate_report(
    body: ReportGenerateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Generate a new report from real session data."""
    logger.info("POST /api/report/generate — type=%s", body.type)

    sessions = _get_session_files(current_user=user)
    if not sessions:
        return ReportGenerateResponse(
            id="RPT-NO-DATA",
            title="No Sessions Available",
            message="No session data found. Run a monitoring session first.",
        )

    # Use the most recent session
    latest_session = sessions[0]
    session_id = latest_session["id"]

    label_map = {
        "safety": "Safety Report",
        "trend": "Trend Report",
        "session": "Session Export",
        "summary": "Summary Report",
        "csv": "CSV Export",
    }
    label = label_map.get(body.type, "Report")

    return ReportGenerateResponse(
        id=f"RPT-{session_id}",
        title=f"{label} — {session_id}",
        message=f"{label} generated for session {session_id}.",
    )
