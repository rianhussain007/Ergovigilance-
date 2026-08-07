"""Trend analysis tests — against the current backend.services.trend_analysis.

Covers ``analyze_risk_trend`` (structured JSON output), ``_compute_trend``
thresholds, inverted-metric flipping, and the metrics array. The archived
``TrendAnalysis`` markdown-report class was removed from the codebase; the
module now returns structured JSON consumed by the risk-trend API endpoint.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.trend_analysis import (
    METRIC_NAMES,
    _INVERTED_METRICS,
    _compute_trend,
    analyze_risk_trend,
)


def make_session(
    timestamp="20260601_000000",
    low=60.0, med=30.0, high=10.0,
    issue="Neck Flexion",
    highest_risk="HIGH",
    neck=15.0, trunk=20.0, shoulder=5.0, knee=150.0,
):
    return {
        "session_timestamp": timestamp,
        "session_duration_seconds": 120.0,
        "total_frames": 100,
        "risk_percentages": {"LOW": low, "MEDIUM": med, "HIGH": high},
        "most_frequent_issue": issue,
        "most_frequent_issue_count": 30,
        "highest_risk_level": highest_risk,
        "highest_risk_timestamp": "14:00:00",
        "avg_neck_flexion": neck,
        "avg_trunk_flexion": trunk,
        "avg_shoulder_symmetry": shoulder,
        "avg_knee_angle": knee,
    }


results: list[str] = []


def check(label, got, expected):
    status = "PASS" if got == expected else "FAIL"
    line = f"  {status}: {label} — got {got!r}, expected {expected!r}"
    print(line)
    results.append(line)
    if status == "FAIL":
        raise SystemExit(1)


def metric_trend(report, metric: str) -> str:
    """Trend value for a named metric from an analyze_risk_trend() report."""
    for m in report["metrics"]:
        if m["name"] == metric:
            return m["trend"]
    raise KeyError(metric)


# ---------------------------------------------------------------------------
# 1.  No sessions
# ---------------------------------------------------------------------------
r = analyze_risk_trend([])
check("no sessions total", r["total_sessions"], 0)
check("no sessions status", r["status"], "No sessions found")


# ---------------------------------------------------------------------------
# 2.  Single session
# ---------------------------------------------------------------------------
r = analyze_risk_trend([make_session()])
check("single session count", r["total_sessions"], 1)
check("single session avg low", r["risk_distribution"]["low_pct"], 60.0)
check("single session avg high", r["risk_distribution"]["high_pct"], 10.0)
check("single session neck trend", metric_trend(r, "avg_neck_flexion"), "Stable")
check("single session overall trend", r["overall_trend"], "Stable")


# ---------------------------------------------------------------------------
# 3.  Multiple sessions — averages
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session("20260601_000000", low=50, med=30, high=20),
    make_session("20260602_000000", low=60, med=30, high=10),
    make_session("20260603_000000", low=70, med=20, high=10),
])
check("multi avg low", r["risk_distribution"]["low_pct"], 60.0)
check("multi avg med", r["risk_distribution"]["medium_pct"], 26.7)
check("multi avg high", r["risk_distribution"]["high_pct"], 13.3)
check("multi total sessions", r["total_sessions"], 3)


# ---------------------------------------------------------------------------
# 4.  Most common issue across sessions
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session("20260601_000000", issue="Neck Flexion"),
    make_session("20260602_000000", issue="Neck Flexion"),
    make_session("20260603_000000", issue="Shoulder Imbalance"),
    make_session("20260604_000000", issue="Neck Flexion"),
])
check("most common issue", r["most_common_issue"], "Neck Flexion")
check("most common issue count", r["most_common_issue_count"], 3)


# ---------------------------------------------------------------------------
# 5.  Most common highest risk
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session("20260601_000000", highest_risk="HIGH"),
    make_session("20260602_000000", highest_risk="MEDIUM"),
    make_session("20260603_000000", highest_risk="HIGH"),
])
check("most common highest risk", r["most_common_highest_risk"], "HIGH")


# ---------------------------------------------------------------------------
# 6.  Improving trend (neck decreasing — inverted metric)
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session(f"2026060{i + 1}_000000", neck=25.0 - i * 3.0) for i in range(6)
])
check("improving neck trend", metric_trend(r, "avg_neck_flexion"), "Improving")
check("improving overall", r["overall_trend"], "Improving")


# ---------------------------------------------------------------------------
# 7.  Deteriorating trend (neck increasing — inverted metric)
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session(f"2026060{i + 1}_000000", neck=10.0 + i * 3.0) for i in range(6)
])
check("deteriorating neck trend", metric_trend(r, "avg_neck_flexion"), "Deteriorating")
check("deteriorating overall", r["overall_trend"], "Deteriorating")


# ---------------------------------------------------------------------------
# 8.  Knee angle improving (increasing = better, not inverted)
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session(f"2026060{i + 1}_000000", knee=140.0 + i * 4.0) for i in range(6)
])
check("improving knee trend", metric_trend(r, "avg_knee_angle"), "Improving")


# ---------------------------------------------------------------------------
# 9.  _compute_trend thresholds (< 4 values is Stable)
# ---------------------------------------------------------------------------
check("trend 1 session", _compute_trend([10.0]), "Stable")
check("trend 2 sessions", _compute_trend([10.0, 20.0]), "Stable")
check("trend 3 sessions", _compute_trend([10.0, 20.0, 30.0]), "Stable")
check("trend raw decreasing", _compute_trend([20.0, 18.0, 16.0, 14.0]), "Deteriorating")
check("trend raw increasing", _compute_trend([10.0, 12.0, 14.0, 16.0]), "Improving")
check("trend flat stable", _compute_trend([15.0, 15.0, 15.0, 15.0]), "Stable")


# ---------------------------------------------------------------------------
# 10.  Earliest and latest timestamps
# ---------------------------------------------------------------------------
r = analyze_risk_trend([
    make_session("20260610_000000"),
    make_session("20260601_000000"),
    make_session("20260605_000000"),
])
check("earliest session", r["earliest_session"], "20260601_000000")
check("latest session", r["latest_session"], "20260610_000000")


# ---------------------------------------------------------------------------
# 11.  Metrics structure (replaces the removed markdown report tests)
# ---------------------------------------------------------------------------
r = analyze_risk_trend([make_session(f"2026060{i + 1}_000000") for i in range(4)])
check("metrics count", len(r["metrics"]), 4)
check("metrics names match METRIC_NAMES", [m["name"] for m in r["metrics"]], METRIC_NAMES)
check("metric keys complete", all(
    all(k in m for k in ("name", "label", "unit", "average", "trend"))
    for m in r["metrics"]
), True)
check("knee metric label", r["metrics"][3]["label"], "Knee Angle")
check("knee metric unit", r["metrics"][3]["unit"], "deg")
check("knee metric average", r["metrics"][3]["average"], 150.0)


# ---------------------------------------------------------------------------
# 12.  Inverted metric logic
# ---------------------------------------------------------------------------
check("neck lower better inverted", "avg_neck_flexion" in _INVERTED_METRICS, True)
check("trunk lower better inverted", "avg_trunk_flexion" in _INVERTED_METRICS, True)
check("shoulder lower better inverted", "avg_shoulder_symmetry" in _INVERTED_METRICS, True)
check("knee NOT inverted", "avg_knee_angle" not in _INVERTED_METRICS, True)


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
