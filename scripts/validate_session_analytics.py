from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.session_analytics import SessionAnalytics


def make_features(neck=0.0, trunk=0.0, shoulder=0.0, knee=160.0):
    return {
        "neck_flexion": neck,
        "trunk_flexion": trunk,
        "left_shoulder_elev": 0.0,
        "right_shoulder_elev": 0.0,
        "shoulder_symmetry": shoulder,
        "alignment_deviation": 1.0,
        "knee_angle": knee,
    }


def make_issue(name, severity="LOW"):
    return [{"issue": name, "severity": severity, "value": 15.0, "threshold": 10.0}]


def section(title):
    w = 70
    print(f"\n{'=' * w}")
    print(f"  {title}")
    print(f"{'=' * w}")


def ok():
    print("  ✓ PASS")


def fail(msg):
    print(f"  ✗ FAIL: {msg}")
    raise SystemExit(1)


results: list[str] = []


def check(label, got, expected):
    status = "PASS" if got == expected else "FAIL"
    line = f"  {status}: {label} — got {got!r}, expected {expected!r}"
    print(line)
    results.append(line)
    if status == "FAIL":
        raise SystemExit(1)


# =========================================================================
section("Scenario 1 — Risk Percentages (60 LOW, 30 MEDIUM, 10 HIGH)")
# =========================================================================

a1 = SessionAnalytics()
for _ in range(60):
    a1.update(make_features(), "LOW", [], True)
for _ in range(30):
    a1.update(make_features(neck=20.0), "MEDIUM", [], True)
for _ in range(10):
    a1.update(make_features(neck=40.0), "HIGH", [], True)

s1 = a1.get_summary()
check("total_frames", s1["total_frames"], 100)
check("LOW %", s1["risk_percentages"]["LOW"], 60.0)
check("MEDIUM %", s1["risk_percentages"]["MEDIUM"], 30.0)
check("HIGH %", s1["risk_percentages"]["HIGH"], 10.0)
check("highest_risk_level", s1["highest_risk_level"], "HIGH")

# =========================================================================
section("Scenario 2 — Most Frequent Issue (Shoulder Imbalance 40, Neck Flexion 25)")
# =========================================================================

a2 = SessionAnalytics()
for _ in range(40):
    a2.update(make_features(), "LOW", make_issue("Shoulder Imbalance"), True)
for _ in range(25):
    a2.update(make_features(), "LOW", make_issue("Neck Flexion"), True)

s2 = a2.get_summary()
check("most_frequent_issue", s2["most_frequent_issue"], "Shoulder Imbalance")
check("most_frequent_issue_count", s2["most_frequent_issue_count"], 40)
check("total_frames", s2["total_frames"], 65)

# =========================================================================
section("Scenario 3 — Feature Averages (Neck: 10, 20, 30 -> expected 20)")
# =========================================================================

a3 = SessionAnalytics()
a3.update(make_features(neck=10.0), "LOW", [], True)
a3.update(make_features(neck=20.0), "LOW", [], True)
a3.update(make_features(neck=30.0), "LOW", [], True)

s3 = a3.get_summary()
check("avg_neck_flexion", s3["avg_neck_flexion"], 20.0)
check("total_frames", s3["total_frames"], 3)

# =========================================================================
section("Scenario 4 — No person detected (should be skipped)")
# =========================================================================

a4 = SessionAnalytics()
a4.update(make_features(neck=99.0), "HIGH", make_issue("Neck Flexion", "HIGH"), False)
s4 = a4.get_summary()
check("total_frames (skipped)", s4["total_frames"], 0)
check("avg_neck (skipped)", s4["avg_neck_flexion"], 0.0)
check("highest_risk (skipped)", s4["highest_risk_level"], "LOW")

# =========================================================================
section("Scenario 5 — Reset clears all state")
# =========================================================================

a5 = SessionAnalytics()
a5.update(make_features(neck=15.0), "MEDIUM", make_issue("Neck Flexion", "MEDIUM"), True, "12:00:00")
a5.reset()
s5 = a5.get_summary()
check("total_frames after reset", s5["total_frames"], 0)
check("avg_neck after reset", s5["avg_neck_flexion"], 0.0)
check("highest_risk after reset", s5["highest_risk_level"], "LOW")
check("most_frequent after reset", s5["most_frequent_issue"], None)

# =========================================================================
section("Summary")
# =========================================================================

all_pass = all("PASS" in r for r in results)
print(f"\n  {'=' * 50}")
if all_pass:
    print(f"  RESULT: ALL SCENARIOS PASSED ({len(results)} checks)")
else:
    print(f"  RESULT: SOME CHECKS FAILED")
print(f"  {'=' * 50}")

# Write output file
out_dir = ROOT / "outputs"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "session_analytics_validation.txt"
with open(out_path, "w") as f:
    f.write("SESSION ANALYTICS VALIDATION REPORT\n")
    f.write(f"{'=' * 50}\n\n")
    f.write("\n".join(results))
    f.write(f"\n\n{'=' * 50}\n")
    f.write(f"RESULT: ALL SCENARIOS PASSED ({len(results)} checks)\n")
    f.write(f"{'=' * 50}\n")

print(f"\n  Results written to: {out_path}")
