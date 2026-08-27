"""Worker Self-View endpoint — personal posture data for the operator.

Returns the logged-in user's own sessions, alerts, risk trend, and
consent status.  Uses created_by_user_id to scope sessions to the
authenticated user.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/worker/my-summary")
async def get_worker_summary(
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return personal posture summary for the logged-in user.

    Includes:
    - Current risk status (from live session if active)
    - Personal session history (only this user's sessions)
    - Personal alert history
    - Risk trend (improving / stable / deteriorating)
    - Consent status
    """
    from app.services.session_cache import get_all_sessions
    from app.services.live_monitor import get_live_service_or_none

    # Current live status
    current_risk = "low"
    current_score = 0.0
    current_task = "No active session"
    session_active = False
    confidence_band = "medium"

    service = get_live_service_or_none()
    if service and service.is_running():
        state = service.get_state_snapshot()
        if state.context_snapshot:
            current_risk = state.context_snapshot.risk_level.lower()
            current_score = state.context_snapshot.final_risk
            confidence_band = state.context_snapshot.confidence_band
        current_task = state.task_name or "Classifying..."
        session_active = True

    # Personal session history — scoped by created_by_user_id
    all_sessions = get_all_sessions()
    my_sessions = [
        s for s in all_sessions
        if s.get("created_by_user_id") == user.id
    ]

    sessions_summary: list[dict] = []
    for s in my_sessions[:20]:  # last 20
        ts = s.get("session_timestamp", "")
        date_str = ""
        if ts:
            try:
                clean_ts = ts.rsplit("_", 1)[0] if ts.count("_") > 1 and ts.rsplit("_", 1)[1].isdigit() else ts
                dt = datetime.strptime(clean_ts, "%Y%m%d_%H%M%S")
                date_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, TypeError):
                date_str = ts
        duration_secs = s.get("session_duration_seconds", 0)
        mins = int(duration_secs // 60)
        secs = int(duration_secs % 60)
        duration_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        sessions_summary.append({
            "id": s.get("session_id", ""),
            "date": date_str,
            "duration": duration_str,
            "highestRisk": s.get("highest_risk_level", "LOW"),
            "task": s.get("task_name", "Not classified"),
            "status": "completed",
        })

    # Personal alert history
    my_alerts: list[dict] = []
    if service:
        engine = service.alert_engine
        my_session_ids = {s.get("session_id") for s in my_sessions}
        for a in engine._history[-20:]:
            if a.session_id in my_session_ids:
                my_alerts.append({
                    "id": a.id,
                    "title": a.title,
                    "severity": a.severity.value,
                    "state": a.state.value,
                    "created_at": a.created_at,
                    "session_id": a.session_id,
                    "message": a.message,
                    "confidence": a.confidence,
                    "confidence_band": a.confidence_band,
                })

    # Risk trend
    risk_scores = [
        {"HIGH": 80, "MEDIUM": 50, "LOW": 20}.get(s.get("highest_risk_level", "LOW"), 20)
        for s in my_sessions[:10]
    ]
    trend = "stable"
    if len(risk_scores) >= 2:
        recent = sum(risk_scores[:3]) / min(3, len(risk_scores[:3]))
        older = sum(risk_scores[3:]) / max(1, len(risk_scores[3:]))
        if recent < older - 5:
            trend = "improving"
        elif recent > older + 5:
            trend = "deteriorating"

    return {
        "worker_id": None,
        "worker_name": user.email.split("@")[0],
        "current_risk": current_risk,
        "current_score": current_score,
        "current_task": current_task,
        "session_active": session_active,
        "confidence_band": confidence_band,
        "sessions": sessions_summary,
        "alerts": my_alerts,
        "risk_trend": trend,
        "total_sessions": len(my_sessions),
        "consent_status": "granted",
        "identity_mode": "off",
        "data_retention": "Session data is retained per your site's retention policy. You can request deletion of your data at any time.",
    }
