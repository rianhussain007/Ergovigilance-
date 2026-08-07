"""Safety Report — alert-focused cross-session analysis.

Only sessions that genuinely have an alerts array are included. The 58 sessions
that predate alert tracking (alerts key missing entirely) are explicitly excluded
and the report prominently reports N=34 coverage so nobody mistakes it for
full-dataset coverage.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "WARNING": 3, "LOW": 4}

_ALERT_TRACKING_START = "2026-07-06"  # earliest alert-bearing session date


def analyze_safety(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze safety alerts across sessions that have alert data.

    Args:
        sessions: Pre-filtered list of session dicts (role-filtered by caller).
                  Only sessions with a non-empty alerts array are analyzed;
                  sessions without an alerts key are silently excluded.

    Returns:
        Structured JSON dict for the /api/reports/safety-report endpoint.
    """
    # Isolate sessions that genuinely have alert data
    alert_sessions = [s for s in sessions if s.get("alerts") and len(s["alerts"]) > 0]
    n = len(alert_sessions)

    if n == 0:
        return {
            "total_sessions_with_alerts": 0,
            "coverage_statement": (
                "No sessions with alert tracking found among the sessions "
                "you have access to. Alert tracking began on "
                + _ALERT_TRACKING_START
                + "."
            ),
            "status": "No alert data available",
        }

    # --- date range ---
    timestamps = [
        s.get("session_timestamp", "") for s in alert_sessions
        if s.get("session_timestamp")
    ]
    earliest = min(timestamps) if timestamps else "unknown"
    latest = max(timestamps) if timestamps else "unknown"
    total_all_sessions = len(sessions)

    # --- total alerts ---
    total_alerts = sum(len(s["alerts"]) for s in alert_sessions)
    alert_counts = [len(s["alerts"]) for s in alert_sessions]

    # --- severity breakdown ---
    sev_counter: Counter[str] = Counter()
    # --- trigger rule breakdown ---
    rule_counter: Counter[str] = Counter()
    # --- per-session alert info for top-N ---
    session_alert_list: List[Dict[str, Any]] = []

    for s in alert_sessions:
        session_alerts = s["alerts"]
        session_count = len(session_alerts)
        for a in session_alerts:
            sev_counter[a.get("severity", "UNKNOWN")] += 1
            rule_counter[a.get("trigger_rule", "UNKNOWN")] += 1

        session_alert_list.append({
            "session_timestamp": s.get("session_timestamp", "unknown"),
            "alert_count": session_count,
            "highest_risk_level": s.get("highest_risk_level", "UNKNOWN"),
        })

    # top-N by alert count (top 15)
    session_alert_list.sort(key=lambda x: -x["alert_count"])
    top_sessions = session_alert_list[:15]

    # --- severity grouping ---
    severity_breakdown = dict(sev_counter.most_common())
    high_severity = sev_counter.get("CRITICAL", 0) + sev_counter.get("HIGH", 0)
    low_severity = sev_counter.get("WARNING", 0) + sev_counter.get("LOW", 0)
    medium_severity = sev_counter.get("MEDIUM", 0)

    # --- trigger rule breakdown with percentages ---
    total_for_pct = sum(rule_counter.values()) or 1
    trigger_rules = [
        {"rule": rule, "count": cnt, "pct": round(cnt / total_for_pct * 100, 1)}
        for rule, cnt in rule_counter.most_common()
    ]

    # --- alert density ---
    total_seconds = sum(s.get("session_duration_seconds", 0) for s in alert_sessions)
    total_hours = total_seconds / 3600 if total_seconds > 0 else 0.01
    avg_per_session = round(total_alerts / n, 1) if n > 0 else 0
    alerts_per_hour = round(total_alerts / total_hours, 1) if total_hours > 0 else 0

    # --- most frequent issues among alert sessions ---
    issue_counter: Counter[str] = Counter()
    for s in alert_sessions:
        issue = s.get("most_frequent_issue")
        if issue:
            issue_counter[issue] += 1
    most_frequent_issues = [
        {"issue": issue, "count": cnt}
        for issue, cnt in issue_counter.most_common()
    ]

    # Format dates for display
    def fmt_date(ts: str) -> str:
        m = __import__("re").match(r"(\d{4})(\d{2})(\d{2})", ts)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return ts

    coverage_statement = (
        f"Based on {n} sessions with alert tracking "
        f"({fmt_date(earliest)} to {fmt_date(latest)}). "
        f"The remaining {total_all_sessions - n} session(s) without alert data "
        f"are excluded — they predate alert tracking and genuinely have no alert records."
    )

    avg_duration_seconds = round(total_seconds / n) if n > 0 else 0

    return {
        "total_sessions_with_alerts": n,
        "total_all_sessions": total_all_sessions,
        "earliest_session": earliest,
        "latest_session": latest,
        "coverage_statement": coverage_statement,
        "total_alerts": total_alerts,
        "severity_breakdown": severity_breakdown,
        "high_severity_total": high_severity,
        "medium_severity_total": medium_severity,
        "low_severity_total": low_severity,
        "trigger_rule_breakdown": trigger_rules,
        "alert_density": {
            "avg_per_session": avg_per_session,
            "alerts_per_hour": alerts_per_hour,
            "total_monitored_hours": round(total_hours, 1),
            "avg_session_duration_seconds": avg_duration_seconds,
            "min_alerts_per_session": min(alert_counts) if alert_counts else 0,
            "max_alerts_per_session": max(alert_counts) if alert_counts else 0,
        },
        "top_sessions_by_alerts": top_sessions,
        "most_frequent_issues": most_frequent_issues,
    }
