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
    "knee_angle",
    "elbow_flexion_angle",
    "upper_arm_angle_from_vertical",
]

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

FEATURE_THRESHOLDS = {
    "neck_flexion": "LOW <= 10 deg, MEDIUM 10-30 deg, HIGH > 30 deg",
    "trunk_flexion": "LOW <= 20 deg, MEDIUM 20-60 deg, HIGH > 60 deg",
    "left_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "right_shoulder_elev": "LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg",
    "shoulder_symmetry": "LOW <= 5%, MEDIUM 5-15%, HIGH > 15%",
    "alignment_deviation": "Lower is better; large horizontal ear-to-hip offset suggests alignment risk",
    "knee_angle": "HIGH < 100 deg, MEDIUM 100-150 deg, LOW >= 150 deg",
    "elbow_flexion_angle": "LOW >= 90 deg, MEDIUM 45-90 deg, HIGH < 45 deg",
    "upper_arm_angle_from_vertical": "LOW <= 20 deg, MEDIUM 20-45 deg, HIGH > 45 deg",
}

FEATURE_DEPENDENCIES = {
    "neck_flexion": ["left_ear", "right_ear", "left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "trunk_flexion": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "left_shoulder_elev": ["left_shoulder", "left_elbow"],
    "right_shoulder_elev": ["right_shoulder", "right_elbow"],
    "shoulder_symmetry": ["left_shoulder", "right_shoulder"],
    "alignment_deviation": ["left_ear", "right_ear", "left_hip", "right_hip"],
    "knee_angle": ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    "elbow_flexion_angle": ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist"],
    "upper_arm_angle_from_vertical": ["left_shoulder", "right_shoulder", "left_wrist", "right_wrist"],
}


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
    "left_wrist": 9,
    "right_wrist": 10,
    "left_hip": 11,
    "right_hip": 12,
    "left_knee": 13,
    "right_knee": 14,
    "left_ankle": 15,
    "right_ankle": 16,
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
) -> tuple[Dict[str, float], list[str], list[str]]:
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17

    unavailable = unavailable_features_from_keypoints(keypoints, index_map)

    _ANGLE_SENSITIVE_VIS_OVERRIDE = 0.40
    _ANGLE_SENSITIVE_FEATURES = {
        "left_shoulder_elev", "right_shoulder_elev",
        "elbow_flexion_angle", "upper_arm_angle_from_vertical",
    }
    for feature in _ANGLE_SENSITIVE_FEATURES:
        if feature not in unavailable:
            dependencies = FEATURE_DEPENDENCIES[feature]
            for landmark in dependencies:
                idx = index_map[landmark]
                if len(kps) > idx and kps.shape[1] >= 4 and kps[idx][3] < _ANGLE_SENSITIVE_VIS_OVERRIDE:
                    unavailable.append(feature)
                    break

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

    left_knee_pt = _point(kps, index_map, "left_knee")
    right_knee_pt = _point(kps, index_map, "right_knee")
    left_ankle_pt = _point(kps, index_map, "left_ankle")
    right_ankle_pt = _point(kps, index_map, "right_ankle")
    left_knee_angle = angle_between_three_points(left_hip, left_knee_pt, left_ankle_pt)
    right_knee_angle = angle_between_three_points(right_hip, right_knee_pt, right_ankle_pt)
    knee_angle = (left_knee_angle + right_knee_angle) / 2.0

    left_wrist_pt = _point(kps, index_map, "left_wrist")
    right_wrist_pt = _point(kps, index_map, "right_wrist")
    left_elbow_angle = angle_between_three_points(left_shoulder, left_elbow, left_wrist_pt)
    right_elbow_angle = angle_between_three_points(right_shoulder, right_elbow, right_wrist_pt)
    elbow_flexion_angle = (left_elbow_angle + right_elbow_angle) / 2.0

    vertical_up_left = np.array([left_shoulder[0], left_shoulder[1] - torso_len])
    vertical_up_right = np.array([right_shoulder[0], right_shoulder[1] - torso_len])
    left_upper_arm = angle_between_three_points(vertical_up_left, left_shoulder, left_wrist_pt)
    right_upper_arm = angle_between_three_points(vertical_up_right, right_shoulder, right_wrist_pt)
    upper_arm_angle_from_vertical = (left_upper_arm + right_upper_arm) / 2.0

    raw_alignment_deviation = alignment_deviation
    if "alignment_deviation" in unavailable:
        raw_alignment_deviation = float("nan")

    raw_features = {
        "neck_flexion": neck_flexion,
        "trunk_flexion": trunk_flexion,
        "left_shoulder_elev": left_shoulder_elev,
        "right_shoulder_elev": right_shoulder_elev,
        "shoulder_symmetry": shoulder_symmetry,
        "alignment_deviation": raw_alignment_deviation,
        "knee_angle": knee_angle,
        "elbow_flexion_angle": elbow_flexion_angle,
        "upper_arm_angle_from_vertical": upper_arm_angle_from_vertical,
    }

    features = {}
    for name in FEATURE_COLUMNS:
        val = raw_features[name]
        if name in unavailable:
            features[name] = float("nan")
        else:
            features[name] = round(float(np.nan_to_num(val, nan=0.0)), 4)

    approximate_features: list[str] = []

    if "neck_flexion" in unavailable:
        if np.isfinite(ear).all() and np.isfinite(neck).all():
            fake_hip = np.array([neck[0], neck[1] + torso_len])
            raw_approx = angle_between_three_points(ear, neck, fake_hip)
            approx_val = abs(180.0 - raw_approx)
            if approx_val == approx_val:
                features["neck_flexion"] = round(float(approx_val), 4)
                unavailable.remove("neck_flexion")
                approximate_features.append("neck_flexion")

    if "alignment_deviation" in unavailable:
        if np.isfinite(ear).all() and np.isfinite(neck).all():
            approx_val = abs(ear[0] - neck[0]) / torso_len * 100.0
            if approx_val == approx_val:
                features["alignment_deviation"] = round(float(approx_val), 4)
                unavailable.remove("alignment_deviation")
                approximate_features.append("alignment_deviation")

    return features, unavailable, approximate_features


def risk_from_features(
    features: Mapping[str, float],
    unavailable_features: list[str] | None = None,
) -> str:
    unavailable = set(unavailable_features or ())

    def _get(name: str, default: float, unknown_val: float) -> float:
        if name in unavailable:
            return unknown_val
        val = features.get(name, default)
        if val != val:
            return unknown_val
        return val

    shoulder = max(
        _get("left_shoulder_elev", 0.0, 30.0),
        _get("right_shoulder_elev", 0.0, 30.0),
    )
    knee = _get("knee_angle", 180.0, 140.0)
    neck = _get("neck_flexion", 0.0, 10.0)
    trunk = _get("trunk_flexion", 0.0, 20.0)
    sym = _get("shoulder_symmetry", 0.0, 5.0)

    if (
        neck > 30
        or trunk > 60
        or shoulder > 60
        or sym > 15
        or knee < 100
    ):
        return "HIGH"
    if (
        neck > 10
        or trunk > 20
        or shoulder > 30
        or sym > 5
        or knee < 150
    ):
        return "MEDIUM"

    nan_features = {name for name in FEATURE_COLUMNS if features.get(name, 0.0) != features.get(name, 0.0)}
    lower_body_missing = (unavailable | nan_features) & {"trunk_flexion", "knee_angle", "neck_flexion"}
    if lower_body_missing:
        return "MEDIUM"

    return "LOW"


def risk_breakdown(features: Mapping[str, float]) -> Dict[str, RiskBreakdown]:
    breakdown: Dict[str, RiskBreakdown] = {}
    for name, value in features.items():
        if value != value:
            breakdown[name] = RiskBreakdown(level="UNKNOWN", color=(128, 128, 128))
            continue

        if name == "shoulder_symmetry":
            high, medium = 15.0, 5.0
        elif "shoulder" in name:
            high, medium = 60.0, 30.0
        elif name == "trunk_flexion":
            high, medium = 60.0, 20.0
        elif name == "knee_angle":
            high, medium = 100.0, 150.0
        elif name == "alignment_deviation":
            high, medium = 50.0, 20.0
        else:
            high, medium = 30.0, 10.0

        if name == "knee_angle":
            level = "HIGH" if value < high else "MEDIUM" if value < medium else "LOW"
        else:
            level = "HIGH" if value > high else "MEDIUM" if value > medium else "LOW"
        breakdown[name] = RiskBreakdown(level=level, color=RISK_COLORS_BGR[level])
    return breakdown


def _band(value: float, thresholds: list[float]) -> int:
    for i, t in enumerate(thresholds):
        if value < t:
            return i + 1
    return len(thresholds) + 1


def compute_rula_informed_score(
    features: Mapping[str, float],
    unavailable_features: list[str] | None = None
) -> Dict[str, int | bool]:
    unavailable = set(unavailable_features or [])

    neck = features.get("neck_flexion", 0.0)
    trunk = features.get("trunk_flexion", 0.0)

    knee = features.get("knee_angle", 90.0) if "knee_angle" in unavailable else features.get("knee_angle", 180.0)
    knee_val = knee if (knee == knee) else 90.0

    is_partial = "knee_angle" in unavailable or (knee != knee)

    shoulder_l = features.get("left_shoulder_elev", 0.0)
    shoulder_r = features.get("right_shoulder_elev", 0.0)
    shoulder = max(shoulder_l, shoulder_r)
    elbow_l = features.get("elbow_flexion_angle", 90.0)
    elbow_r = features.get("elbow_flexion_angle", 90.0)
    upper_arm = features.get("upper_arm_angle_from_vertical", 0.0)

    neck_b = _band(neck, [10, 20, 30])
    trunk_b = _band(trunk, [20, 40, 60])
    legs_b = 1 if knee_val >= 150 else 2 if knee_val >= 100 else 3
    score_a_table = [
        [1, 2, 3, 4],
        [2, 3, 4, 5],
        [3, 4, 5, 6],
    ]
    row_a = min(trunk_b - 1, 2)
    col_a = min(neck_b - 1, 3)
    table_a = score_a_table[row_a][col_a] + (legs_b - 1)

    arm_b = _band(upper_arm, [20, 45, 90])
    elbow_b_l = _band(elbow_l, [45, 90, 150])
    elbow_b_r = _band(elbow_r, [45, 90, 150])
    elbow_b = max(elbow_b_l, elbow_b_r)
    score_b_table = [
        [1, 2, 3, 4],
        [2, 3, 4, 5],
        [3, 4, 5, 6],
    ]
    row_b = min(arm_b - 1, 2)
    col_b = min(elbow_b - 1, 3)
    table_b = score_b_table[row_b][col_b]

    combined_a = max(table_a, 1)
    combined_b = max(table_b, 1)
    score_c_table = [
        [1, 2, 3, 4, 5, 6],
        [2, 3, 4, 5, 6, 7],
        [3, 4, 5, 6, 7, 7],
    ]
    row_c = min(combined_a - 1, 2)
    col_c = min(combined_b - 1, 5)
    final_score = score_c_table[row_c][col_c]

    return {
        "rula_informed_score": final_score,
        "is_partial_score": is_partial
    }


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

    unavailable = []
    for feature, landmarks in FEATURE_DEPENDENCIES.items():
        for landmark in landmarks:
            idx = index_map[landmark]
            if idx >= len(kps):
                unavailable.append(feature)
                break
            if kps.shape[1] >= 4 and kps[idx][3] < min_visibility:
                unavailable.append(feature)
                break
    return unavailable


def lower_body_confidence(keypoints: Sequence[Sequence[float]], index_map: Mapping[str, int] | None = None) -> float:
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17
    if kps.shape[1] < 4:
        return 0.0

    lower_indices = [index_map[name] for name in ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]]
    vis_vals = [kps[i][3] for i in lower_indices if i < len(kps)]
    return float(np.mean(vis_vals)) * 100 if vis_vals else 0.0
