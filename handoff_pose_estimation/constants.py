from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


FEATURE_COLUMNS = [
    "neck_flexion",
    "trunk_flexion",
    "left_shoulder_elev",
    "right_shoulder_elev",
    "shoulder_symmetry",
    "alignment_deviation",
    "knee_angle",
]

FEATURE_THRESHOLDS = {
    "neck_flexion": "LOW <= 10 deg, MEDIUM 10-30 deg, HIGH > 30 deg",
    "trunk_flexion": "LOW <= 20 deg, MEDIUM 20-60 deg, HIGH > 60 deg",
    "left_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "right_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "shoulder_symmetry": "LOW <= 5%, MEDIUM 5-15%, HIGH > 15%",
    "alignment_deviation": "Lower is better; large horizontal ear-to-hip offset suggests alignment risk",
    "knee_angle": "LOW >= 150 deg, MEDIUM 100-150 deg, HIGH < 100 deg",
}


MEDIAPIPE_33 = {
    "nose": 0,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}

COCO_17 = {
    "nose": 0,
    "left_ear": 3,
    "right_ear": 4,
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_elbow": 7,
    "right_elbow": 8,
    "left_hip": 11,
    "right_hip": 12,
    "left_ankle": 15,
    "right_ankle": 16,
}

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


RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

RISK_LEVELS_DICT = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


RISK_COLORS_BGR: Mapping[str, tuple[int, int, int]] = {
    "LOW": (40, 170, 70),
    "MEDIUM": (0, 165, 255),
    "HIGH": (40, 40, 220),
}


@dataclass(frozen=True)
class RiskBreakdown:
    level: str
    color: tuple[int, int, int]


CONFIDENCE_LANDMARKS = list(range(0, 17))

LOWER_BODY_LANDMARKS = [23, 24, 25, 26, 27, 28]
UPPER_BODY_LANDMARKS = list(range(0, 17))
