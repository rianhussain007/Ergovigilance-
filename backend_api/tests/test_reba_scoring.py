"""Unit tests for backend/services/reba_scoring.py (standard REBA from 2D joints)."""

from __future__ import annotations

from backend.services.reba_scoring import (
    reba_from_keypoints,
    reba_risk_band,
)


def _pose(**overrides) -> dict:
    """Neutral upright pose in named-keypoint format (COCO visibility 2)."""
    pts = {
        "forehead": [320, 110, 2],
        "nose": [320, 120, 2],
        "left_eye": [310, 118, 2],
        "right_eye": [330, 118, 2],
        "left_ear": [295, 130, 2],
        "right_ear": [345, 130, 2],
        "neck": [320, 220, 2],
        "left_shoulder": [295, 220, 2],
        "right_shoulder": [345, 220, 2],
        "left_elbow": [295, 330, 2],
        "right_elbow": [345, 330, 2],
        "left_wrist": [295, 430, 2],
        "right_wrist": [345, 430, 2],
        "left_hand": [295, 445, 2],
        "right_hand": [345, 445, 2],
        "left_hip": [300, 420, 2],
        "center_hip": [320, 420, 2],
        "right_hip": [340, 420, 2],
        "left_knee": [305, 560, 2],
        "right_knee": [335, 560, 2],
        "left_ankle": [305, 700, 2],
        "right_ankle": [335, 700, 2],
    }
    pts.update(overrides)
    return pts


class TestNeutralPose:
    def test_neutral_scores_low(self):
        result = reba_from_keypoints(_pose())
        assert result["reba_score"] <= 4
        assert result["reba_risk_level"] <= 3
        assert result["score_a"] <= 4
        assert result["score_b"] <= 4

    def test_neutral_band_not_high(self):
        result = reba_from_keypoints(_pose())
        assert reba_risk_band(int(result["reba_risk_level"])) in {"LOW", "MEDIUM"}


class TestRiskyPoses:
    def test_hunched_forward_scores_higher(self):
        # Trunk leans ~30 deg forward (neck ~115px ahead of the hip), head follows.
        hunched = _pose(
            forehead=[435, 130, 2], nose=[435, 140, 2],
            left_ear=[410, 150, 2], right_ear=[460, 150, 2],
            neck=[435, 220, 2], left_shoulder=[410, 225, 2], right_shoulder=[460, 225, 2],
            left_elbow=[425, 330, 2], right_elbow=[445, 330, 2],
            left_wrist=[420, 430, 2], right_wrist=[450, 430, 2],
            left_hand=[418, 445, 2], right_hand=[452, 445, 2],
        )
        result = reba_from_keypoints(hunched)
        neutral = reba_from_keypoints(_pose())
        assert result["trunk_score"] >= 2
        assert result["reba_score"] > neutral["reba_score"]

    def test_deep_knee_bend_increases_legs_and_total(self):
        # Deep squat: knees bent ~60+ deg (hip above knee, ankle forward).
        squat = _pose(
            forehead=[390, 160, 2], nose=[390, 170, 2],
            neck=[390, 250, 2], left_shoulder=[365, 255, 2], right_shoulder=[415, 255, 2],
            left_elbow=[375, 360, 2], right_elbow=[405, 360, 2],
            left_wrist=[370, 440, 2], right_wrist=[420, 440, 2],
            center_hip=[370, 420, 2], left_hip=[350, 425, 2], right_hip=[390, 425, 2],
            left_knee=[370, 520, 2], right_knee=[410, 520, 2],
            left_ankle=[510, 590, 2], right_ankle=[550, 590, 2],
        )
        result = reba_from_keypoints(squat)
        neutral = reba_from_keypoints(_pose())
        assert result["legs_score"] >= 2
        assert result["reba_score"] > neutral["reba_score"]


class TestDegradation:
    def test_missing_joints_do_not_crash(self):
        pose = _pose()
        for j in ("left_knee", "right_knee", "left_ankle", "right_ankle", "center_hip"):
            pose[j] = [0, 0, 0]
        result = reba_from_keypoints(pose)
        assert 1 <= result["reba_score"] <= 15
        assert 1 <= result["reba_risk_level"] <= 5

    def test_missing_neck_does_not_wrap_to_worst_case(self):
        # Regression: a missing neck used to index TABLE_A with -1 (worst
        # row/col). Missing joints must not inflate the score above the
        # same pose with the joints present.
        complete = reba_from_keypoints(_pose())
        missing_neck = _pose()
        missing_neck["neck"] = [0, 0, 0]
        missing_neck["center_hip"] = [0, 0, 0]
        result = reba_from_keypoints(missing_neck)
        assert result["reba_score"] <= complete["reba_score"]
        assert result["trunk_score"] == 0 or result["reba_score"] <= 4

    def test_band_mapping(self):
        assert reba_risk_band(1) == "LOW"
        assert reba_risk_band(2) == "MEDIUM"
        assert reba_risk_band(3) == "MEDIUM"
        assert reba_risk_band(4) == "HIGH"
        assert reba_risk_band(5) == "HIGH"
