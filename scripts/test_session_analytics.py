from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.session_analytics import SessionAnalytics, RISK_ORDER


def make_features(
    neck: float = 5.0,
    trunk: float = 10.0,
    shoulder: float = 2.0,
    knee: float = 160.0,
) -> dict:
    return {
        "neck_flexion": neck,
        "trunk_flexion": trunk,
        "left_shoulder_elev": 0.0,
        "right_shoulder_elev": 0.0,
        "shoulder_symmetry": shoulder,
        "alignment_deviation": 1.0,
        "knee_angle": knee,
    }


def make_issue(name: str, severity: str = "LOW") -> list[dict]:
    return [{"issue": name, "severity": severity, "value": 15.0, "threshold": 10.0}]


# ---------------------------------------------------------------------------
# 1.  Constructor and initial state
# ---------------------------------------------------------------------------
def test_initial_state() -> None:
    a = SessionAnalytics()
    s = a.get_summary()
    assert s["total_frames"] == 0
    assert s["most_frequent_issue"] is None
    assert s["highest_risk_timestamp"] is None
    assert s["highest_risk_level"] == "LOW"
    assert s["avg_neck_flexion"] == 0.0
    assert s["avg_trunk_flexion"] == 0.0
    assert s["avg_shoulder_symmetry"] == 0.0
    assert s["avg_knee_angle"] == 0.0
    for rl in ("LOW", "MEDIUM", "HIGH"):
        assert s["risk_percentages"][rl] == 0.0
    print("  [PASS] test_initial_state")


# ---------------------------------------------------------------------------
# 2.  Single frame update
# ---------------------------------------------------------------------------
def test_single_frame() -> None:
    a = SessionAnalytics()
    feats = make_features(neck=12.3, trunk=25.0, shoulder=5.5, knee=145.0)
    a.update(feats, "MEDIUM", make_issue("Neck Flexion", "MEDIUM"), True, "12:00:00")
    s = a.get_summary()
    assert s["total_frames"] == 1
    assert s["risk_percentages"]["MEDIUM"] == 100.0
    assert s["avg_neck_flexion"] == 12.3
    assert s["avg_trunk_flexion"] == 25.0
    assert s["avg_shoulder_symmetry"] == 5.5
    assert s["avg_knee_angle"] == 145.0
    assert s["most_frequent_issue"] == "Neck Flexion"
    assert s["highest_risk_level"] == "MEDIUM"
    assert s["highest_risk_timestamp"] == "12:00:00"
    print("  [PASS] test_single_frame")


# ---------------------------------------------------------------------------
# 3.  Multiple frames — risk percentages
# ---------------------------------------------------------------------------
def test_risk_percentages() -> None:
    a = SessionAnalytics()
    feats_low = make_features()
    feats_med = make_features(neck=20.0)
    feats_high = make_features(neck=40.0)

    a.update(feats_low, "LOW", [], True)
    a.update(feats_low, "LOW", [], True)
    a.update(feats_med, "MEDIUM", [], True)
    a.update(feats_high, "HIGH", [], True)
    a.update(feats_med, "MEDIUM", [], True)

    s = a.get_summary()
    assert s["total_frames"] == 5
    assert s["risk_percentages"]["LOW"] == 40.0
    assert s["risk_percentages"]["MEDIUM"] == 40.0
    assert s["risk_percentages"]["HIGH"] == 20.0
    print("  [PASS] test_risk_percentages")


# ---------------------------------------------------------------------------
# 4.  Highest risk event tracking
# ---------------------------------------------------------------------------
def test_highest_risk_tracking() -> None:
    a = SessionAnalytics()
    feats = make_features()

    a.update(feats, "MEDIUM", [], True, "10:00:00")
    assert a._highest_risk_level == "MEDIUM"
    assert a._highest_risk_timestamp == "10:00:00"

    a.update(feats, "HIGH", [], True, "10:05:00")
    assert a._highest_risk_level == "HIGH"
    assert a._highest_risk_timestamp == "10:05:00"

    a.update(feats, "LOW", [], True, "10:10:00")
    assert a._highest_risk_level == "HIGH"
    assert a._highest_risk_timestamp == "10:05:00"
    print("  [PASS] test_highest_risk_tracking")


# ---------------------------------------------------------------------------
# 5.  Most frequent issue
# ---------------------------------------------------------------------------
def test_most_frequent_issue() -> None:
    a = SessionAnalytics()
    feats = make_features()

    a.update(feats, "LOW", make_issue("Neck Flexion"), True)
    a.update(feats, "LOW", make_issue("Neck Flexion"), True)
    a.update(feats, "LOW", make_issue("Shoulder Imbalance"), True)
    a.update(feats, "LOW", make_issue("Neck Flexion"), True)
    a.update(feats, "LOW", make_issue("Knee Instability"), True)

    s = a.get_summary()
    assert s["most_frequent_issue"] == "Neck Flexion"
    assert s["most_frequent_issue_count"] == 3
    print("  [PASS] test_most_frequent_issue")


# ---------------------------------------------------------------------------
# 6.  Averages over multiple frames
# ---------------------------------------------------------------------------
def test_averages() -> None:
    a = SessionAnalytics()

    a.update(make_features(neck=10.0, trunk=20.0, shoulder=2.0, knee=160.0), "LOW", [], True)
    a.update(make_features(neck=20.0, trunk=30.0, shoulder=4.0, knee=150.0), "LOW", [], True)
    a.update(make_features(neck=30.0, trunk=40.0, shoulder=6.0, knee=140.0), "LOW", [], True)

    s = a.get_summary()
    assert s["avg_neck_flexion"] == 20.0
    assert s["avg_trunk_flexion"] == 30.0
    assert s["avg_shoulder_symmetry"] == 4.0
    assert s["avg_knee_angle"] == 150.0
    print("  [PASS] test_averages")


# ---------------------------------------------------------------------------
# 7.  person_detected=False skips frame
# ---------------------------------------------------------------------------
def test_skip_when_not_detected() -> None:
    a = SessionAnalytics()
    feats = make_features(neck=50.0)

    a.update(feats, "HIGH", make_issue("Neck Flexion", "HIGH"), False)
    s = a.get_summary()
    assert s["total_frames"] == 0
    assert s["avg_neck_flexion"] == 0.0
    assert s["highest_risk_level"] == "LOW"
    print("  [PASS] test_skip_when_not_detected")


# ---------------------------------------------------------------------------
# 8.  reset() clears everything
# ---------------------------------------------------------------------------
def test_reset() -> None:
    a = SessionAnalytics()
    a.update(make_features(neck=15.0), "MEDIUM", make_issue("Neck Flexion", "MEDIUM"), True, "12:00:00")
    a.reset()

    s = a.get_summary()
    assert s["total_frames"] == 0
    assert s["avg_neck_flexion"] == 0.0
    assert s["highest_risk_level"] == "LOW"
    assert s["highest_risk_timestamp"] is None
    assert s["most_frequent_issue"] is None
    print("  [PASS] test_reset")


# ---------------------------------------------------------------------------
# 9.  Empty features dict (missing keys)
# ---------------------------------------------------------------------------
def test_empty_features() -> None:
    a = SessionAnalytics()
    a.update({}, "LOW", [], True)
    s = a.get_summary()
    assert s["total_frames"] == 1
    assert s["avg_neck_flexion"] == 0.0
    assert s["avg_trunk_flexion"] == 0.0
    assert s["avg_shoulder_symmetry"] == 0.0
    assert s["avg_knee_angle"] == 0.0
    print("  [PASS] test_empty_features")


# ---------------------------------------------------------------------------
# 10.  No issues tracked (empty list each frame)
# ---------------------------------------------------------------------------
def test_no_issues() -> None:
    a = SessionAnalytics()
    a.update(make_features(), "LOW", [], True)
    a.update(make_features(), "LOW", [], True)
    s = a.get_summary()
    assert s["most_frequent_issue"] is None
    assert s["most_frequent_issue_count"] == 0
    print("  [PASS] test_no_issues")


# ---------------------------------------------------------------------------
# 11.  Elapsed time increases
# ---------------------------------------------------------------------------
def test_elapsed_time() -> None:
    a = SessionAnalytics()
    t0 = a.elapsed_seconds
    time.sleep(0.01)
    t1 = a.elapsed_seconds
    assert t1 > t0
    print("  [PASS] test_elapsed_time")


# ---------------------------------------------------------------------------
# 12.  RISK_ORDER lookup completeness
# ---------------------------------------------------------------------------
def test_risk_order() -> None:
    assert RISK_ORDER["LOW"] == 0
    assert RISK_ORDER["MEDIUM"] == 1
    assert RISK_ORDER["HIGH"] == 2
    print("  [PASS] test_risk_order")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"\nRunning Session Analytics tests ({Path(__file__).name})\n")
    test_initial_state()
    test_single_frame()
    test_risk_percentages()
    test_highest_risk_tracking()
    test_most_frequent_issue()
    test_averages()
    test_skip_when_not_detected()
    test_reset()
    test_empty_features()
    test_no_issues()
    test_elapsed_time()
    test_risk_order()
    print(f"\n{'=' * 50}")
    print("All tests passed.")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
