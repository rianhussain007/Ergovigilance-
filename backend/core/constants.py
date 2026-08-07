"""Centralized constants for ErgoVigilance.

Single source of truth for all shared constants across subsystems.
Original modules re-export these for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


# ── Feature Extraction ──────────────────────────────────────────────

FEATURE_COLUMNS = [
    # Core trunk / neck / shoulders
    "neck_flexion",
    "trunk_flexion",
    "left_shoulder_elev",
    "right_shoulder_elev",
    "shoulder_symmetry",
    "alignment_deviation",
    # Lower body
    "knee_angle",
    # Arms
    "elbow_flexion_angle",
    "upper_arm_angle_from_vertical",
    # Phase-A additions (2026-08): head/hand/stance ergonomics
    "forward_head_posture",
    "head_tilt_angle",
    "wrist_deviation_angle",
    "stance_stability",
    "weight_shift_offset",
    "hand_reach_ratio",
    "finger_spread_ratio",
    "stance_width_ratio",
]

FEATURE_THRESHOLDS = {
    "neck_flexion": "LOW <= 10 deg, MEDIUM 10-30 deg, HIGH > 30 deg",
    "trunk_flexion": "LOW <= 20 deg, MEDIUM 20-60 deg, HIGH > 60 deg",
    "left_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "right_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "shoulder_symmetry": "LOW <= 5%, MEDIUM 5-15%, HIGH > 15%",
    "alignment_deviation": "Lower is better; large horizontal ear-to-hip offset suggests alignment risk",
    "knee_angle": "LOW >= 150 deg, MEDIUM 100-150 deg, HIGH < 100 deg",
    "elbow_flexion_angle": "LOW >= 90 deg, MEDIUM 45-90 deg, HIGH < 45 deg",
    "upper_arm_angle_from_vertical": "LOW <= 20 deg, MEDIUM 20-45 deg, HIGH > 45 deg",
    "forward_head_posture": "LOW <= 10% shoulder-width, MEDIUM 10-20%, HIGH > 20% (head protrusion)",
    "head_tilt_angle": "LOW <= 10 deg, MEDIUM 10-20 deg, HIGH > 20 deg (head off vertical)",
    "wrist_deviation_angle": "LOW <= 5 deg, MEDIUM 5-15 deg, HIGH > 15 deg (RULA Table B)",
    "stance_stability": "LOW >= 0.7, MEDIUM 0.5-0.7, HIGH < 0.5 (min(ankle/hip span, hip/ankle span))",
    "weight_shift_offset": "LOW <= 8% torso, MEDIUM 8-15%, HIGH > 15% (mid-ankle vs mid-hip offset)",
    "hand_reach_ratio": "Reference (task signal); fingertip-to-shoulder distance / torso length",
    "finger_spread_ratio": "Reference (task signal); index-thumb spread / wrist-index length",
    "stance_width_ratio": "Reference; ankle span / hip span (ideal near 1.0)",
}


# ── Keypoint Index Maps ────────────────────────────────────────────

MEDIAPIPE_33 = {
    "nose": 0,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_pinky": 17,
    "right_pinky": 18,
    "left_index": 19,
    "right_index": 20,
    "left_thumb": 21,
    "right_thumb": 22,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}

COCO_17 = {
    "nose": 0,
    "left_ear": 3,
    "right_ear": 4,
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_elbow": 7,
    "right_elbow": 8,
    "left_wrist": 9,
    "right_wrist": 10,
    "left_hip": 11,
    "right_hip": 12,
    "left_knee": 13,
    "right_knee": 14,
    "left_ankle": 15,
    "right_ankle": 16,
}

# Keypoint indices used by TaskRecognition ( MediaPipe 33 indices)
TASK_KEYPOINT_INDICES = {
    "LEFT_SHOULDER": 11,
    "RIGHT_SHOULDER": 12,
    "LEFT_ELBOW": 13,
    "RIGHT_ELBOW": 14,
    "LEFT_WRIST": 15,
    "RIGHT_WRIST": 16,
    "LEFT_HIP": 23,
    "RIGHT_HIP": 24,
    "LEFT_KNEE": 25,
    "RIGHT_KNEE": 26,
    "LEFT_ANKLE": 27,
    "RIGHT_ANKLE": 28,
    "NOSE": 0,
}


# ── Risk Levels ─────────────────────────────────────────────────────

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

RISK_LEVELS_DICT = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


# ── Risk Colors (BGR for OpenCV) ───────────────────────────────────

RISK_COLORS_BGR: Mapping[str, tuple[int, int, int]] = {
    "LOW": (40, 170, 70),
    "MEDIUM": (0, 165, 255),
    "HIGH": (40, 40, 220),
}


@dataclass(frozen=True)
class RiskBreakdown:
    level: str
    color: tuple[int, int, int]


# ── Confidence Landmarks ───────────────────────────────────────────

CONFIDENCE_LANDMARKS = list(range(0, 17))

# Lower-body landmarks (MediaPipe 33 indices) — used to detect when
# the camera framing cuts off the legs, making trunk/knee features unreliable.
LOWER_BODY_LANDMARKS = [23, 24, 25, 26, 27, 28]  # hips, knees, ankles
UPPER_BODY_LANDMARKS = list(range(0, 17))
