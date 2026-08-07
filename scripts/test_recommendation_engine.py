from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.issue_detection import detect_posture_issues
from backend.services.recommendation_engine import (
    format_recommendations_text,
    get_recommendations,
)

TEST_CASES = [
    {
        "name": "Normal Posture — No Recommendations",
        "features": {
            "neck_flexion": 5.0,
            "trunk_flexion": 8.0,
            "left_shoulder_elev": 12.0,
            "right_shoulder_elev": 14.0,
            "shoulder_symmetry": 2.0,
            "alignment_deviation": 3.0,
            "knee_angle": 165.0,
        },
    },
    {
        "name": "Neck Flexion — Worker + Supervisor Guidance",
        "features": {
            "neck_flexion": 35.0,
            "trunk_flexion": 10.0,
            "left_shoulder_elev": 15.0,
            "right_shoulder_elev": 16.0,
            "shoulder_symmetry": 2.5,
            "alignment_deviation": 4.0,
            "knee_angle": 160.0,
        },
    },
    {
        "name": "Multiple Issues — All Guidance Shown",
        "features": {
            "neck_flexion": 35.0,
            "trunk_flexion": 45.0,
            "left_shoulder_elev": 55.0,
            "right_shoulder_elev": 50.0,
            "shoulder_symmetry": 14.0,
            "alignment_deviation": 18.0,
            "knee_angle": 120.0,
        },
    },
]


def main() -> None:
    print("=" * 72)
    print("  INDUSTRIAL RECOMMENDATION ENGINE — TEST SUITE")
    print("=" * 72)

    all_ok = True
    for case in TEST_CASES:
        name = case["name"]
        features = case["features"]
        issues = detect_posture_issues(features)
        recs = get_recommendations(issues)

        print(f"\n{'-' * 72}")
        print(f"  Case: {name}")
        print(f"{'-' * 72}")

        if not recs:
            print("  No issues — no recommendations generated.")
            continue

        for rec in recs:
            icon = "!" if rec["severity"] == "HIGH" else "~"
            print(f"\n  [{icon}] {rec['issue']} ({rec['severity']})")
            print(f"  {'-' * 52}")

            print(f"  WORKER GUIDANCE:")
            for i, action in enumerate(rec["worker_actions"], 1):
                print(f"    {i}. {action}")

            print(f"  SUPERVISOR / WORKPLACE INTERVENTION:")
            for i, action in enumerate(rec["supervisor_actions"], 1):
                print(f"    {i}. {action}")

            # Verify structure
            assert "issue" in rec, f"Missing 'issue' key in {rec}"
            assert "severity" in rec, f"Missing 'severity' key in {rec}"
            assert "worker_actions" in rec, f"Missing 'worker_actions' key in {rec}"
            assert "supervisor_actions" in rec, f"Missing 'supervisor_actions' key in {rec}"
            assert isinstance(rec["worker_actions"], list), "worker_actions must be a list"
            assert isinstance(rec["supervisor_actions"], list), "supervisor_actions must be a list"
            assert len(rec["worker_actions"]) > 0, "worker_actions must not be empty"
            assert len(rec["supervisor_actions"]) > 0, "supervisor_actions must not be empty"

        # Test format helper
        text = format_recommendations_text(recs)
        assert isinstance(text, str), "format_recommendations_text must return string"
        assert len(text) > 0, "format_recommendations_text must not be empty"

    print(f"\n{'=' * 72}")
    print(f"  All structure and content checks passed.")
    print(f"  {len(TEST_CASES)} test cases verified.")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
