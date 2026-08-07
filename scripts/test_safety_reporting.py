"""Safety report tests — against backend.services.safety_report.analyze_safety.

The archived ``SafetyReport`` markdown-report class was removed; the current
module aggregates safety-alert data across sessions into structured JSON.
This suite covers totals, severity/trigger-rule breakdowns, alert density,
top sessions, most-frequent issues, and coverage statements.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.safety_report import SEVERITY_ORDER, analyze_safety


def make_alert(severity: str = "HIGH", rule: str = "critical_risk"):
    return {
        "id": f"A-{severity}-{rule}",
        "severity": severity,
        "trigger_rule": rule,
        "title": f"{severity} alert",
        "message": "test alert",
        "state": "ACTIVE",
    }


def make_session(
    timestamp="20260710_000000",
    duration=3600.0,
    issue="Neck Flexion",
    highest_risk="HIGH",
    alerts=None,
):
    session = {
        "session_timestamp": timestamp,
        "session_duration_seconds": duration,
        "total_frames": 100,
        "risk_percentages": {"LOW": 60.0, "MEDIUM": 30.0, "HIGH": 10.0},
        "most_frequent_issue": issue,
        "most_frequent_issue_count": 30,
        "highest_risk_level": highest_risk,
        "highest_risk_timestamp": "14:00:00",
    }
    if alerts is not None:
        session["alerts"] = alerts
    return session


results: list[str] = []


def check(label, got, expected):
    status = "PASS" if got == expected else "FAIL"
    line = f"  {status}: {label} — got {got!r}, expected {expected!r}"
    print(line)
    results.append(line)
    if status == "FAIL":
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# 1.  No alert data
# ---------------------------------------------------------------------------
r = analyze_safety([make_session(alerts=None)])
check("no alerts: total with alerts", r["total_sessions_with_alerts"], 0)
check("no alerts: status", r["status"], "No alert data available")
check("no alerts: coverage mentions tracking start", "2026-07-06" in r["coverage_statement"], True)


# ---------------------------------------------------------------------------
# 2.  Aggregation across alert-bearing sessions
# ---------------------------------------------------------------------------
s1 = make_session(
    timestamp="20260710_000000",
    alerts=[make_alert("HIGH", "critical_risk"), make_alert("MEDIUM", "neck_flexion")],
)
s2 = make_session(
    timestamp="20260711_000000",
    alerts=[make_alert("CRITICAL", "critical_risk")],
)
s3 = make_session(timestamp="20260712_000000", alerts=None)  # excluded
r = analyze_safety([s1, s2, s3])
check("total sessions with alerts", r["total_sessions_with_alerts"], 2)
check("total all sessions", r["total_all_sessions"], 3)
check("total alerts", r["total_alerts"], 3)
check("high severity total", r["high_severity_total"], 2)  # CRITICAL + HIGH
check("medium severity total", r["medium_severity_total"], 1)
check("low severity total", r["low_severity_total"], 0)
check("severity breakdown HIGH", r["severity_breakdown"].get("HIGH"), 1)
check("severity breakdown CRITICAL", r["severity_breakdown"].get("CRITICAL"), 1)
check("severity breakdown MEDIUM", r["severity_breakdown"].get("MEDIUM"), 1)
check("earliest session", r["earliest_session"], "20260710_000000")
check("latest session", r["latest_session"], "20260711_000000")


# ---------------------------------------------------------------------------
# 3.  Trigger rule breakdown with percentages
# ---------------------------------------------------------------------------
rules = {item["rule"]: item["count"] for item in r["trigger_rule_breakdown"]}
check("critical_risk count", rules.get("critical_risk"), 2)
check("neck_flexion count", rules.get("neck_flexion"), 1)
pct_by_rule = {item["rule"]: item["pct"] for item in r["trigger_rule_breakdown"]}
check("critical_risk pct", pct_by_rule.get("critical_risk"), 66.7)
check("neck_flexion pct", pct_by_rule.get("neck_flexion"), 33.3)


# ---------------------------------------------------------------------------
# 4.  Alert density
# ---------------------------------------------------------------------------
density = r["alert_density"]
check("avg per session", density["avg_per_session"], 1.5)
check("min per session", density["min_alerts_per_session"], 1)
check("max per session", density["max_alerts_per_session"], 2)
check("total monitored hours", density["total_monitored_hours"], 2.0)
check("avg session duration", density["avg_session_duration_seconds"], 3600)


# ---------------------------------------------------------------------------
# 5.  Top sessions sorted by alert count (desc)
# ---------------------------------------------------------------------------
top = r["top_sessions_by_alerts"]
check("top session first", top[0]["session_timestamp"], "20260710_000000")
check("top session alert count", top[0]["alert_count"], 2)
check("top session second", top[1]["session_timestamp"], "20260711_000000")


# ---------------------------------------------------------------------------
# 6.  Most frequent issues among alert sessions
# ---------------------------------------------------------------------------
r = analyze_safety([
    make_session(timestamp="20260710_000000", issue="Neck Flexion", alerts=[make_alert()]),
    make_session(timestamp="20260711_000000", issue="Neck Flexion", alerts=[make_alert()]),
    make_session(timestamp="20260712_000000", issue="Shoulder Imbalance", alerts=[make_alert()]),
])
issues = {item["issue"]: item["count"] for item in r["most_frequent_issues"]}
check("most frequent issue", issues.get("Neck Flexion"), 2)
check("second issue", issues.get("Shoulder Imbalance"), 1)


# ---------------------------------------------------------------------------
# 7.  Coverage statement excludes sessions without alert data
# ---------------------------------------------------------------------------
r = analyze_safety([make_session(timestamp="20260710_000000", alerts=[make_alert()]),
                    make_session(timestamp="20260711_000000", alerts=None)])
check("coverage mentions excluded count", "1 session(s) without alert data" in r["coverage_statement"], True)
check("coverage n", "Based on 1 sessions with alert tracking" in r["coverage_statement"], True)


# ---------------------------------------------------------------------------
# 8.  SEVERITY_ORDER sanity
# ---------------------------------------------------------------------------
check("CRITICAL ranked 0", SEVERITY_ORDER["CRITICAL"], 0)
check("HIGH ranked 1", SEVERITY_ORDER["HIGH"], 1)
check("LOW ranked 4", SEVERITY_ORDER["LOW"], 4)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
all_pass = all("PASS" in r for r in results)
print(f"\n  {'=' * 50}")
if all_pass:
    print(f"  RESULT: ALL TESTS PASSED ({len(results)} checks)")
else:
    print(f"  RESULT: SOME CHECKS FAILED")
print(f"  {'=' * 50}")
