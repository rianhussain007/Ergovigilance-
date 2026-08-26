"""Demo Mode seeding — generates realistic synthetic data when DEMO_MODE=true.

When the environment variable ``DEMO_MODE=true`` is set, this module
populates the session cache and alert engine with realistic synthetic
data so the dashboard is never empty during a customer demo.

All data is clearly marked as synthetic in API responses
(``source: "demo"``) so it can never be mistaken for real floor data.
"""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")


def _random_risk_level(weights: tuple[float, float, float] = (0.6, 0.3, 0.1)) -> str:
    return random.choices(["LOW", "MEDIUM", "HIGH"], weights=weights)[0]


def _random_task() -> str:
    tasks = [
        ("Assembly Work", 0.35),
        ("Lifting / Picking", 0.20),
        ("Inspection", 0.15),
        ("Reaching", 0.15),
        ("Walking / Moving", 0.10),
        ("Seated Work", 0.05),
    ]
    labels, weights = zip(*tasks)
    return random.choices(labels, weights=weights)[0]


def _generate_demo_sessions(count: int = 30) -> list[dict[str, object]]:
    """Generate *count* synthetic completed sessions spanning the last 30 days."""
    now = datetime.now(timezone.utc)
    workers = [
        {"id": "W-001", "name": "Ahmad R. (Line A)"},
        {"id": "W-002", "name": "Siti N. (Line B)"},
        {"id": "W-003", "name": "Ravi K. (Warehouse)"},
    ]
    sessions: list[dict[str, object]] = []
    for i in range(count):
        worker = random.choice(workers)
        days_ago = random.randint(0, 29)
        hour = random.choice([7, 8, 9, 10, 13, 14, 15])
        minute = random.randint(0, 59)
        ts_dt = (now - timedelta(days=days_ago)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        ts_str = ts_dt.strftime("%Y%m%d_%H%M%S")
        duration_secs = random.randint(600, 3600)
        risk_level = _random_risk_level()
        task = _random_task()

        # Risk percentages that sum to ~100
        if risk_level == "LOW":
            low_pct = random.uniform(65, 95)
            med_pct = random.uniform(2, 25)
            high_pct = 100 - low_pct - med_pct
        elif risk_level == "MEDIUM":
            low_pct = random.uniform(30, 60)
            med_pct = random.uniform(25, 50)
            high_pct = 100 - low_pct - med_pct
        else:
            low_pct = random.uniform(5, 30)
            med_pct = random.uniform(20, 40)
            high_pct = 100 - low_pct - med_pct

        total_frames = random.randint(1800, 10800)
        neck_avg = random.uniform(5, 25)
        trunk_avg = random.uniform(8, 30)
        knee_avg = random.uniform(100, 160)
        shoulder_sym = random.uniform(1, 10)

        session = {
            "session_id": f"SESH-{ts_str}_000",
            "session_timestamp": ts_str,
            "session_duration_seconds": duration_secs,
            "total_frames": total_frames,
            "highest_risk_level": risk_level,
            "risk_level": risk_level,
            "risk_percentages": {
                "LOW": round(low_pct, 1),
                "MEDIUM": round(med_pct, 1),
                "HIGH": round(max(0, high_pct), 1),
            },
            "most_frequent_issue": "Neck Flexion" if risk_level != "LOW" else None,
            "most_frequent_issue_count": random.randint(10, 200) if risk_level != "LOW" else 0,
            "avg_neck_flexion": round(neck_avg, 1),
            "avg_trunk_flexion": round(trunk_avg, 1),
            "avg_shoulder_symmetry": round(shoulder_sym, 1),
            "avg_knee_angle": round(knee_avg, 1),
            "task_name": task,
            "worker_id": worker["id"],
            "created_by_user_id": None,
            "camera_id": f"cam-{random.randint(0, 2)}",
            "source": "demo",
        }
        sessions.append(session)

    # Sort newest first
    sessions.sort(key=lambda s: s["session_timestamp"], reverse=True)
    return sessions


def _generate_demo_alerts(sessions: list[dict]) -> list[dict]:
    """Generate synthetic alert history from the demo sessions."""
    alerts = []
    alert_id = 1000
    for session in sessions:
        if session["risk_level"] == "LOW":
            continue
        # Generate 1-3 alerts per non-low session
        n_alerts = random.randint(1, 3) if session["risk_level"] == "HIGH" else random.randint(0, 1)
        for _ in range(n_alerts):
            severity = "HIGH" if session["risk_level"] == "HIGH" else "MEDIUM"
            state = random.choices(["ACTIVE", "ACKNOWLEDGED", "RESOLVED"], weights=[0.1, 0.3, 0.6])[0]
            ts = session["session_timestamp"]
            alerts.append({
                "id": f"ALT-{alert_id}",
                "session_id": session["session_id"],
                "frame_number": random.randint(100, session["total_frames"]),
                "created_at": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}Z",
                "severity": severity,
                "state": state,
                "title": f"{severity} Risk — {session.get('most_frequent_issue', 'Posture')}",
                "message": f"Worker {session['worker_id']} showed sustained {severity.lower()} risk posture during {session['task_name']}.",
                "trigger_rule": f"risk_level_{severity.lower()}",
                "confidence": round(random.uniform(0.75, 0.98), 2),
                "requires_ack": severity == "HIGH",
                "expires_at": "",
                "source": "demo",
            })
            alert_id += 1
    return alerts


def generate_demo_data() -> dict:
    """Generate the full demo dataset. Returns dict with 'sessions' and 'alerts'."""
    sessions = _generate_demo_sessions(30)
    alerts = _generate_demo_alerts(sessions)
    logger.info(
        "Demo mode: generated %d sessions + %d alerts",
        len(sessions),
        len(alerts),
    )
    return {"sessions": sessions, "alerts": alerts}
