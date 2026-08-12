from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.issue_detection import (
    detect_posture_issues,
    highest_priority_issue,
    summarize_issues,
)
from backend.services.features import risk_from_features

TEST_CASES = [
    {
        "name": "Normal Posture",
        "features": {
            "neck_flexion": 5.0,
            "trunk_flexion": 8.0,
            "left_shoulder_elev": 12.0,
            "right_shoulder_elev": 14.0,
            "shoulder_symmetry": 2.0,
            "alignment_deviation": 3.0,
            "knee_angle": 165.0,
            "stance_stability": 0.9,
        },
        "expect_count": 0,
    },
    {
        "name": "High Neck Flexion",
        "features": {
            "neck_flexion": 42.0,
            "trunk_flexion": 10.0,
            "left_shoulder_elev": 15.0,
            "right_shoulder_elev": 16.0,
            "shoulder_symmetry": 2.5,
            "alignment_deviation": 4.0,
            "knee_angle": 160.0,
            "stance_stability": 0.9,
        },
        "expect_count": 1,
    },
    {
        "name": "High Trunk Flexion",
        "features": {
            "neck_flexion": 8.0,
            "trunk_flexion": 55.0,
            "left_shoulder_elev": 14.0,
            "right_shoulder_elev": 13.0,
            "shoulder_symmetry": 1.8,
            "alignment_deviation": 12.0,
            "knee_angle": 155.0,
            "stance_stability": 0.9,
        },
        "expect_count": 2,
    },
    {
        "name": "Shoulder Imbalance",
        "features": {
            "neck_flexion": 6.0,
            "trunk_flexion": 12.0,
            "left_shoulder_elev": 40.0,
            "right_shoulder_elev": 12.0,
            "shoulder_symmetry": 18.0,
            "alignment_deviation": 3.5,
            "knee_angle": 162.0,
            "stance_stability": 0.9,
        },
        "expect_count": 2,
    },
    {
        "name": "Multiple Simultaneous Issues",
        "features": {
            "neck_flexion": 35.0,
            "trunk_flexion": 45.0,
            "left_shoulder_elev": 55.0,
            "right_shoulder_elev": 50.0,
            "shoulder_symmetry": 14.0,
            "alignment_deviation": 18.0,
            "knee_angle": 120.0,
            "stance_stability": 0.9,
        },
        "expect_count": 7,
    },
]


def main() -> None:
    print("=" * 64)
    print("  POSTURE ISSUE DETECTION — TEST SUITE")
    print("=" * 64)
    print(f"\n{'Test Case':<38} {'Issues':>8} {'Risk':>8} {'Result':>8}")
    print("-" * 64)

    passed = 0
    for case in TEST_CASES:
        issues = detect_posture_issues(case["features"])
        overall_risk = risk_from_features(case["features"])
        summary = summarize_issues(issues)
        top = highest_priority_issue(issues)
        count = len(issues)
        ok = count == case["expect_count"]
        if ok:
            passed += 1

        status = "  PASS" if ok else "  FAIL"
        print(f"{case['name']:<38} {count:>8} {overall_risk:>8} {status:>8}")

        if not ok:
            print(f"  {' '*38} Expected {case['expect_count']} issues, got {count}")

        if issues:
            print(f"  {'-'*60}")
            for iss in issues:
                print(f"    [{iss['severity'][0]}] {iss['issue']:<34} value={iss['value']:<8.1f} threshold={iss['threshold']}")
            print(f"  {'-'*60}")
            print(f"  Summary: {summary}")
            if top:
                print(f"  Highest priority: {top['issue']} ({top['severity']})")
        else:
            print(f"  No issues detected. Summary: {summary}")
        print()

    print("-" * 64)
    print(f"  Result: {passed}/{len(TEST_CASES)} tests passed")
    print("=" * 64)


if __name__ == "__main__":
    main()
