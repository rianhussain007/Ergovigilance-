"""Analytics endpoint — computes real cross-session analytics from session files."""

import json
import logging
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.auth import can_view_all_sessions, get_current_user
from app.core.security import AuthenticatedUser
from backend.services.trend_analysis import _compute_trend_for_metric, TREND_ORDER

logger = logging.getLogger(__name__)
router = APIRouter()

SESSIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "outputs", "sessions"
)


def _sanitize(val, default=0.0):
    """Replace NaN/inf floats with a safe default for JSON serialization."""
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return default
    return val


def _sanitize_session(s: dict) -> dict:
    """Sanitize NaN values in a session dict."""
    for key in ("avg_neck_flexion", "avg_trunk_flexion", "avg_shoulder_symmetry",
                "avg_knee_angle", "avg_upper_arm_angle", "avg_elbow_flexion_angle"):
        if key in s:
            s[key] = _sanitize(s[key])
    rp = s.get("risk_percentages", {})
    for k in rp:
        rp[k] = _sanitize(rp[k])
    return s


def _load_sessions(user: AuthenticatedUser) -> list[dict]:
    from backend.services.session_cache import get_all_sessions
    sessions = [_sanitize_session(s) for s in get_all_sessions()]
    if not can_view_all_sessions(user):
        sessions = [s for s in sessions if s.get("created_by_user_id") == user.id]
    return sessions


def _is_analyzed(s: dict) -> bool:
    """False for O1 "no person detected" stub sessions (0 analyzed frames).

    Stubs are real sessions and count toward total_sessions, but they carry no
    risk measurements — folding them into risk averages/trends would drag every
    score toward zero and fake an "improving" trend.
    """
    return not (s.get("no_person_detected") or s.get("total_frames") == 0)


def _iso_week(session_timestamp: str) -> str:
    """Convert '20260713_180306' to 'W28' (ISO week number)."""
    try:
        dt = datetime.strptime(session_timestamp[:8], "%Y%m%d")
        return f"W{dt.isocalendar()[1]}"
    except (ValueError, IndexError):
        return "Unknown"


@router.get("/analytics")
async def get_analytics(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Real cross-session analytics from session JSON files."""
    sessions = _load_sessions(user)
    if not sessions:
        return {
            "summary": {"total_sessions": 0, "avg_risk_score": 0, "improving": 0, "stable": 0, "deteriorating": 0},
            "weekly_risk_trend": [],
            "risk_distribution": [],
            "issue_frequency": [],
            "neck_trunk_trend": [],
        }

    n = len(sessions)
    # O1: stub sessions (ran, but no person was ever in frame) are counted in
    # total_sessions but excluded from every risk/feature aggregate — they
    # carry no measurements, so averaging them in would drag scores to zero.
    analyzed = [s for s in sessions if _is_analyzed(s)]
    if not analyzed:
        return {
            "summary": {"total_sessions": n, "avg_risk_score": 0, "improving": 0, "stable": 0, "deteriorating": 0},
            "weekly_risk_trend": [],
            "risk_distribution": [],
            "issue_frequency": [],
            "neck_trunk_trend": [],
        }

    # ── Summary ──────────────────────────────────────────────────────
    risk_scores = []
    for s in analyzed:
        rp = s.get("risk_percentages", {})
        low = rp.get("LOW", 0)
        med = rp.get("MEDIUM", 0)
        high = rp.get("HIGH", 0)
        total = low + med + high
        risk_scores.append((med * 50 + high * 100) / max(total, 1))

    avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0

    neck_vals = [s.get("avg_neck_flexion", 0) for s in analyzed]
    trunk_vals = [s.get("avg_trunk_flexion", 0) for s in analyzed]
    shoulder_vals = [s.get("avg_shoulder_symmetry", 0) for s in analyzed]
    knee_vals = [s.get("avg_knee_angle", 0) for s in analyzed]

    improving = sum(1 for m in ["avg_neck_flexion", "avg_trunk_flexion", "avg_shoulder_symmetry"]
                    if _compute_trend_for_metric(
                        [s.get(m, 0) for s in analyzed], m) == "Improving")
    deteriorating = sum(1 for m in ["avg_neck_flexion", "avg_trunk_flexion", "avg_shoulder_symmetry"]
                        if _compute_trend_for_metric(
                            [s.get(m, 0) for s in analyzed], m) == "Deteriorating")
    stable = 3 - improving - deteriorating

    summary = {
        "total_sessions": n,
        "avg_risk_score": avg_risk,
        "improving": improving,
        "stable": stable,
        "deteriorating": deteriorating,
    }

    # ── Weekly Risk Trend ────────────────────────────────────────────
    week_data = defaultdict(list)
    for i, s in enumerate(analyzed):
        wk = _iso_week(s.get("session_timestamp", ""))
        week_data[wk].append(risk_scores[i])

    weekly_risk_trend = [
        {"week": wk, "averageRisk": round(sum(vals) / len(vals), 1), "sessions": len(vals)}
        for wk, vals in sorted(week_data.items())
    ]

    # ── Risk Distribution (averaged percentages) ─────────────────────
    total_low = sum(s.get("risk_percentages", {}).get("LOW", 0) for s in analyzed)
    total_med = sum(s.get("risk_percentages", {}).get("MEDIUM", 0) for s in analyzed)
    total_high = sum(s.get("risk_percentages", {}).get("HIGH", 0) for s in analyzed)
    total = total_low + total_med + total_high or 1

    risk_distribution = [
        {"name": "Low", "value": round(total_low / total * 100, 1), "color": "#22c55e"},
        {"name": "Moderate", "value": round(total_med / total * 100, 1), "color": "#f97316"},
        {"name": "High", "value": round(total_high / total * 100, 1), "color": "#ef4444"},
    ]

    # ── Issue Frequency ──────────────────────────────────────────────
    issues = [s.get("most_frequent_issue") for s in analyzed if s.get("most_frequent_issue")]
    issue_counts = Counter(issues).most_common(5)
    issue_frequency = [{"name": name, "count": count} for name, count in issue_counts]

    # ── Neck & Trunk Trend (weekly) ──────────────────────────────────
    neck_week = defaultdict(list)
    trunk_week = defaultdict(list)
    for i, s in enumerate(analyzed):
        wk = _iso_week(s.get("session_timestamp", ""))
        neck_week[wk].append(neck_vals[i])
        trunk_week[wk].append(trunk_vals[i])

    neck_trunk_trend = []
    all_weeks = sorted(set(list(neck_week.keys()) + list(trunk_week.keys())))
    for wk in all_weeks:
        neck_trunk_trend.append({
            "week": wk,
            "neck": round(sum(neck_week[wk]) / len(neck_week[wk]), 2) if neck_week[wk] else 0,
            "trunk": round(sum(trunk_week[wk]) / len(trunk_week[wk]), 2) if trunk_week[wk] else 0,
        })

    return {
        "summary": summary,
        "weekly_risk_trend": weekly_risk_trend,
        "risk_distribution": risk_distribution,
        "issue_frequency": issue_frequency,
        "neck_trunk_trend": neck_trunk_trend,
    }
