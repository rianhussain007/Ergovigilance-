"""Unit tests for the Phase-A CV-core additions (2026-08).

Covers the newly activated MediaPipe-33 landmarks and the 8 new
ergonomic features (forward_head_posture, head_tilt_angle,
wrist_deviation_angle, stance_stability, weight_shift_offset,
hand_reach_ratio, finger_spread_ratio, stance_width_ratio), plus the
two angle-inversion fixes (head_tilt, upper_arm) that the new features
exposed.

Geometric conventions used here (frame 640x800, person centered):
  - Neutral upright posture: all angles ~0, risk LOW, RULA low.
  - Bent wrist (index bent sideways): wrist_deviation_angle > 15 -> HIGH.
  - Arms raised: upper_arm_angle_from_vertical increases, RULA rises.
  - COCO_17 keypoints (no fingers/feet): new features degrade to NaN,
    pipeline still returns a sane risk without crashing.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.services.features import (
    COCO_17,
    MEDIAPIPE_33,
    FEATURE_COLUMNS,
    compute_rula_informed_score,
    extract_features_from_keypoints,
    risk_from_features,
)

# Canonical neutral-upright posture (pixel coordinates, visibility 0.95).
NEUTRAL = {
    "nose": (320, 120),
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
        kp[MEDIAPIPE_33[name], 0] = x
        kp[MEDIAPIPE_33[name], 1] = y
    return kp


def _extract(kp) -> tuple[dict, list, list]:
    return extract_features_from_keypoints(kp)


class TestNeutralPosture:
    def test_all_17_columns_present(self):
        feats, unavail, _ = _extract(_build_33())
        assert set(FEATURE_COLUMNS) <= set(feats.keys())
        assert len(feats) >= 17

    def test_neutral_angles_are_zero(self):
        feats, _, _ = _extract(_build_33())
        assert feats["head_tilt_angle"] == pytest.approx(0.0, abs=0.5)
        assert feats["upper_arm_angle_from_vertical"] == pytest.approx(0.0, abs=0.5)
        assert feats["forward_head_posture"] == pytest.approx(0.0, abs=0.5)
        assert feats["wrist_deviation_angle"] == pytest.approx(0.0, abs=0.5)

    def test_neutral_stance_is_stable(self):
        feats, _, _ = _extract(_build_33())
        assert feats["stance_stability"] >= 0.7
        assert feats["weight_shift_offset"] <= 8.0

    def test_neutral_risk_is_low(self):
        feats, unavail, _ = _extract(_build_33())
        assert risk_from_features(feats, unavail) == "LOW"

    def test_neutral_rula_is_not_maxed(self):
        feats, unavail, _ = _extract(_build_33())
        rula = compute_rula_informed_score(feats, unavail)
        assert rula["rula_informed_score"] <= 5
        assert rula["is_partial_score"] is False


class TestNewFeatures:
    def test_forward_head_posture_detects_protrusion(self):
        # Head juts ~25px ahead of the neck (shoulder width = 50px -> 50%).
        feats, _, _ = _extract(_build_33({"nose": (345, 120), "left_ear": (320, 130), "right_ear": (370, 130)}))
        assert feats["forward_head_posture"] > 20
        assert risk_from_features(feats, []) in {"MEDIUM", "HIGH"}

    def test_head_tilt_detects_side_tilt(self):
        feats, _, _ = _extract(_build_33({"nose": (335, 120)}))
        assert feats["head_tilt_angle"] > 20

    def test_wrist_deviation_detects_bent_wrist(self):
        kp = _build_33({"left_index": (320, 435)})
        feats, unavail, _ = _extract(kp)
        assert feats["wrist_deviation_angle"] > 15
        assert risk_from_features(feats, unavail) == "HIGH"

    def test_stance_stability_penalizes_narrow_stance(self):
        kp = _build_33({"left_ankle": (315, 700), "right_ankle": (325, 700)})
        feats, unavail, _ = _extract(kp)
        assert feats["stance_stability"] < 0.7

    def test_weight_shift_detects_offset(self):
        kp = _build_33({"left_ankle": (280, 700), "right_ankle": (320, 700)})
        feats, _, _ = _extract(kp)
        assert feats["weight_shift_offset"] > 8

    def test_hand_reach_grows_with_reach(self):
        # Baseline: hands hanging at the sides. Reaching pose: arms extended
        # horizontally, so fingertips are farther from the neck midpoint.
        close_feats, _, _ = _extract(_build_33())
        far_feats, _, _ = _extract(_build_33({"left_index": (90, 240), "right_index": (550, 240)}))
        assert far_feats["hand_reach_ratio"] > close_feats["hand_reach_ratio"]

    def test_finger_spread_reflects_grip(self):
        kp = _build_33({"left_thumb": (290, 420), "right_thumb": (350, 420)})
        feats, _, _ = _extract(kp)
        assert feats["finger_spread_ratio"] > 1.0


class TestCocoDegradation:
    def test_missing_fingers_yield_nan(self):
        coco = np.zeros((17, 4))
        coco[:, 3] = 0.95
        pts = {k: v for k, v in NEUTRAL.items() if k in COCO_17}
        for name, (x, y) in pts.items():
            coco[COCO_17[name], 0] = x
            coco[COCO_17[name], 1] = y
        feats, unavail, _ = _extract(coco)
        assert feats["wrist_deviation_angle"] != feats["wrist_deviation_angle"]  # NaN
        assert feats["hand_reach_ratio"] != feats["hand_reach_ratio"]  # NaN
        assert "wrist_deviation_angle" in unavail
        # Pipeline must not crash and should not over-alarm on a neutral pose.
        assert risk_from_features(feats, unavail) == "LOW"

    def test_short_keypoint_rows_do_not_crash(self):
        kp = np.zeros((10, 3))  # no visibility column, < 25 rows -> COCO path
        feats, unavail, _ = _extract(kp)
        assert set(FEATURE_COLUMNS) <= set(feats.keys())
        assert risk_from_features(feats, unavail) in {"LOW", "MEDIUM", "HIGH"}
