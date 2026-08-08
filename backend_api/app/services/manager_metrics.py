"""Cross-session manager metrics computed from persisted session summaries.

Pure functions (no I/O) so they are trivially unit-testable. The live
repository feeds them the parsed session JSON dicts from the session cache.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_WEEK_SECONDS = 7 * 24 * 3600


def _parse_ts(ts: str) -> float | None:
    """Epoch seconds from a session_timestamp like '20260709_140605' or
    '20260709_140605_123456'. Returns None on any parse failure."""
    if not ts:
        return None
    clean = ts.rsplit("_", 1)[0] if ts.count("_") > 1 and ts.rsplit("_", 1)[1].isdigit() else ts
    try:
        return datetime.strptime(clean, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


def session_avg_risk(data: dict) -> float:
    """Weighted average risk (0-100) for one session from risk_percentages.

    LOW contributes 0, MEDIUM contributes 50, HIGH contributes 100.
    Falls back to the highest_risk_level if percentages are missing.
    """
    pct = data.get("risk_percentages") or {}
    if pct:
        low = float(pct.get("LOW", 0) or 0)
        med = float(pct.get("MEDIUM", 0) or 0)
        high = float(pct.get("HIGH", 0) or 0)
        total = low + med + high
        if total > 0:
            return round((med * 50 + high * 100) / total, 1)
    level = (data.get("highest_risk_level") or "LOW").upper()
    return {"LOW": 10.0, "MEDIUM": 50.0, "HIGH": 90.0}.get(level, 10.0)


def compute_manager_metrics(sessions: list[dict]) -> dict:
    """Aggregate metrics across session summaries.

    Returns:
        {
            "weeklyImprovement": float | None,   # % change, +ve = risk dropped
            "averageCompliance": float | None,   # 100 - avg risk, 0-100
            "healthScore": float | None,         # composite 0-100
        }
    """
    now = datetime.now(timezone.utc).timestamp()

    risks: list[float] = []
    week_risks: list[tuple[float, float]] = []  # (epoch, risk)

    for data in sessions:
        risk = session_avg_risk(data)
        risks.append(risk)
        epoch = _parse_ts(data.get("session_timestamp") or "")
        if epoch is not None:
            week_risks.append((epoch, risk))

    if not risks:
        return {"weeklyImprovement": None, "averageCompliance": None, "healthScore": None}

    avg_risk = sum(risks) / len(risks)
    average_compliance = round(max(0.0, min(100.0, 100.0 - avg_risk)), 1)

    # Health score: blend of compliance with recency — sessions in the last 7
    # days count double so current conditions weigh more than old ones.
    total_weight = 0.0
    weighted_sum = 0.0
    for epoch, risk in week_risks:
        age = max(0.0, now - epoch)
        w = 2.0 if age <= _WEEK_SECONDS else 1.0
        total_weight += w
        weighted_sum += risk * w
    effective_risk = weighted_sum / total_weight if total_weight > 0 else avg_risk
    health_score = round(max(0.0, min(100.0, 100.0 - effective_risk)), 1)

    # Weekly improvement: avg risk last 7d vs the 7d before that.
    this_week: list[float] = []
    last_week: list[float] = []
    for epoch, risk in week_risks:
        if now - epoch <= _WEEK_SECONDS:
            this_week.append(risk)
        elif now - 2 * _WEEK_SECONDS <= epoch < now - _WEEK_SECONDS:
            last_week.append(risk)

    weekly_improvement: float | None = None
    if last_week and this_week:
        prev = sum(last_week) / len(last_week)
        curr = sum(this_week) / len(this_week)
        if prev > 0:
            weekly_improvement = round((prev - curr) / prev * 100.0, 1)
    elif this_week and not last_week:
        # No baseline yet — report stable.
        weekly_improvement = 0.0

    return {
        "weeklyImprovement": weekly_improvement,
        "averageCompliance": average_compliance,
        "healthScore": health_score,
    }
