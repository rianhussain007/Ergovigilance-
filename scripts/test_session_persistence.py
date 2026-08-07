"""Session persistence tests — against the current backend.services.session_analytics.

The old ``backend/persistence`` package was removed; persistence now lives in
``backend/services/session_analytics.py``:

- ``SessionAnalytics`` — in-memory per-session accumulation + ``get_summary()``
- ``save_session_summary`` — writes ``session_<ts>.json`` + ``session_index.csv``

Covers accumulation, summary output, file writing/roundtrip, zero-frame guard,
and alerts attachment.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.session_analytics import SessionAnalytics, save_session_summary


def make_summary(total_frames=100):
    return {
        "session_duration_seconds": 120.0,
        "total_frames": total_frames,
        "risk_percentages": {"LOW": 60.0, "MEDIUM": 30.0, "HIGH": 10.0},
        "most_frequent_issue": "Neck Flexion",
        "most_frequent_issue_count": 30,
        "highest_risk_level": "HIGH",
        "highest_risk_timestamp": "14:00:00",
        "avg_neck_flexion": 12.5,
        "avg_trunk_flexion": 8.0,
        "avg_shoulder_symmetry": 5.0,
        "avg_knee_angle": 160.0,
    }


def make_features():
    return {
        "neck_flexion": 10.0,
        "trunk_flexion": 20.0,
        "shoulder_symmetry": 5.0,
        "knee_angle": 150.0,
    }


results: list[str] = []


def check(label, got, expected):
    status = "PASS" if got == expected else "FAIL"
    line = f"  {status}: {label} — got {got!r}, expected {expected!r}"
    print(line)
    results.append(line)
    if status == "FAIL":
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# 1.  SessionAnalytics accumulation
# ---------------------------------------------------------------------------
sa = SessionAnalytics()
sa.update(make_features(), "HIGH", [{"issue": "Neck Flexion"}], person_detected=True)
sa.update(make_features(), "MEDIUM", [{"issue": "Neck Flexion"}], person_detected=True)
summary = sa.get_summary()

check("frame count", summary["total_frames"], 2)
check("risk percentages", summary["risk_percentages"], {"LOW": 0.0, "MEDIUM": 50.0, "HIGH": 50.0})
check("highest risk level", summary["highest_risk_level"], "HIGH")
check("most frequent issue", summary["most_frequent_issue"], "Neck Flexion")
check("most frequent issue count", summary["most_frequent_issue_count"], 2)
check("avg neck flexion", summary["avg_neck_flexion"], 10.0)
check("avg trunk flexion", summary["avg_trunk_flexion"], 20.0)
check("avg knee angle", summary["avg_knee_angle"], 150.0)


# ---------------------------------------------------------------------------
# 2.  Frames without a person are skipped
# ---------------------------------------------------------------------------
sa.update(make_features(), "LOW", [], person_detected=False)
check("no-person frames skipped", sa.get_summary()["total_frames"], 2)


# ---------------------------------------------------------------------------
# 3.  Empty analytics summary
# ---------------------------------------------------------------------------
empty = SessionAnalytics().get_summary()
check("empty total frames", empty["total_frames"], 0)
check("empty risk percentages zero", empty["risk_percentages"], {"LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0})
check("empty highest risk LOW", empty["highest_risk_level"], "LOW")
check("empty issue None", empty["most_frequent_issue"], None)


# ---------------------------------------------------------------------------
# 4.  save_session_summary writes JSON + index
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    path = save_session_summary(make_summary(), tmp, session_timestamp="20260701_000000")
    check("save returns a path string", isinstance(path, str) and Path(path).exists(), True)
    check("filename prefix", Path(path).name.startswith("session_20260701_000000"), True)

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    check("saved timestamp", data["session_timestamp"], "20260701_000000")
    check("saved risk HIGH", data["risk_percentages"]["HIGH"], 10.0)
    check("saved issue", data["most_frequent_issue"], "Neck Flexion")
    check("saved avg knee", data["avg_knee_angle"], 160.0)

    index = Path(tmp) / "session_index.csv"
    check("index csv exists", index.exists(), True)
    check("index header present", index.read_text(encoding="utf-8").splitlines()[0].startswith("timestamp"), True)


# ---------------------------------------------------------------------------
# 5.  Zero-frame summaries are not persisted
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    path = save_session_summary(make_summary(total_frames=0), tmp)
    check("zero-frame returns None", path, None)
    check("zero-frame writes no file", len(list(Path(tmp).glob("session_*.json"))), 0)


# ---------------------------------------------------------------------------
# 6.  Alerts attached when provided
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    path = save_session_summary(
        make_summary(), tmp, session_timestamp="20260702_000000",
        alerts_data={"history": [{"severity": "HIGH", "title": "x"}]},
    )
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    check("alerts attached", len(data.get("alerts", [])), 1)
    check("alert severity kept", data["alerts"][0]["severity"], "HIGH")


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
