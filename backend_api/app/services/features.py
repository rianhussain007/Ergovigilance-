"""Ergonomic feature risk breakdown using RULA/REBA-informed thresholds.

Each feature is classified into LOW, MEDIUM, or HIGH risk based on
validated ergonomic assessment thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class BreakResult:
    """Risk classification for a single ergonomic feature."""
    level: str  # LOW, MEDIUM, HIGH
    value: float
    threshold_low: float
    threshold_high: float


# RULA/REBA-informed threshold table.
# (feature_key, low_threshold, high_threshold)
# Below low = LOW risk, between low-high = MEDIUM, above high = HIGH.
# For "lower is worse" features (like knee_angle), thresholds are inverted.
_THRESHOLDS: list[tuple[str, float, float]] = [
    ("neck_flexion",          15.0, 30.0),
    ("trunk_flexion",         20.0, 40.0),
    ("left_shoulder_elev",    30.0, 60.0),
    ("right_shoulder_elev",   30.0, 60.0),
    ("shoulder_symmetry",     10.0, 20.0),
    ("alignment_deviation",   5.0,  15.0),
    ("forward_head_posture",  10.0, 25.0),
    ("head_tilt_angle",       10.0, 25.0),
    ("wrist_deviation_angle", 10.0, 20.0),
    ("weight_shift_offset",   8.0,  18.0),
    # Knee angle: lower is worse (deeper squat = more strain)
    ("knee_angle",            90.0, 120.0),
    # Stance stability: lower is worse (0 = very unstable)
    ("stance_stability",      0.3,  0.6),
]


def risk_breakdown(features: Dict[str, float]) -> Dict[str, BreakResult]:
    """Classify each ergonomic feature into risk bands.

    Args:
        features: dict mapping feature names to their current values.

    Returns:
        dict mapping feature names to BreakResult with level, value, thresholds.
    """
    import math
    result: Dict[str, BreakResult] = {}

    for key, low_thresh, high_thresh in _THRESHOLDS:
        raw = features.get(key, 0.0)
        val = 0.0 if (isinstance(raw, float) and math.isnan(raw)) else float(raw)

        if key in ("knee_angle", "stance_stability"):
            # Lower values = higher risk (inverted thresholds)
            if val >= high_thresh:
                level = "LOW"
            elif val >= low_thresh:
                level = "MEDIUM"
            else:
                level = "HIGH"
        else:
            # Standard: higher values = higher risk
            if val <= low_thresh:
                level = "LOW"
            elif val <= high_thresh:
                level = "MEDIUM"
            else:
                level = "HIGH"

        result[key] = BreakResult(
            level=level,
            value=val,
            threshold_low=low_thresh,
            threshold_high=high_thresh,
        )

    return result


def load_calibration(*args, **kwargs):
    """Compatibility stub — real calibration lives in calibration.py."""
    return None


def compute_rula_informed_score(features: Dict[str, float]) -> float:
    """Compute an overall RULA/REBA-informed risk score from ergonomic features.

    Returns a float 0-10 where higher means more risk.
    """
    import math
    breakdown = risk_breakdown(features)
    scores = {"LOW": 1, "MEDIUM": 5, "HIGH": 9}
    vals = [scores.get(b.level, 1) for b in breakdown.values()]
    return round(sum(vals) / max(len(vals), 1), 1)


def unavailable_features_from_keypoints(keypoints: Optional[dict] = None) -> list:
    """Return list of features that cannot be computed from available keypoints.

    If keypoints dict is None or missing critical landmarks, returns all features.
    """
    if not keypoints:
        return [k for k, _, _ in _THRESHOLDS]
    unavailable = []
    # Check if we have enough landmarks for each feature group
    landmark_count = len(keypoints) if isinstance(keypoints, dict) else 0
    if landmark_count < 33:
        # Some features may be unavailable with partial keypoints
        if landmark_count < 25:
            unavailable.extend(["knee_angle", "stance_stability", "weight_shift_offset"])
        if landmark_count < 13:
            unavailable.extend(["left_shoulder_elev", "right_shoulder_elev", "wrist_deviation_angle"])
    return unavailable


def lower_body_confidence(keypoints: Optional[dict] = None) -> float:
    """Estimate confidence of lower body landmark detection (0.0 to 1.0).

    Returns high confidence if legs/knees/feet landmarks are available.
    """
    if not keypoints or not isinstance(keypoints, dict):
        return 0.0
    # COCO lower body landmarks: hips(23,24), knees(25,26), ankles(27,28), feet(29,30,31,32)
    lower_ids = {23, 24, 25, 26, 27, 28, 29, 30, 31, 32}
    present = sum(1 for lid in lower_ids if lid in keypoints and keypoints[lid] is not None)
    return round(present / len(lower_ids), 2)
