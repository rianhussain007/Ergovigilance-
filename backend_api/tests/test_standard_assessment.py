"""Tests for the authoritative RULA/REBA standard assessment gate.

Covers the core "fix the risk engine" behavior:
- Risk only fires when a published RULA/REBA rule is broken (band mapping).
- RULA is applied when the FULL body is NOT visible (legs out of frame).
- REBA is applied ONLY when the full body IS visible.
- A neutral posture scores LOW; a genuinely hunched/reaching pose scores HIGH.
"""

from __future__ import annotations

import numpy as np

from backend.services.features import (
    MEDIAPIPE_33,
    compute_rula_informed_score,
)
from backend.services.calibration import RELAXED, STANDARD, load_calibration
from backend.services.reba_scoring import reba_from_keypoints
from backend.services.standard_assessment import (
    FULL_BODY_THRESHOLD,
    assess_standard_risk,
    compute_rula_score,
    mediapipe_to_reba_points,
    reba_score_to_band,
    rula_score_to_band,
)


# ── MediaPipe-33 fixture (640x800 frame, person centered) ──────────

NEUTRAL = {
    "nose": (320, 120),
    "left_eye": (313, 122),
    "right_eye": (327, 122),
    "left_ear": (295, 130),
    "right_ear": (345, 130),
    "left_shoulder": (295, 220),
    "right_shoulder": (345, 220),
    "left_elbow": (295, 330),
    "right_elbow": (345, 330),
    "left_wrist": (295, 430),
    "right_wrist": (345, 430),
    "left_index": (295, 445),
    "right_index": (345, 445),
    "left_thumb": (299, 440),
    "right_thumb": (341, 440),
    "left_pinky": (296, 447),
    "right_pinky": (344, 447),
    "left_hip": (300, 420),
    "right_hip": (340, 420),
    "left_knee": (305, 560),
    "right_knee": (335, 560),
    "left_ankle": (305, 700),
    "right_ankle": (335, 700),
    "left_heel": (307, 720),
    "right_heel": (333, 720),
    "left_foot_index": (309, 730),
    "right_foot_index": (331, 730),
}


def _build_33(overrides: dict | None = None, visibility: float = 0.95) -> np.ndarray:
    kp = np.zeros((33, 4))
    kp[:, 3] = visibility
    pts = dict(NEUTRAL)
    if overrides:
        pts.update(overrides)
    for name, (x, y) in pts.items():
        if name in MEDIAPIPE_33:
            kp[MEDIAPIPE_33[name], 0] = x
            kp[MEDIAPIPE_33[name], 1] = y
        elif name == "left_eye":
            kp[2, 0] = x
            kp[2, 1] = y
        elif name == "right_eye":
            kp[5, 0] = x
            kp[5, 1] = y
    return kp


def _features(kp: np.ndarray) -> tuple[dict, list]:
    from backend.services.features import extract_features_from_keypoints
    feats, unavail, _ = extract_features_from_keypoints(kp)
    return feats, unavail


def _upper_only(kp: np.ndarray) -> np.ndarray:
    """Simulate legs out of frame: knees/ankles/feet hidden, hips still visible
    (waist-up framing keeps the trunk assessable — the realistic RULA case)."""
    out = kp.copy()
    for idx in (25, 26, 27, 28, 29, 30, 31, 32):
        out[idx, 3] = 0.0
    return out


class TestBandMapping:
    def test_reba_score_to_band(self):
        assert reba_score_to_band(1) == "LOW"
        assert reba_score_to_band(2) == "LOW"
        assert reba_score_to_band(3) == "LOW"
        assert reba_score_to_band(4) == "MEDIUM"
        assert reba_score_to_band(7) == "MEDIUM"
        assert reba_score_to_band(8) == "HIGH"
        assert reba_score_to_band(11) == "HIGH"
        assert reba_score_to_band(15) == "HIGH"

    def test_rula_score_to_band(self):
        assert rula_score_to_band(1) == "LOW"
        assert rula_score_to_band(2) == "LOW"
        assert rula_score_to_band(3) == "MEDIUM"
        assert rula_score_to_band(4) == "MEDIUM"
        assert rula_score_to_band(5) == "HIGH"
        assert rula_score_to_band(7) == "HIGH"


class TestMethodSelection:
    def test_full_body_uses_reba(self):
        kp = _build_33()
        feats, unavail = _features(kp)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=95.0)
        assert result["method"] == "REBA"
        assert result["risk_level"] == "LOW"

    def test_upper_body_only_uses_rula(self):
        kp = _upper_only(_build_33())
        feats, unavail = _features(kp)
        # Lower-body features are unavailable (legs out of frame).
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=5.0)
        assert result["method"] == "RULA"
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_lower_body_confidence_gate(self):
        """Just below the threshold -> RULA, at/above -> REBA (same pose)."""
        kp = _build_33()
        feats, unavail = _features(kp)
        below = assess_standard_risk(kp, feats, unavail, lower_body_confidence=FULL_BODY_THRESHOLD - 1.0)
        above = assess_standard_risk(kp, feats, unavail, lower_body_confidence=FULL_BODY_THRESHOLD)
        assert below["method"] == "RULA"
        assert above["method"] == "REBA"

    def test_no_person_returns_none(self):
        kp = np.zeros((33, 4))
        result = assess_standard_risk(kp, {}, [], lower_body_confidence=0.0)
        assert result["method"] == "NONE"
        assert result["risk_level"] is None


class TestRulaPartialBody:
    def test_neutral_upper_body_scores_low(self):
        """A neutral pose with legs out of frame must NOT score HIGH.

        Regression for the core complaint: partial body was previously
        fail-closed to elevated risk; RULA exists precisely to assess the
        upper body without legs, so a neutral pose is LOW.
        """
        kp = _upper_only(_build_33())
        feats, unavail = _features(kp)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=5.0)
        assert result["method"] == "RULA"
        assert result["risk_level"] == "LOW"
        assert result["is_partial"] is False  # missing legs don't make RULA partial

    def test_hunched_upper_body_scores_higher(self):
        """Trunk leaning forward (neck ahead of the hip line) is never LOW.

        With the relaxed (default) calibration a mild hunch scores MEDIUM;
        the point is that a genuine lean must still out-score neutral and
        must never read LOW.
        """
        # Forward hunch in 2D: shoulders/head shifted ahead of the hip x-line,
        # which the trunk_flexion feature reads as a real forward lean.
        kp = _upper_only(_build_33({
            "left_ear": (385, 130),
            "right_ear": (435, 130),
            "nose": (405, 120),
            "left_shoulder": (380, 220),
            "right_shoulder": (430, 220),
            "left_elbow": (390, 330),
            "right_elbow": (420, 330),
            "left_wrist": (395, 430),
            "right_wrist": (415, 430),
        }))
        feats, unavail = _features(kp)
        assert feats["trunk_flexion"] > 15  # actually leaning
        n_kp = _upper_only(_build_33())
        n_feats, n_unavail = _features(n_kp)
        neutral = assess_standard_risk(n_kp, n_feats, n_unavail, lower_body_confidence=5.0)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=5.0)
        assert result["method"] == "RULA"
        assert result["score"] > neutral["score"]
        assert result["risk_level"] in ("MEDIUM", "HIGH")

    def test_severe_pose_scores_high(self):
        """Hunched + arms overhead + head forward -> RULA 6 (HIGH)."""
        kp = _upper_only(_build_33({
            "left_ear": (380, 130),
            "right_ear": (430, 130),
            "nose": (400, 120),
            "left_shoulder": (375, 220),
            "right_shoulder": (425, 220),
            "left_elbow": (375, 170),
            "right_elbow": (425, 170),
            "left_wrist": (375, 120),
            "right_wrist": (425, 120),
            "left_index": (375, 100),
            "right_index": (425, 100),
        }))
        feats, unavail = _features(kp)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=5.0)
        assert result["method"] == "RULA"
        assert result["risk_level"] == "HIGH"
        assert result["score"] >= 5


class TestRebaFullBody:
    def test_neutral_full_body_low(self):
        kp = _build_33()
        feats, unavail = _features(kp)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=95.0)
        assert result["method"] == "REBA"
        assert result["risk_level"] == "LOW"

    def test_hunched_full_body_scores_higher(self):
        kp = _build_33({
            "left_shoulder": (295, 300),
            "right_shoulder": (345, 300),
            "left_elbow": (295, 410),
            "right_elbow": (345, 410),
            "left_wrist": (295, 500),
            "right_wrist": (345, 500),
            "left_hip": (300, 470),
            "right_hip": (340, 470),
        })
        feats, unavail = _features(kp)
        n_kp = _build_33()
        n_feats, n_unavail = _features(n_kp)
        neutral = assess_standard_risk(n_kp, n_feats, n_unavail, lower_body_confidence=95.0)
        hunched = assess_standard_risk(kp, feats, unavail, lower_body_confidence=95.0)
        assert hunched["method"] == "REBA"
        assert hunched["score"] > neutral["score"]

    def test_reba_details_exposed(self):
        kp = _build_33()
        feats, unavail = _features(kp)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=95.0)
        assert "reba_score" in result["details"]
        assert "trunk_score" in result["details"]


class TestMediapipeAdapter:
    def test_adapter_builds_reba_points(self):
        kp = _build_33()
        points = mediapipe_to_reba_points(kp)
        assert points["neck"][2] > 0
        assert points["center_hip"][2] > 0
        assert points["forehead"][2] > 0
        # Should be directly consumable by the REBA scorer.
        result = reba_from_keypoints(points)
        assert 1 <= result["reba_score"] <= 15

    def test_low_visibility_joints_marked_missing(self):
        kp = _build_33(visibility=0.1)  # everything below the 0.35 gate
        points = mediapipe_to_reba_points(kp)
        # Joints below the gate are emitted with visibility 0 (missing), and
        # composite joints whose parents are missing are dropped entirely.
        assert points["left_shoulder"][2] == 0.0
        assert "neck" not in points
        assert "center_hip" not in points


class TestRulaCompute:
    def test_neutral_rula_low(self):
        feats, unavail = _features(_build_33())
        rula = compute_rula_score(feats, unavail, legs_visible=True)
        assert rula["rula_informed_score"] <= 2

    def test_backward_compat_function(self):
        feats, unavail = _features(_build_33())
        rula = compute_rula_informed_score(feats, unavail)
        assert rula["rula_informed_score"] >= 1
        assert "is_partial_score" in rula

    def test_legs_not_visible_not_partial(self):
        feats, unavail = _features(_upper_only(_build_33()))
        rula = compute_rula_score(feats, unavail, legs_visible=False)
        assert rula["is_partial_score"] is False
        assert rula["rula_legs"] == 1


# A mild, ordinary work posture: slight trunk lean, slight neck flexion, arms
# slightly out, elbow near neutral, small wrist deviation. This is the exact
# case that used to flash yellow/red on the slightest movement.
SLIGHT_FEATURES = {
    "neck_flexion": 12.0,
    "trunk_flexion": 15.0,
    "upper_arm_angle_from_vertical": 25.0,
    "elbow_flexion_angle": 110.0,
    "wrist_deviation_angle": 8.0,
    "left_shoulder_elev": 20.0,
    "right_shoulder_elev": 20.0,
    "head_tilt_angle": 5.0,
    "stance_stability": 0.9,
}


class TestCalibration:
    """The calibration layer decides how much bend/strain starts scoring.

    Slight, normal postures must read LOW under the relaxed (default)
    profile while the same posture still reads MEDIUM under the published
    (standard) breakpoints — that gap is exactly the operator's tuning
    knob, and genuine severe risk stays HIGH under both.
    """

    def test_slight_posture_low_under_relaxed_default(self):
        rula = compute_rula_score(SLIGHT_FEATURES, legs_visible=True)
        assert rula["rula_informed_score"] <= 2
        assert rula["calibration"] == "relaxed"

    def test_slight_posture_medium_under_standard(self):
        rula = compute_rula_score(
            SLIGHT_FEATURES, legs_visible=True, calibration=STANDARD
        )
        assert rula["rula_informed_score"] >= 3

    def test_calibration_exposed_in_gate_details(self):
        kp = _build_33()
        feats, unavail = _features(kp)
        relaxed = assess_standard_risk(kp, feats, unavail, lower_body_confidence=5.0)
        standard = assess_standard_risk(
            kp, feats, unavail, lower_body_confidence=5.0, calibration=STANDARD
        )
        assert relaxed["details"]["calibration"] == "relaxed"
        assert standard["details"]["calibration"] == "standard"

    def test_severe_pose_stays_high_under_relaxed(self):
        kp = _upper_only(_build_33({
            "left_ear": (380, 130),
            "right_ear": (430, 130),
            "nose": (400, 120),
            "left_shoulder": (375, 220),
            "right_shoulder": (425, 220),
            "left_elbow": (375, 170),
            "right_elbow": (425, 170),
            "left_wrist": (375, 120),
            "right_wrist": (425, 120),
            "left_index": (375, 100),
            "right_index": (425, 100),
        }))
        feats, unavail = _features(kp)
        result = assess_standard_risk(kp, feats, unavail, lower_body_confidence=5.0)
        assert result["risk_level"] == "HIGH"
        assert result["score"] >= 5

    def test_load_calibration_presets(self):
        assert load_calibration("standard") is STANDARD
        assert load_calibration("relaxed") is RELAXED
        assert load_calibration("garbage-value") is RELAXED
        assert load_calibration("") is RELAXED

    def test_load_calibration_custom_json(self):
        cal = load_calibration('{"trunk_neutral_max": 20, "neck_neutral_max": 25}')
        assert cal.name == "custom"
        assert cal.trunk_neutral_max == 20.0
        assert cal.neck_neutral_max == 25.0
        assert cal.trunk_medium_max == RELAXED.trunk_medium_max  # rest inherited

    def test_risk_breakdown_follows_calibration(self):
        from backend.services.features import risk_breakdown
        feats = {"neck_flexion": 12.0, "trunk_flexion": 12.0}
        relaxed = risk_breakdown(feats)
        assert relaxed["neck_flexion"].level == "LOW"
        standard = risk_breakdown(feats, calibration=STANDARD)
        assert standard["neck_flexion"].level == "MEDIUM"

    def test_issue_detection_follows_calibration(self):
        from backend.services.issue_detection import detect_posture_issues
        feats = {
            "neck_flexion": 12.0, "trunk_flexion": 12.0,
            "left_shoulder_elev": 10.0, "right_shoulder_elev": 10.0,
            "shoulder_symmetry": 2.0, "knee_angle": 165.0,
            "forward_head_posture": 8.0, "head_tilt_angle": 5.0,
            "wrist_deviation_angle": 6.0, "stance_stability": 0.9,
            "weight_shift_offset": 4.0,
        }
        assert detect_posture_issues(feats) == []  # relaxed: below the allowance
        issues = detect_posture_issues(feats, calibration=STANDARD)
        assert any(i["issue"] == "Excessive Neck Flexion" for i in issues)
