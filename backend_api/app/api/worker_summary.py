"""Worker Self-View endpoint — personal posture data for the operator.

Returns the logged-in user's own sessions, alerts, risk trend, and
consent status.  Uses created_by_user_id to scope sessions to the
authenticated user.

When DEMO_MODE=true, returns synthetic worker-specific data so the
"My Posture" page is never empty during a customer demo.
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter()

DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")


def _generate_demo_worker_summary(user: AuthenticatedUser) -> dict[str, Any]:
    """Generate realistic synthetic posture data for the demo operator."""
    now = datetime.now(timezone.utc)

    # Simulate current posture — weighted toward LOW with occasional MEDIUM
    current_risk = random.choices(["low", "medium", "high"], weights=[0.65, 0.25, 0.10])[0]
    current_score = {"low": random.uniform(5, 25), "medium": random.uniform(35, 65), "high": random.uniform(70, 95)}[current_risk]
    current_task = random.choices(
        ["Assembly Work", "Lifting / Picking", "Inspection", "Reaching", "Walking / Moving", "Seated Work", "Neutral Standing"],
        weights=[0.30, 0.20, 0.15, 0.12, 0.10, 0.08, 0.05],
    )[0]
    confidence_band = random.choices(["high", "medium", "low"], weights=[0.5, 0.35, 0.15])[0]

    # Generate 15 synthetic sessions over the last 21 days
    sessions: list[dict] = []
    for i in range(15):
        days_ago = random.randint(0, 20)
        hour = random.choice([7, 8, 9, 10, 13, 14, 15])
        minute = random.randint(0, 59)
        ts_dt = (now - timedelta(days=days_ago, hours=now.hour - hour, minutes=now.minute - minute))
        ts_str = ts_dt.strftime("%Y%m%d_%H%M%S")
        duration_secs = random.randint(900, 5400)
        risk_level = random.choices(["LOW", "MEDIUM", "HIGH"], weights=[0.55, 0.30, 0.15])[0]
        task = random.choices(
            ["Assembly Work", "Lifting / Picking", "Inspection", "Reaching", "Walking / Moving", "Seated Work"],
            weights=[0.30, 0.20, 0.15, 0.12, 0.13, 0.10],
        )[0]
        mins = int(duration_secs // 60)
        secs = int(duration_secs % 60)

        sessions.append({
            "id": f"DEMO-SESH-{ts_str}",
            "date": ts_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration": f"{mins}m {secs}s",
            "highestRisk": risk_level,
            "task": task,
            "status": "completed",
        })

    # Sort newest first
    sessions.sort(key=lambda s: s["date"], reverse=True)

    # Generate 5 synthetic alerts
    alerts: list[dict] = []
    alert_issues = [
        ("Neck Flexion", "Keep your head neutral — avoid looking down for extended periods."),
        ("Trunk Flexion", "Straighten your back. Bend at the knees when reaching low objects."),
        ("Shoulder Elevation", "Lower your shoulders. Use a step stool instead of reaching overhead."),
        ("Knee Angle", "Avoid deep squatting. Use a lift-assist tool for low picks."),
        ("Forward Head Posture", "Pull your chin back and align your ears over your shoulders."),
    ]
    for i in range(5):
        issue, tip = random.choice(alert_issues)
        severity = random.choices(["MEDIUM", "HIGH"], weights=[0.6, 0.4])[0]
        state = random.choices(["ACTIVE", "ACKNOWLEDGED", "RESOLVED"], weights=[0.15, 0.35, 0.50])[0]
        alerts.append({
            "id": f"DEMO-ALT-{i + 1}",
            "title": f"{severity} Risk — {issue}",
            "severity": severity,
            "state": state,
            "created_at": (now - timedelta(days=random.randint(0, 14), hours=random.randint(0, 12))).isoformat(),
            "session_id": f"DEMO-SESH-{(now - timedelta(days=random.randint(0, 14))).strftime('%Y%m%d_%H%M%S')}",
            "message": f"Sustained {issue.lower()} detected during {current_task}. {tip}",
            "confidence": round(random.uniform(0.78, 0.97), 2),
            "confidence_band": confidence_band,
        })

    # Risk trend — slightly improving over time
    trend = random.choices(["improving", "stable", "deteriorating"], weights=[0.45, 0.40, 0.15])[0]

    # Privacy values from DB
    from app.core.database import get_worker
    worker_row = get_worker("W-001")
    identity_mode = worker_row["identity_mode"] if worker_row and "identity_mode" in worker_row.keys() else "off"
    consent_status = worker_row["consent_status"] if worker_row and "consent_status" in worker_row.keys() else "pending"

    return {
        "worker_id": "W-001",
        "worker_name": user.email.split("@")[0].replace(".", " ").title(),
        "current_risk": current_risk,
        "current_score": round(current_score, 1),
        "current_task": current_task,
        "session_active": True,
        "confidence_band": confidence_band,
        "sessions": sessions,
        "alerts": alerts,
        "risk_trend": trend,
        "total_sessions": 15,
        "consent_status": consent_status,
        "identity_mode": identity_mode,
        "data_retention": "Session data is retained per your site's retention policy. You can request deletion of your data at any time.",
        "source": "demo",
    }


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

    When DEMO_MODE=true, returns synthetic data instead of filtering by user ID.
    """
    # ── Demo mode: return synthetic worker data ────────────────────
    if DEMO_MODE:
        return _generate_demo_worker_summary(user)

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

    # Privacy from DB
    from app.core.database import get_worker
    worker_row = get_worker("W-001") if my_sessions else None
    identity_mode = worker_row["identity_mode"] if worker_row and "identity_mode" in worker_row.keys() else "off"
    consent_status = worker_row["consent_status"] if worker_row and "consent_status" in worker_row.keys() else "pending"

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
        "consent_status": consent_status,
        "identity_mode": identity_mode,
        "data_retention": "Session data is retained per your site's retention policy. You can request deletion of your data at any time.",
        "source": "live",
    }
