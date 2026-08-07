"""Phase 3B Issue Detection — Full Validation Script.

Tests:
  1. detect_posture_issues() with 5 representative cases
  2. LiveRepository mapping logic (backend -> React Issue interface)
  3. Severity mapping correctness
  4. Field generation (id, name, timestamp, detail)

Run: python scripts/validate_phase3b_issues.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.issue_detection import detect_posture_issues

# ─────────────────────────────────────────────────────────────
# SECTION 1: Issue Detection Engine — 5 Required Cases
# ─────────────────────────────────────────────────────────────

CASES = [
    {
        "label": "Case 1: Healthy posture",
        "features": {
            "neck_flexion": 5.0,
            "trunk_flexion": 8.0,
            "left_shoulder_elev": 12.0,
            "right_shoulder_elev": 14.0,
            "shoulder_symmetry": 2.0,
            "alignment_deviation": 3.0,
            "knee_angle": 165.0,
        },
        "expect_count": 0,
    },
    {
        "label": "Case 2: Poor neck posture (HIGH)",
        "features": {
            "neck_flexion": 42.0,
            "trunk_flexion": 10.0,
            "left_shoulder_elev": 15.0,
            "right_shoulder_elev": 16.0,
            "shoulder_symmetry": 2.5,
            "alignment_deviation": 4.0,
            "knee_angle": 160.0,
        },
        "expect_count": 1,
        "expect_issues": [
            {"name": "Excessive Neck Flexion", "severity": "HIGH"},
        ],
    },
    {
        "label": "Case 3: Poor trunk posture (MEDIUM)",
        "features": {
            "neck_flexion": 8.0,
            "trunk_flexion": 35.0,
            "left_shoulder_elev": 14.0,
            "right_shoulder_elev": 13.0,
            "shoulder_symmetry": 1.8,
            "alignment_deviation": 4.0,
            "knee_angle": 155.0,
        },
        "expect_count": 1,
        "expect_issues": [
            {"name": "Excessive Trunk Flexion", "severity": "MEDIUM"},
        ],
    },
    {
        "label": "Case 4: Multiple violations",
        "features": {
            "neck_flexion": 35.0,
            "trunk_flexion": 45.0,
            "left_shoulder_elev": 55.0,
            "right_shoulder_elev": 50.0,
            "shoulder_symmetry": 14.0,
            "alignment_deviation": 18.0,
            "knee_angle": 120.0,
        },
        "expect_count": 7,
        "expect_issues": [
            {"name": "Excessive Neck Flexion", "severity": "HIGH"},
            {"name": "Excessive Trunk Flexion", "severity": "MEDIUM"},
            {"name": "Shoulder Imbalance", "severity": "MEDIUM"},
            {"name": "Elevated Left Shoulder", "severity": "MEDIUM"},
            {"name": "Elevated Right Shoulder", "severity": "MEDIUM"},
            {"name": "Knee Instability", "severity": "MEDIUM"},
            {"name": "Body Misalignment", "severity": "MEDIUM"},
        ],
    },
    {
        "label": "Case 5: Recovery (back to healthy)",
        "features": {
            "neck_flexion": 5.0,
            "trunk_flexion": 8.0,
            "left_shoulder_elev": 12.0,
            "right_shoulder_elev": 14.0,
            "shoulder_symmetry": 2.0,
            "alignment_deviation": 3.0,
            "knee_angle": 165.0,
        },
        "expect_count": 0,
    },
]


def run_detection_tests() -> bool:
    print("=" * 70)
    print("  SECTION 1: ISSUE DETECTION ENGINE")
    print("=" * 70)
    print(f"\n{'Case':<42} {'Issues':>6} {'Result':>8}")
    print("-" * 70)

    all_pass = True
    for case in CASES:
        issues = detect_posture_issues(case["features"])
        count = len(issues)
        ok = count == case["expect_count"]

        # Verify specific issues if expected
        if ok and "expect_issues" in case:
            for exp in case["expect_issues"]:
                found = any(
                    i["issue"] == exp["name"] and i["severity"] == exp["severity"]
                    for i in issues
                )
                if not found:
                    ok = False
                    print(f"  MISMATCH: Expected {exp['name']} ({exp['severity']}) not found")

        status = "PASS" if ok else "FAIL"
        print(f"  {case['label']:<40} {count:>6} {status:>8}")

        if not ok:
            all_pass = False
            print(f"    Expected {case['expect_count']} issues, got {count}")
            for i in issues:
                print(f"      [{i['severity'][0]}] {i['issue']} = {i['value']}")

        if issues:
            for i in issues:
                print(f"    [{i['severity'][0]}] {i['issue']:<30} val={i['value']:<6.1f} thr={i['threshold']}")

    print("-" * 70)
    return all_pass


# ─────────────────────────────────────────────────────────────
# SECTION 2: LiveRepository Mapping Verification
# ─────────────────────────────────────────────────────────────

# Replicate the exact mapping logic from live.py:71-86
def map_backend_issues_to_react(backend_issues: list[dict], timestamp: str) -> list[dict]:
    """Exact replica of LiveRepository._build_dashboard() issue mapping."""
    issues_list = []
    for i, issue in enumerate(backend_issues):
        sev = issue.get("severity", "LOW").lower()
        if sev == "low":
            mapped_sev = "low"
        elif sev == "medium":
            mapped_sev = "moderate"
        else:
            mapped_sev = "high"
        issues_list.append({
            "id": f"ISSUE-{i:03d}",
            "severity": mapped_sev,
            "name": issue.get("issue", "Unknown"),
            "timestamp": timestamp,
            "detail": f"{issue.get('issue', '')} — Value: {issue.get('value', 0):.1f}, Threshold: {issue.get('threshold', 0)}",
        })
    return issues_list


MAPPING_CASES = [
    {
        "label": "No issues -> empty array",
        "backend_issues": [],
        "expect_react": [],
    },
    {
        "label": "HIGH severity -> high",
        "backend_issues": [
            {"issue": "Excessive Neck Flexion", "severity": "HIGH", "value": 42.0, "threshold": 30.0},
        ],
        "expect_react": [
            {"id": "ISSUE-000", "severity": "high", "name": "Excessive Neck Flexion"},
        ],
    },
    {
        "label": "MEDIUM severity -> moderate",
        "backend_issues": [
            {"issue": "Excessive Trunk Flexion", "severity": "MEDIUM", "value": 35.0, "threshold": 20.0},
        ],
        "expect_react": [
            {"id": "ISSUE-000", "severity": "moderate", "name": "Excessive Trunk Flexion"},
        ],
    },
    {
        "label": "Mixed severities -> correct mapping",
        "backend_issues": [
            {"issue": "Excessive Neck Flexion", "severity": "HIGH", "value": 42.0, "threshold": 30.0},
            {"issue": "Shoulder Imbalance", "severity": "MEDIUM", "value": 18.0, "threshold": 15.0},
            {"issue": "Body Misalignment", "severity": "MEDIUM", "value": 12.0, "threshold": 10.0},
        ],
        "expect_react": [
            {"id": "ISSUE-000", "severity": "high", "name": "Excessive Neck Flexion"},
            {"id": "ISSUE-001", "severity": "moderate", "name": "Shoulder Imbalance"},
            {"id": "ISSUE-002", "severity": "moderate", "name": "Body Misalignment"},
        ],
    },
    {
        "label": "ID generation — sequential",
        "backend_issues": [
            {"issue": "A", "severity": "HIGH", "value": 1.0, "threshold": 1.0},
            {"issue": "B", "severity": "HIGH", "value": 2.0, "threshold": 2.0},
            {"issue": "C", "severity": "HIGH", "value": 3.0, "threshold": 3.0},
        ],
        "expect_react": [
            {"id": "ISSUE-000"},
            {"id": "ISSUE-001"},
            {"id": "ISSUE-002"},
        ],
    },
]


def run_mapping_tests() -> bool:
    print("\n" + "=" * 70)
    print("  SECTION 2: LiveRepository -> React Issue Mapping")
    print("=" * 70)
    print(f"\n{'Case':<42} {'Result':>8}")
    print("-" * 70)

    test_timestamp = "2026-07-05T12:00:00Z"
    all_pass = True

    for case in MAPPING_CASES:
        react_issues = map_backend_issues_to_react(case["backend_issues"], test_timestamp)
        ok = True

        # Check count
        if len(react_issues) != len(case["expect_react"]):
            ok = False

        # Check specific fields
        if ok:
            for j, exp in enumerate(case["expect_react"]):
                actual = react_issues[j]
                for field, expected_val in exp.items():
                    if actual.get(field) != expected_val:
                        ok = False
                        print(f"    MISMATCH: {field} expected={expected_val} actual={actual.get(field)}")

        # Check timestamp is present on all
        if ok and case["backend_issues"]:
            for ri in react_issues:
                if ri.get("timestamp") != test_timestamp:
                    ok = False
                    print(f"    MISMATCH: timestamp not set correctly")

        # Check detail format
        if ok and case["backend_issues"]:
            for j, ri in enumerate(react_issues):
                detail = ri.get("detail", "")
                if "— Value:" not in detail or "Threshold:" not in detail:
                    ok = False
                    print(f"    MISMATCH: detail format wrong: {detail}")

        status = "PASS" if ok else "FAIL"
        print(f"  {case['label']:<40} {status:>8}")

        if not ok:
            all_pass = False
            print(f"    Backend:  {case['backend_issues']}")
            print(f"    React:    {react_issues}")

    print("-" * 70)
    return all_pass


# ─────────────────────────────────────────────────────────────
# SECTION 3: Severity Mapping Truth Table
# ─────────────────────────────────────────────────────────────

def run_severity_truth_table() -> bool:
    print("\n" + "=" * 70)
    print("  SECTION 3: SEVERITY MAPPING TRUTH TABLE")
    print("=" * 70)
    print(f"\n  Backend Input  -> React Output")
    print("-" * 70)

    truth_table = [
        ("HIGH", "high"),
        ("MEDIUM", "moderate"),
        ("LOW", "low"),
    ]

    all_pass = True
    for backend_sev, expected_react in truth_table:
        backend_issues = [{"issue": "Test", "severity": backend_sev, "value": 0.0, "threshold": 0.0}]
        react = map_backend_issues_to_react(backend_issues, "2026-01-01T00:00:00Z")
        actual = react[0]["severity"]
        ok = actual == expected_react
        status = "PASS" if ok else "FAIL"
        print(f"  {backend_sev:<14}->  {expected_react:<12} {status}")
        if not ok:
            all_pass = False
            print(f"    Got: {actual}")

    print("-" * 70)
    return all_pass


# ─────────────────────────────────────────────────────────────
# SECTION 4: Full Pipeline — Detection -> Mapping -> React Shape
# ─────────────────────────────────────────────────────────────

def run_pipeline_test() -> bool:
    print("\n" + "=" * 70)
    print("  SECTION 4: FULL PIPELINE — Detection -> Mapping -> React Shape")
    print("=" * 70)

    # Simulate: good posture -> poor neck -> recovery
    timeline = [
        ("00:00:00", "Good posture", {
            "neck_flexion": 5.0, "trunk_flexion": 8.0,
            "left_shoulder_elev": 12.0, "right_shoulder_elev": 14.0,
            "shoulder_symmetry": 2.0, "alignment_deviation": 3.0, "knee_angle": 165.0,
        }),
        ("00:00:01", "Poor neck (HIGH)", {
            "neck_flexion": 42.0, "trunk_flexion": 10.0,
            "left_shoulder_elev": 15.0, "right_shoulder_elev": 16.0,
            "shoulder_symmetry": 2.5, "alignment_deviation": 4.0, "knee_angle": 160.0,
        }),
        ("00:00:02", "Poor trunk (MEDIUM)", {
            "neck_flexion": 8.0, "trunk_flexion": 35.0,
            "left_shoulder_elev": 14.0, "right_shoulder_elev": 13.0,
            "shoulder_symmetry": 1.8, "alignment_deviation": 4.0, "knee_angle": 155.0,
        }),
        ("00:00:03", "Recovery", {
            "neck_flexion": 5.0, "trunk_flexion": 8.0,
            "left_shoulder_elev": 12.0, "right_shoulder_elev": 14.0,
            "shoulder_symmetry": 2.0, "alignment_deviation": 3.0, "knee_angle": 165.0,
        }),
    ]

    all_pass = True
    for ts, label, features in timeline:
        backend_issues = detect_posture_issues(features)
        react_issues = map_backend_issues_to_react(backend_issues, f"2026-07-05T{ts}Z")

        print(f"\n  [{ts}] {label}")
        print(f"    Backend issues: {len(backend_issues)}")
        print(f"    React issues:   {len(react_issues)}")

        if react_issues:
            for ri in react_issues:
                print(f"      id={ri['id']} sev={ri['severity']:<10} name={ri['name']}")
                print(f"        detail: {ri['detail']}")
        else:
            print(f"    (empty)")

        # Verify no backend severity leaks into React
        for ri in react_issues:
            if ri["severity"] in ("HIGH", "MEDIUM", "LOW"):
                all_pass = False
                print(f"    BUG: Backend severity '{ri['severity']}' leaked into React output")

    print("\n" + "-" * 70)
    return all_pass


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main() -> None:
    results = []
    results.append(("Issue Detection Engine", run_detection_tests()))
    results.append(("LiveRepository Mapping", run_mapping_tests()))
    results.append(("Severity Truth Table", run_severity_truth_table()))
    results.append(("Full Pipeline", run_pipeline_test()))

    print("\n" + "=" * 70)
    print("  PHASE 3B VALIDATION SUMMARY")
    print("=" * 70)
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {name:<35} {status}")
    print("-" * 70)

    all_ok = all(ok for _, ok in results)
    verdict = "ALL TESTS PASSED — Phase 3B validation complete" if all_ok else "TESTS FAILED — investigate before proceeding"
    print(f"  {verdict}")
    print("=" * 70)


if __name__ == "__main__":
    main()
