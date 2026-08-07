from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.safety_reporting import (
    SafetyReport,
    _assess_safety,
    _format_duration,
    _recommendation_for,
    _sanitize_text,
)


def make_session(
    total_frames=100,
    duration=3665.0,
    low_pct=60.0,
    med_pct=30.0,
    high_pct=10.0,
    most_frequent="Shoulder Imbalance",
    mf_count=40,
    highest_risk="HIGH",
    risk_ts="14:30:00",
    avg_neck=12.3,
    avg_trunk=18.7,
    avg_shoulder=4.2,
    avg_knee=155.0,
    timestamp="20260622_143005",
):
    return {
        "session_timestamp": timestamp,
        "session_duration_seconds": duration,
        "total_frames": total_frames,
        "risk_percentages": {"LOW": low_pct, "MEDIUM": med_pct, "HIGH": high_pct},
        "most_frequent_issue": most_frequent,
        "most_frequent_issue_count": mf_count,
        "highest_risk_level": highest_risk,
        "highest_risk_timestamp": risk_ts,
        "avg_neck_flexion": avg_neck,
        "avg_trunk_flexion": avg_trunk,
        "avg_shoulder_symmetry": avg_shoulder,
        "avg_knee_angle": avg_knee,
    }


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
# 1.  Generate report with all fields
# ---------------------------------------------------------------------------
s = make_session()
report = SafetyReport(s)
md = report.generate()

check("report contains A. Session Information", contains(md, "A. Session Information"), True)
check("report contains B. Risk Summary", contains(md, "B. Risk Summary"), True)
check("report contains C. Issue Analysis", contains(md, "C. Issue Analysis"), True)
check("report contains D. Ergonomic Metrics", contains(md, "D. Ergonomic Metrics"), True)
check("report contains E. Safety Assessment", contains(md, "E. Safety Assessment"), True)
check("report contains F. Recommendations", contains(md, "F. Recommendations"), True)
check("date rendered", contains(md, "2026-06-22 14:30:05"), True)
check("duration rendered", contains(md, "1h 1m 5s"), True)
check("risk percentages rendered", contains(md, "**LOW Risk:** 60.0%"), True)
check("contains MEDIUM", contains(md, "**MEDIUM Risk:** 30.0%"), True)
check("contains HIGH", contains(md, "**HIGH Risk:** 10.0%"), True)
check("most frequent issue", contains(md, "Shoulder Imbalance"), True)
check("highest risk level", contains(md, "HIGH"), True)
check("risk timestamp", contains(md, "14:30:00"), True)
check("avg neck", contains(md, "12.3 deg"), True)
check("avg trunk", contains(md, "18.7 deg"), True)
check("avg shoulder", contains(md, "4.2 %"), True)
check("avg knee", contains(md, "155.0 deg"), True)
check("worker recommendation", contains(md, "**Worker:**"), True)
check("supervisor recommendation", contains(md, "**Supervisor:**"), True)

# --- Executive Summary ---
check("exec summary section header", contains(md, "## Executive Summary"), True)
check("exec summary before section A",
      md.index("## Executive Summary") < md.index("## A. Session Information"), True)
check("exec summary mentions assessment", contains(md, "Moderate Risk"), True)
check("exec summary mentions risk %", contains(md, "60.0%"), True)
check("exec summary mentions issue", contains(md, "Shoulder Imbalance"), True)

# Sentence counts per assessment level
for label, cfg, expected_text in [
    ("Excellent summary", make_session(high_pct=0.0, med_pct=0.0), "was excellent"),
    ("Good summary", make_session(high_pct=5.0, med_pct=10.0), "was good"),
    ("Moderate Risk summary", make_session(high_pct=10.0, med_pct=10.0), "was acceptable"),
    ("High Risk summary", make_session(high_pct=20.0, med_pct=0.0), "Immediate ergonomic"),
]:
    summary_md = SafetyReport(cfg).generate()
    check(f"{label} text match", contains(summary_md, expected_text), True)
    summary_section = summary_md.split("## Executive Summary")[1].split("## A.")[0]
    flat = summary_section.replace("\n", " ")
    sentence_count = len([s for s in flat.split(". ") if s.strip()])
    check(f"{label} sentence count ({sentence_count})",
          3 <= sentence_count <= 5, True)

# Executive summary without most frequent issue
no_issue = SafetyReport(make_session(most_frequent=None))
no_issue_md = no_issue.generate()
summary_no_issue = no_issue_md.split("## Executive Summary")[1].split("## A.")[0]
check("no-issue summary omits issue line", contains(summary_no_issue, "most frequently observed"), False)


# ---------------------------------------------------------------------------
# 2.  Safety assessment levels
# ---------------------------------------------------------------------------
check("Excellent: high=0 med=0",
      _assess_safety(make_session(high_pct=0.0, med_pct=0.0)),
      "Excellent")
check("Excellent: high=0 med=5",
      _assess_safety(make_session(high_pct=0.0, med_pct=5.0)),
      "Excellent")
check("Good: high=5 med=10",
      _assess_safety(make_session(high_pct=5.0, med_pct=10.0)),
      "Good")
check("Moderate: high=10 med=10",
      _assess_safety(make_session(high_pct=10.0, med_pct=10.0)),
      "Moderate Risk")
check("Moderate: high=5 med=30",
      _assess_safety(make_session(high_pct=5.0, med_pct=30.0)),
      "Moderate Risk")
check("High Risk: high=20 med=0",
      _assess_safety(make_session(high_pct=20.0, med_pct=0.0)),
      "High Risk")
check("High Risk: high=0 med=50",
      _assess_safety(make_session(high_pct=0.0, med_pct=50.0)),
      "High Risk")
check("High Risk: high=25 med=25",
      _assess_safety(make_session(high_pct=25.0, med_pct=25.0)),
      "High Risk")


# ---------------------------------------------------------------------------
# 3.  Duration formatting
# ---------------------------------------------------------------------------
check("0 seconds", _format_duration(0), "0m 0s")
check("30 seconds", _format_duration(30), "0m 30s")
check("1 minute", _format_duration(60), "1m 0s")
check("90 seconds", _format_duration(90), "1m 30s")
check("1 hour", _format_duration(3600), "1h 0m 0s")
check("1h 5m 30s", _format_duration(3930), "1h 5m 30s")


# ---------------------------------------------------------------------------
# 4.  Recommendation lookup
# ---------------------------------------------------------------------------
check("Neck Flexion recommendation",
      _recommendation_for("Excessive Neck Flexion") is not None, True)
check("Shoulder Imbalance recommendation",
      _recommendation_for("Shoulder Imbalance") is not None, True)
check("Unknown issue returns None",
      _recommendation_for("Unknown Issue"), None)
check("None issue returns None",
      _recommendation_for(None), None)


# ---------------------------------------------------------------------------
# 5.  No most frequent issue
# ---------------------------------------------------------------------------
s_no_issue = make_session(most_frequent=None)
md2 = SafetyReport(s_no_issue).generate()
check("no issue renders None detected", contains(md2, "None detected"), True)
check("no issue has no recommendation", contains(md2, "No specific recommendations available."), True)


# ---------------------------------------------------------------------------
# 6.  Save to file
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "reports" / "session_report.md"
    r = SafetyReport(make_session())
    saved = r.save(out)
    check("save returns correct path", saved, str(out))
    check("file exists", out.exists(), True)
    content = out.read_text()
    check("saved file contains header", contains(content, "# Session Safety Report"), True)
    check("saved file contains assessment", contains(content, "Moderate Risk"), True)


# ---------------------------------------------------------------------------
# 7.  Load from JSON
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    json_path = Path(tmp) / "test_session.json"
    sd = make_session()
    with open(json_path, "w") as f:
        json.dump(sd, f)
    r = SafetyReport.from_json(json_path)
    md3 = r.generate()
    check("from_json works", contains(md3, "60.0%"), True)


# ---------------------------------------------------------------------------
# 8.  Unicode sanitization
# ---------------------------------------------------------------------------
check("sanitize em dash", _sanitize_text("word\u2014word"), "word - word")
check("sanitize en dash", _sanitize_text("a\u2013b"), "a-b")
check("sanitize curly double quotes", _sanitize_text("\u201chello\u201d"), '"hello"')
check("sanitize curly single quotes", _sanitize_text("\u2018hi\u2019"), "'hi'")
check("sanitize bullet", _sanitize_text("\u2022 item"), "* item")
check("sanitize ellipsis", _sanitize_text("wait\u2026"), "wait...")
check("sanitize plain ASCII unchanged", _sanitize_text("hello world"), "hello world")
check("sanitize numbers unchanged", _sanitize_text("12.3 deg"), "12.3 deg")

# Verify full report is ASCII-safe (no char > 127)
s = make_session()
md4 = SafetyReport(s).generate()
non_ascii = [c for c in md4 if ord(c) > 127]
check("full report ASCII-safe", len(non_ascii), 0)

# Create a session with recommendations containing em dashes
from backend.services.recommendation_engine import _RECOMMENDATIONS
neck_rec = _RECOMMENDATIONS.get("Excessive Neck Flexion", {})
worker_action = neck_rec.get("worker_actions", [""])[0]
supervisor_action = neck_rec.get("supervisor_actions", [""])[0]
check("recommendation worker em dash sanitized", "\u2014" not in _sanitize_text(worker_action), True)
check("recommendation supervisor em dash sanitized", "\u2014" not in _sanitize_text(supervisor_action), True)

# Verify actual report output from real recommendations
neck_session = make_session(most_frequent="Excessive Neck Flexion")
neck_report = SafetyReport(neck_session).generate()
check("real report worker line ASCII-safe",
      "\u2014" not in neck_report, True)
check("real report contains hyphen instead",
      "- " in neck_report, True)


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
