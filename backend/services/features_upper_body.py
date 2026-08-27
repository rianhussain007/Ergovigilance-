"""Upper-body feature extraction for partial camera views.

When the camera only shows the upper body (common in factory deployments),
standard feature extraction fails because hips, knees, and ankles are not
visible. This module provides fallback feature computation using only
available keypoints (head, shoulders, elbows, wrists).

Usage:
    from backend.services.features_upper_body import extract_upper_body_features
    features, unavailable = extract_upper_body_features(keypoints)
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np

# MediaPipe 33-keypoint indices
MEDIAPIPE_33 = {
    "nose": 0, "left_ear": 2, "right_ear": 5,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}


def _point(kps: np.ndarray, name: str) -> np.ndarray | None:
    """Get a 2D point from keypoints, or None if not visible."""
    idx = MEDIAPIPE_33.get(name)
    if idx is None or idx >= len(kps):
        return None
    pt = kps[idx]
    # Check visibility (index 3)
    if len(pt) > 3 and pt[3] < 0.3:
        return None
    if not np.isfinite(pt[0]) or not np.isfinite(pt[1]):
        return None
    return np.array(pt[:2], dtype=float)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at point b between a-b and c-b (degrees)."""
    v1 = a - b
    v2 = c - b
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-9:
        return float("nan")
    cos_angle = np.dot(v1, v2) / denom
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two points."""
    return float(np.linalg.norm(a - b))


def extract_upper_body_features(
    keypoints: Sequence[Sequence[float]],
) -> Tuple[Dict[str, float], List[str]]:
    """Extract features from upper-body keypoints only.
    
    Returns:
        (features, unavailable_features) - features dict and list of
        features that couldn't be computed.
    """
    kps = np.asarray(keypoints, dtype=float)
    
    # Get available points
    left_ear = _point(kps, "left_ear")
    right_ear = _point(kps, "right_ear")
    left_shoulder = _point(kps, "left_shoulder")
    right_shoulder = _point(kps, "right_shoulder")
    left_elbow = _point(kps, "left_elbow")
    right_elbow = _point(kps, "right_elbow")
    left_wrist = _point(kps, "left_wrist")
    right_wrist = _point(kps, "right_wrist")
    
    features = {}
    unavailable = []
    
    # ── Compute available features ──────────────────────────────────
    
    # 1. Neck flexion (head tilt forward)
    if left_ear is not None and right_ear is not None and left_shoulder is not None and right_shoulder is not None:
        ear = (left_ear + right_ear) / 2
        neck = (left_shoulder + right_shoulder) / 2
        # Vertical reference
        vertical_up = np.array([neck[0], neck[1] - 100])
        angle = _angle(vertical_up, neck, ear)
        features["neck_flexion"] = abs(180.0 - angle) if np.isfinite(angle) else 0.0
    else:
        unavailable.append("neck_flexion")
        features["neck_flexion"] = 0.0
    
    # 2. Shoulder elevation (arm raise angle)
    if left_shoulder is not None and left_elbow is not None:
        vertical_down = np.array([left_shoulder[0], left_shoulder[1] + 100])
        angle = _angle(vertical_down, left_shoulder, left_elbow)
        features["left_shoulder_elev"] = abs(180.0 - angle) if np.isfinite(angle) else 0.0
    else:
        unavailable.append("left_shoulder_elev")
        features["left_shoulder_elev"] = 0.0
    
    if right_shoulder is not None and right_elbow is not None:
        vertical_down = np.array([right_shoulder[0], right_shoulder[1] + 100])
        angle = _angle(vertical_down, right_shoulder, right_elbow)
        features["right_shoulder_elev"] = abs(180.0 - angle) if np.isfinite(angle) else 0.0
    else:
        unavailable.append("right_shoulder_elev")
        features["right_shoulder_elev"] = 0.0
    
    # 3. Shoulder symmetry (height difference)
    if left_shoulder is not None and right_shoulder is not None:
        shoulder_width = _distance(left_shoulder, right_shoulder)
        height_diff = abs(left_shoulder[1] - right_shoulder[1])
        features["shoulder_symmetry"] = (height_diff / max(shoulder_width, 1.0)) * 100.0
    else:
        unavailable.append("shoulder_symmetry")
        features["shoulder_symmetry"] = 0.0
    
    # 4. Alignment deviation (head offset from center)
    if left_ear is not None and right_ear is not None and left_shoulder is not None and right_shoulder is not None:
        ear = (left_ear + right_ear) / 2
        neck = (left_shoulder + right_shoulder) / 2
        shoulder_width = _distance(left_shoulder, right_shoulder)
        horizontal_offset = abs(ear[0] - neck[0])
        features["alignment_deviation"] = (horizontal_offset / max(shoulder_width, 1.0)) * 100.0
    else:
        unavailable.append("alignment_deviation")
        features["alignment_deviation"] = 0.0
    
    # 5. Forward head posture (head protrusion angle)
    if left_ear is not None and right_ear is not None and left_shoulder is not None and right_shoulder is not None:
        ear = (left_ear + right_ear) / 2
        neck = (left_shoulder + right_shoulder) / 2
        vertical_up = np.array([neck[0], neck[1] - 100])
        angle = _angle(vertical_up, neck, ear)
        features["forward_head_posture"] = abs(180.0 - angle) if np.isfinite(angle) else 0.0
    else:
        unavailable.append("forward_head_posture")
        features["forward_head_posture"] = 0.0
    
    # 6. Head tilt angle (lateral tilt)
    if left_ear is not None and right_ear is not None and left_shoulder is not None and right_shoulder is not None:
        ear_vec = right_ear - left_ear
        shoulder_vec = right_shoulder - left_shoulder
        ear_len = np.linalg.norm(ear_vec)
        shoulder_len = np.linalg.norm(shoulder_vec)
        if ear_len > 0 and shoulder_len > 0:
            cos_angle = np.dot(ear_vec, shoulder_vec) / (ear_len * shoulder_len)
            angle = np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))
            features["head_tilt_angle"] = abs(90.0 - angle) if np.isfinite(angle) else 0.0
        else:
            features["head_tilt_angle"] = 0.0
    else:
        unavailable.append("head_tilt_angle")
        features["head_tilt_angle"] = 0.0
    
    # 7. Elbow flexion angle (arm bend)
    if left_shoulder is not None and left_elbow is not None and left_wrist is not None:
        angle = _angle(left_shoulder, left_elbow, left_wrist)
        features["elbow_flexion_angle"] = angle if np.isfinite(angle) else 0.0
    elif right_shoulder is not None and right_elbow is not None and right_wrist is not None:
        angle = _angle(right_shoulder, right_elbow, right_wrist)
        features["elbow_flexion_angle"] = angle if np.isfinite(angle) else 0.0
    else:
        unavailable.append("elbow_flexion_angle")
        features["elbow_flexion_angle"] = 0.0
    
    # 8. Wrist height ratio (relative to shoulders)
    if left_shoulder is not None and right_shoulder is not None and left_wrist is not None and right_wrist is not None:
        shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
        wrist_y = (left_wrist[1] + right_wrist[1]) / 2
        shoulder_width = _distance(left_shoulder, right_shoulder)
        features["wrist_height_ratio"] = (wrist_y - shoulder_y) / max(shoulder_width, 1.0)
    else:
        unavailable.append("wrist_height_ratio")
        features["wrist_height_ratio"] = 0.0
    
    # 9. Arm extension ratio (how extended are the arms)
    if left_shoulder is not None and left_elbow is not None and left_wrist is not None:
        arm_len = _distance(left_shoulder, left_elbow) + _distance(left_elbow, left_wrist)
        straight_len = _distance(left_shoulder, left_wrist)
        features["arm_extension_ratio"] = straight_len / max(arm_len, 1.0)
    elif right_shoulder is not None and right_elbow is not None and right_wrist is not None:
        arm_len = _distance(right_shoulder, right_elbow) + _distance(right_elbow, right_wrist)
        straight_len = _distance(right_shoulder, right_wrist)
        features["arm_extension_ratio"] = straight_len / max(arm_len, 1.0)
    else:
        unavailable.append("arm_extension_ratio")
        features["arm_extension_ratio"] = 0.0
    
    # 10. Hand distance from body (reaching indicator)
    if left_shoulder is not None and right_shoulder is not None and left_wrist is not None:
        neck = (left_shoulder + right_shoulder) / 2
        shoulder_width = _distance(left_shoulder, right_shoulder)
        hand_dist = _distance(neck, left_wrist)
        features["hand_distance_ratio"] = hand_dist / max(shoulder_width, 1.0)
    else:
        unavailable.append("hand_distance_ratio")
        features["hand_distance_ratio"] = 0.0
    
    # Movement velocity (placeholder - needs temporal data)
    features["movement_velocity"] = 0.0
    features["wrist_movement_velocity"] = 0.0
    
    return features, unavailable


def is_upper_body_only(keypoints: Sequence[Sequence[float]]) -> bool:
    """Check if the camera only shows upper body (lower body not visible)."""
    kps = np.asarray(keypoints, dtype=float)
    
    # Check if hips and knees are visible
    hip_left = _point(kps, "left_hip")
    hip_right = _point(kps, "right_hip")
    knee_left = _point(kps, "left_knee")
    knee_right = _point(kps, "right_knee")
    
    lower_body_visible = (hip_left is not None and hip_right is not None and 
                         knee_left is not None and knee_right is not None)
    
    return not lower_body_visible
