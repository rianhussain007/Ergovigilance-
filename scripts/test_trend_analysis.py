from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.trend_analysis import (
    TrendAnalysis,
    _compute_trend,
    METRIC_NAMES,
    _INVERTED_METRICS,
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


def write_session(tmp, session):
    p = Path(tmp) / f"session_{session['session_timestamp']}.json"
    with open(p, "w") as f:
        json.dump(session, f)


results: list[str] = []


def check(label, got, expected):
    status = "PASS" if got == expected else "FAIL"
    line = f"  {status}: {label} — got {got!r}, expected {expected!r}"
    print(line)
    results.append(line)
    if status == "FAIL":
        raise SystemExit(1)


def contains(text, substring):
    return substring in text


# ---------------------------------------------------------------------------
# 1.  No sessions
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    ta = TrendAnalysis(tmp)
    check("no sessions count", ta.session_count, 0)
    r = ta.analyze()
    check("no sessions status", r.get("status"), "No sessions found")


# ---------------------------------------------------------------------------
# 2.  Single session
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    write_session(tmp, make_session())
    ta = TrendAnalysis(tmp)
    check("single session count", ta.session_count, 1)
    r = ta.analyze()
    check("single session avg low", r["average_low_pct"], 60.0)
    check("single session avg high", r["average_high_pct"], 10.0)
    check("single session neck trend", r["trend_neck_flexion"], "Stable")
    check("single session overall trend", r["overall_ergonomic_trend"], "Stable")


# ---------------------------------------------------------------------------
# 3.  Multiple sessions — averages
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    write_session(tmp, make_session("20260601_000000", low=50, med=30, high=20))
    write_session(tmp, make_session("20260602_000000", low=60, med=30, high=10))
    write_session(tmp, make_session("20260603_000000", low=70, med=20, high=10))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("multi avg low", r["average_low_pct"], 60.0)
    check("multi avg med", r["average_medium_pct"], 26.7)
    check("multi avg high", r["average_high_pct"], 13.3)
    check("multi total sessions", r["total_sessions"], 3)


# ---------------------------------------------------------------------------
# 4.  Most common issue across sessions
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    write_session(tmp, make_session("20260601_000000", issue="Neck Flexion"))
    write_session(tmp, make_session("20260602_000000", issue="Neck Flexion"))
    write_session(tmp, make_session("20260603_000000", issue="Shoulder Imbalance"))
    write_session(tmp, make_session("20260604_000000", issue="Neck Flexion"))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("most common issue", r["most_common_issue"], "Neck Flexion")
    check("most common issue count", r["most_common_issue_count"], 3)


# ---------------------------------------------------------------------------
# 5.  Most common highest risk
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    write_session(tmp, make_session("20260601_000000", highest_risk="HIGH"))
    write_session(tmp, make_session("20260602_000000", highest_risk="MEDIUM"))
    write_session(tmp, make_session("20260603_000000", highest_risk="HIGH"))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("most common highest risk", r["most_common_highest_risk"], "HIGH")


# ---------------------------------------------------------------------------
# 6.  Improving trend (neck decreasing)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    for i in range(6):
        neck_val = 25.0 - i * 3.0
        write_session(tmp, make_session(f"2026060{i+1}_000000", neck=neck_val))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("improving neck trend", r["trend_neck_flexion"], "Improving")
    check("improving overall", r["overall_ergonomic_trend"], "Improving")


# ---------------------------------------------------------------------------
# 7.  Deteriorating trend (neck increasing)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    for i in range(6):
        neck_val = 10.0 + i * 3.0
        write_session(tmp, make_session(f"2026060{i+1}_000000", neck=neck_val))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("deteriorating neck trend", r["trend_neck_flexion"], "Deteriorating")
    check("deteriorating overall", r["overall_ergonomic_trend"], "Deteriorating")


# ---------------------------------------------------------------------------
# 8.  Knee angle improving (increasing = better)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    for i in range(6):
        knee_val = 140.0 + i * 4.0
        write_session(tmp, make_session(f"2026060{i+1}_000000", knee=knee_val))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("improving knee trend", r["trend_knee_angle"], "Improving")


# ---------------------------------------------------------------------------
# 9.  Trend with < 4 sessions is Stable
# ---------------------------------------------------------------------------
check("trend 1 session", _compute_trend([10.0]), "Stable")
check("trend 2 sessions", _compute_trend([10.0, 20.0]), "Stable")
check("trend 3 sessions", _compute_trend([10.0, 20.0, 30.0]), "Stable")
check("trend raw decreasing", _compute_trend([20.0, 18.0, 16.0, 14.0]), "Deteriorating")
check("trend raw increasing", _compute_trend([10.0, 12.0, 14.0, 16.0]), "Improving")
check("trend flat stable", _compute_trend([15.0, 15.0, 15.0, 15.0]), "Stable")
# Full pipeline tests (tests 6,7) already verify inverted metric flipping


# ---------------------------------------------------------------------------
# 10.  Earliest and latest timestamps
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    write_session(tmp, make_session("20260610_000000"))
    write_session(tmp, make_session("20260601_000000"))
    write_session(tmp, make_session("20260605_000000"))
    ta = TrendAnalysis(tmp)
    r = ta.analyze()
    check("earliest session", r["earliest_session"], "20260601_000000")
    check("latest session", r["latest_session"], "20260610_000000")


# ---------------------------------------------------------------------------
# 11.  Report generation
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    for i in range(4):
        write_session(tmp, make_session(f"2026060{i+1}_000000"))
    ta = TrendAnalysis(tmp)
    report = ta.generate_report()
    check("report contains Executive Summary", contains(report, "Executive Summary"), True)
    check("report contains Sessions Analysed", contains(report, "Sessions Analysed"), True)
    check("report contains Trend Analysis", contains(report, "Trend Analysis"), True)
    check("report contains Common Issues", contains(report, "Common Issues"), True)
    check("report contains Risk Distribution", contains(report, "Risk Distribution"), True)
    check("report contains Long-Term", contains(report, "Long-Term Recommendations"), True)
    check("report contains Conclusion", contains(report, "Conclusion"), True)


# ---------------------------------------------------------------------------
# 12.  Save report to file
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    for i in range(4):
        write_session(tmp, make_session(f"2026060{i+1}_000000"))
    ta = TrendAnalysis(tmp)
    out = Path(tmp) / "output" / "trend_report.md"
    saved = ta.save_report(out)
    check("save returns path", saved, str(out))
    check("save file exists", out.exists(), True)
    content = out.read_text()
    check("saved file has content", len(content) > 100, True)


# ---------------------------------------------------------------------------
# 13.  Ensure inverse metric logic is correct
# ---------------------------------------------------------------------------
# For inverted metrics (neck, trunk, shoulder): lower is better
# For non-inverted (knee): higher is better
check("necl lower better inverted", "avg_neck_flexion" in _INVERTED_METRICS, True)
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
