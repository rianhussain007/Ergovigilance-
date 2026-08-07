from __future__ import annotations

from typing import Dict, List, Mapping


_ISSUE_RULES = [
    {
        "issue": "Excessive Neck Flexion",
        "feature": "neck_flexion",
        "med_min": 10,
        "med_max": 30,
        "high_min": 30,
        "inverted": False,
    },
    {
        "issue": "Excessive Trunk Flexion",
        "feature": "trunk_flexion",
        "med_min": 20,
        "med_max": 60,
        "high_min": 60,
        "inverted": False,
    },
    {
        "issue": "Shoulder Imbalance",
        "feature": "shoulder_symmetry",
        "med_min": 5,
        "med_max": 15,
        "high_min": 15,
        "inverted": False,
    },
    {
        "issue": "Elevated Left Shoulder",
        "feature": "left_shoulder_elev",
        "med_min": 30,
        "med_max": 60,
        "high_min": 60,
        "inverted": False,
    },
    {
        "issue": "Elevated Right Shoulder",
        "feature": "right_shoulder_elev",
        "med_min": 30,
        "med_max": 60,
        "high_min": 60,
        "inverted": False,
    },
    {
        "issue": "Knee Instability",
        "feature": "knee_angle",
        "med_min": 100,
        "med_max": 150,
        "high_min": 100,
        "inverted": True,
    },
    {
        "issue": "Body Misalignment",
        "feature": "alignment_deviation",
        "med_min": 10,
        "med_max": 25,
        "high_min": 25,
        "inverted": False,
    },
    # Phase-A additions (2026-08): head / wrist / stance issues
    {
        "issue": "Forward Head Posture",
        "feature": "forward_head_posture",
        "med_min": 10,
        "med_max": 20,
        "high_min": 20,
        "inverted": False,
    },
    {
        "issue": "Head Tilt",
        "feature": "head_tilt_angle",
        "med_min": 10,
        "med_max": 20,
        "high_min": 20,
        "inverted": False,
    },
    {
        "issue": "Wrist Deviation",
        "feature": "wrist_deviation_angle",
        "med_min": 5,
        "med_max": 15,
        "high_min": 15,
        "inverted": False,
    },
    {
        "issue": "Unstable Stance",
        "feature": "stance_stability",
        "med_min": 0.7,
        "med_max": 0.7,
        "high_min": 0.5,
        "inverted": True,
    },
    {
        "issue": "Weight Shift",
        "feature": "weight_shift_offset",
        "med_min": 8,
        "med_max": 15,
        "high_min": 15,
        "inverted": False,
    },
]


def detect_posture_issues(features: Mapping[str, float]) -> List[Dict]:
    issues: List[Dict] = []
    for rule in _ISSUE_RULES:
        value = features.get(rule["feature"], 0.0)
        if rule["inverted"]:
            if value < rule["high_min"]:
                severity = "HIGH"
            elif value < rule["med_max"]:
                severity = "MEDIUM"
            else:
                continue
            threshold = rule["med_max"]
        else:
            if value > rule["high_min"]:
                severity = "HIGH"
            elif value > rule["med_min"]:
                severity = "MEDIUM"
            else:
                continue
            threshold = rule["high_min"] if value > rule["high_min"] else rule["med_min"]

        issues.append({
            "issue": rule["issue"],
            "severity": severity,
            "value": round(value, 2),
            "threshold": float(threshold),
        })
    return issues


def summarize_issues(issues: List[Dict]) -> str:
    count = len(issues)
    if count == 0:
        return "No issues detected"
    if count == 1:
        return "1 posture issue detected"
    return f"{count} posture issues detected"


def highest_priority_issue(issues: List[Dict]) -> Dict | None:
    if not issues:
        return None
    priority = {"HIGH": 0, "MEDIUM": 1}
    return min(issues, key=lambda i: priority.get(i["severity"], 2))
