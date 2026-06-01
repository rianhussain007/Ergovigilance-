from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np


FEATURE_COLUMNS = [
    "neck_flexion",
    "trunk_flexion",
    "left_shoulder_elev",
    "right_shoulder_elev",
    "shoulder_symmetry",
    "alignment_deviation",
]

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

FEATURE_THRESHOLDS = {
    "neck_flexion": "LOW <= 10 deg, MEDIUM 10-30 deg, HIGH > 30 deg",
    "trunk_flexion": "LOW <= 20 deg, MEDIUM 20-60 deg, HIGH > 60 deg",
    "left_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "right_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "shoulder_symmetry": "LOW <= 5%, MEDIUM 5-15%, HIGH > 15%",
    "alignment_deviation": "Lower is better; large horizontal ear-to-hip offset suggests alignment risk",
}

FEATURE_DEPENDENCIES = {
    "neck_flexion": ["left_ear", "right_ear", "left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "trunk_flexion": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "left_shoulder_elev": ["left_shoulder", "left_elbow"],
    "right_shoulder_elev": ["right_shoulder", "right_elbow"],
    "shoulder_symmetry": ["left_shoulder", "right_shoulder"],
    "alignment_deviation": ["left_ear", "right_ear", "left_hip", "right_hip"],
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
}


@dataclass(frozen=True)
class RiskBreakdown:
    level: str
    color: tuple[int, int, int]


RISK_COLORS_BGR: Mapping[str, tuple[int, int, int]] = {
    "LOW": (40, 170, 70),
    "MEDIUM": (0, 165, 255),
    "HIGH": (40, 40, 220),
}


def angle_between_three_points(p1: Sequence[float], p2: Sequence[float], p3: Sequence[float]) -> float:
    v1 = np.array(p1[:2], dtype=float) - np.array(p2[:2], dtype=float)
    v2 = np.array(p3[:2], dtype=float) - np.array(p2[:2], dtype=float)
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom == 0:
        return float("nan")
    cos_angle = np.dot(v1, v2) / denom
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))


def _midpoint(a: Sequence[float], b: Sequence[float]) -> np.ndarray:
    return (np.array(a[:2], dtype=float) + np.array(b[:2], dtype=float)) / 2.0


def _safe_distance(a: Sequence[float], b: Sequence[float], default: float = 1.0) -> float:
    value = float(np.linalg.norm(np.array(a[:2], dtype=float) - np.array(b[:2], dtype=float)))
    return value if value > 1e-9 else default


def _point(kps: np.ndarray, index_map: Mapping[str, int], name: str) -> np.ndarray:
    return np.array(kps[index_map[name]][:2], dtype=float)


def extract_features_from_keypoints(
    keypoints: Sequence[Sequence[float]],
    index_map: Mapping[str, int] | None = None,
) -> Dict[str, float]:
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17

    left_ear = _point(kps, index_map, "left_ear")
    right_ear = _point(kps, index_map, "right_ear")
    left_shoulder = _point(kps, index_map, "left_shoulder")
    right_shoulder = _point(kps, index_map, "right_shoulder")
    left_elbow = _point(kps, index_map, "left_elbow")
    right_elbow = _point(kps, index_map, "right_elbow")
    left_hip = _point(kps, index_map, "left_hip")
    right_hip = _point(kps, index_map, "right_hip")

    ear = _midpoint(left_ear, right_ear)
    neck = _midpoint(left_shoulder, right_shoulder)
    hip = _midpoint(left_hip, right_hip)
    shoulder_width = _safe_distance(left_shoulder, right_shoulder)
    torso_len = _safe_distance(neck, hip, default=shoulder_width)

    vertical_up_from_hip = np.array([hip[0], hip[1] - torso_len])
    vertical_down_left = np.array([left_shoulder[0], left_shoulder[1] + shoulder_width])
    vertical_down_right = np.array([right_shoulder[0], right_shoulder[1] + shoulder_width])

    raw_neck = angle_between_three_points(ear, neck, hip)
    neck_flexion = abs(180.0 - raw_neck)
    trunk_flexion = angle_between_three_points(neck, hip, vertical_up_from_hip)
    left_shoulder_elev = angle_between_three_points(left_elbow, left_shoulder, vertical_down_left)
    right_shoulder_elev = angle_between_three_points(right_elbow, right_shoulder, vertical_down_right)
    shoulder_symmetry = abs(left_shoulder[1] - right_shoulder[1]) / shoulder_width * 100.0
    alignment_deviation = abs(ear[0] - hip[0]) / torso_len * 100.0

    features = {
        "neck_flexion": neck_flexion,
        "trunk_flexion": trunk_flexion,
        "left_shoulder_elev": left_shoulder_elev,
        "right_shoulder_elev": right_shoulder_elev,
        "shoulder_symmetry": shoulder_symmetry,
        "alignment_deviation": alignment_deviation,
    }
    return {name: round(float(np.nan_to_num(features[name], nan=0.0)), 4) for name in FEATURE_COLUMNS}


def risk_from_features(features: Mapping[str, float]) -> str:
    shoulder = max(features["left_shoulder_elev"], features["right_shoulder_elev"])
    if (
        features["neck_flexion"] > 30
        or features["trunk_flexion"] > 60
        or shoulder > 60
        or features["shoulder_symmetry"] > 15
    ):
        return "HIGH"
    if (
        features["neck_flexion"] > 10
        or features["trunk_flexion"] > 20
        or shoulder > 30
        or features["shoulder_symmetry"] > 5
    ):
        return "MEDIUM"
    return "LOW"


def risk_breakdown(features: Mapping[str, float]) -> Dict[str, RiskBreakdown]:
    breakdown: Dict[str, RiskBreakdown] = {}
    for name, value in features.items():
        if name == "shoulder_symmetry":
            high, medium = 15.0, 5.0
        elif "shoulder" in name:
            high, medium = 60.0, 30.0
        elif name == "trunk_flexion":
            high, medium = 60.0, 20.0
        else:
            high, medium = 30.0, 10.0

        level = "HIGH" if value > high else "MEDIUM" if value > medium else "LOW"
        breakdown[name] = RiskBreakdown(level=level, color=RISK_COLORS_BGR[level])
    return breakdown


def mediapipe_landmarks_to_keypoints(landmarks: Iterable[object], width: int, height: int) -> list[list[float]]:
    keypoints = []
    for landmark in landmarks:
        keypoints.append(
            [
                float(landmark.x) * width,
                float(landmark.y) * height,
                float(getattr(landmark, "z", 0.0)),
                float(getattr(landmark, "visibility", getattr(landmark, "presence", 1.0))),
            ]
        )
    return keypoints


def unavailable_features_from_keypoints(
    keypoints: Sequence[Sequence[float]],
    index_map: Mapping[str, int] | None = None,
    min_visibility: float = 0.35,
) -> list[str]:
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17
    if kps.shape[1] < 4:
        return []

    unavailable = []
    for feature, landmarks in FEATURE_DEPENDENCIES.items():
        for landmark in landmarks:
            idx = index_map[landmark]
            if idx >= len(kps) or kps[idx][3] < min_visibility:
                unavailable.append(feature)
                break
    return unavailable
