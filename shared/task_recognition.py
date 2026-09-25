"""Shared Task Recognition Engine — used by both on-premise (MediaPipe) and cloud (YOLO) cores.

Features:
- ML model prediction (loads task_model_v2.pkl when available)
- Geometric posture gate (seated work detection)
- Gaussian probability scoring for each task type
- Temporal smoothing (confidence-weighted sliding window)
- Dwell-time tracking
- Feature history for temporal features
"""

from __future__ import annotations

import math
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

# Canonical MediaPipe landmark indices
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
NOSE = 0

# Feature names used by the v2 ML model
MODEL_FEATURES = [
    "neck_flexion", "trunk_flexion", "left_shoulder_elev", "right_shoulder_elev",
    "shoulder_symmetry", "alignment_deviation", "knee_angle", "forward_head_posture",
    "head_tilt_angle", "wrist_deviation_angle", "stance_stability", "weight_shift_offset",
    "elbow_flexion_angle", "upper_arm_angle_from_vertical",
    "hand_reach_ratio", "finger_spread_ratio", "stance_width_ratio",
    "movement_velocity", "wrist_movement_velocity",
]


def angle_between(p1, vertex, p2) -> float:
    """Compute angle at vertex between p1 and p2 (degrees)."""
    v1 = np.array(p1[:2], dtype=float) - np.array(vertex[:2], dtype=float)
    v2 = np.array(p2[:2], dtype=float) - np.array(vertex[:2], dtype=float)
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def midpoint(p1, p2):
    """Midpoint of two points (2D or 3D)."""
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2)


def dist_2d(p1, p2) -> float:
    """Euclidean distance in 2D."""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def extract_features_from_landmarks(keypoints, w: int, h: int) -> Dict[str, float]:
    """Extract ergonomic features from 33 MediaPipe/YOLO keypoints.

    Keypoints should be in normalized [x, y, z] or [x, y, z, visibility] format.
    Returns a dict of 19 feature values.
    """
    pts = np.array([[kp[0] * w, kp[1] * h] for kp in keypoints])
    l_shoulder, r_shoulder = pts[11], pts[12]
    l_elbow, r_elbow = pts[13], pts[14]
    l_wrist, r_wrist = pts[15], pts[16]
    l_hip, r_hip = pts[23], pts[24]
    l_knee, r_knee = pts[25], pts[26]
    l_ankle, r_ankle = pts[27], pts[28]

    mid_shoulder = (l_shoulder + r_shoulder) / 2
    mid_hip = (l_hip + r_hip) / 2
    body_scale = max(np.linalg.norm(mid_shoulder - mid_hip), 1.0)

    neck_vec = pts[0] - mid_shoulder
    neck_angle = abs(float(np.degrees(np.arctan2(neck_vec[0], neck_vec[1]))))
    trunk_vec = mid_shoulder - mid_hip
    trunk_angle = abs(float(np.degrees(np.arctan2(trunk_vec[0], trunk_vec[1]))))

    left_arm_angle = angle_between(l_shoulder, l_elbow, l_wrist)
    right_arm_angle = angle_between(r_shoulder, r_elbow, r_wrist)

    def upper_arm_vertical(shoulder, elbow):
        vec = elbow - shoulder
        return abs(float(np.degrees(np.arctan2(vec[0], vec[1]))))

    return {
        "neck_flexion": min(neck_angle, 90),
        "trunk_flexion": min(trunk_angle, 90),
        "left_shoulder_elev": abs(l_shoulder[1] - mid_shoulder[1]) / body_scale * 100,
        "right_shoulder_elev": abs(r_shoulder[1] - mid_shoulder[1]) / body_scale * 100,
        "shoulder_symmetry": abs(l_shoulder[1] - r_shoulder[1]) / body_scale * 100,
        "alignment_deviation": abs(mid_shoulder[0] - mid_hip[0]) / body_scale * 100,
        "knee_angle": (angle_between(l_hip, l_knee, l_ankle) + angle_between(r_hip, r_knee, r_ankle)) / 2,
        "forward_head_posture": abs((pts[3][0] + pts[4][0]) / 2 - mid_shoulder[0]) / body_scale * 100,
        "head_tilt_angle": min(abs(float(np.degrees(np.arctan2(pts[3][1] - pts[4][1], pts[3][0] - pts[4][0])))), 90),
        "wrist_deviation_angle": (
            abs(float(np.degrees(np.arctan2(l_wrist[1] - l_elbow[1], l_wrist[0] - l_elbow[0]))))
            + abs(float(np.degrees(np.arctan2(r_wrist[1] - r_elbow[1], r_wrist[0] - r_elbow[0]))))
        ) / 2,
        "stance_stability": abs(l_ankle[0] - r_ankle[0]) / body_scale * 100,
        "weight_shift_offset": abs(mid_hip[0] - w / 2) / w * 100,
        "elbow_flexion_angle": (left_arm_angle + right_arm_angle) / 2,
        "upper_arm_angle_from_vertical": (
            upper_arm_vertical(l_shoulder, l_elbow) + upper_arm_vertical(r_shoulder, r_elbow)
        ) / 2,
        "hand_reach_ratio": np.linalg.norm(l_wrist - mid_shoulder) / body_scale,
        "finger_spread_ratio": 0.0,
        "stance_width_ratio": abs(l_ankle[0] - r_ankle[0]) / (abs(l_hip[0] - r_hip[0]) + 1e-6),
        "movement_velocity": 0.0,
        "wrist_movement_velocity": 0.0,
    }


def classify_task(features: Dict[str, float]) -> str:
    """Classify task using geometric rules (ML model fallback)."""
    neck = features["neck_flexion"]
    trunk = features["trunk_flexion"]
    knee = features["knee_angle"]
    shoulder_elev = max(features["left_shoulder_elev"], features["right_shoulder_elev"])
    elbow = features["elbow_flexion_angle"]
    hand_reach = features.get("hand_reach_ratio", 1.0)
    stance = features.get("stance_width_ratio", 1.0)

    if knee < 90 and trunk > 25:
        return "Lifting/Carrying"
    elif knee < 100 and trunk > 35:
        return "Lifting/Carrying"
    if 80 < knee < 150 and hand_reach < 1.2 and stance < 1.5:
        return "Seated Work"
    elif knee > 140 and trunk < 15 and shoulder_elev < 5:
        return "Seated Work"
    if neck > 25 and trunk < 20 and knee > 130:
        return "Inspection"
    elif neck > 40 and elbow > 100:
        return "Inspection"
    if trunk < 10 and knee > 160:
        return "Neutral Standing"
    if knee > 110 and elbow < 130:
        return "Assembly Work"
    return "Assembly Work"


def classify_risk(features: Dict[str, float]) -> str:
    """Classify risk using ergonomic thresholds."""
    neck = features["neck_flexion"]
    trunk = features["trunk_flexion"]
    shoulder = features["shoulder_symmetry"]
    knee = features["knee_angle"]
    alignment = features["alignment_deviation"]

    score = 0
    if neck > 20: score += 1
    if neck > 40: score += 2
    if neck > 60: score += 3
    if trunk > 20: score += 1
    if trunk > 40: score += 2
    if trunk > 60: score += 3
    if shoulder > 10: score += 1
    if shoulder > 25: score += 2
    if knee < 90: score += 2
    if knee < 60: score += 3
    if alignment > 10: score += 1
    if alignment > 30: score += 2

    if score <= 2:
        return "LOW"
    elif score <= 5:
        return "MEDIUM"
    else:
        return "HIGH"


def _gauss(value: float, mean: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return math.exp(-0.5 * ((value - mean) / sigma) ** 2)


class TaskRecognitionEngine:
    """Full task recognition engine with ML model, geometric gate, and temporal smoothing.

    Shared between on-premise (MediaPipe) and cloud (YOLO) cores.
    """

    def __init__(self, model_path: Optional[str] = None, window_size: int = 10):
        self._current_task: str = "Unknown"
        self._confidence: float = 0.0
        self._reason: str = "Insufficient data"
        self._prev_kps: Optional[np.ndarray] = None
        self._window_size = max(1, window_size)
        self._window: deque = deque(maxlen=self._window_size)
        self._last_smoothed_task: str = "Unknown"
        self._task_start_time: float = time.time()
        self._feature_window: deque = deque(maxlen=10)

        # Model loading
        if model_path:
            self._model_path = Path(model_path)
        else:
            # Try to find the v2 model
            candidates = [
                Path(__file__).resolve().parents[1] / "models" / "task_model_v2.pkl",
                Path(__file__).resolve().parents[2] / "models" / "task_model_v2.pkl",
                Path(__file__).resolve().parents[3] / "models" / "task_model_v2.pkl",
            ]
            self._model_path = None
            for c in candidates:
                if c.exists():
                    self._model_path = c
                    break

        self._model_bundle: Optional[dict] = None
        self._model_tried: bool = False
        self._model_disabled: bool = False
        self._confidence_threshold: float = 0.6
        self._using_model: bool = False
        self._model_version: str = "unknown"

    def _get_model_bundle(self) -> Optional[dict]:
        if self._model_tried:
            return self._model_bundle
        self._model_tried = True
        if not self._model_path or not self._model_path.exists():
            return None
        try:
            import pickle
            with open(self._model_path, "rb") as f:
                bundle = pickle.load(f)
            if not isinstance(bundle, dict) or "model" not in bundle:
                return None
            self._model_bundle = bundle
            self._confidence_threshold = float(
                bundle.get("config", {}).get("confidence_threshold", 0.6))
            n_features = len(bundle.get("feature_columns", []))
            self._model_version = bundle.get("version", "v2" if n_features <= 20 else "v3")
        except Exception:
            self._model_bundle = None
        return self._model_bundle

    def _predict_with_model(self, features: Dict[str, float]) -> Optional[tuple]:
        if self._model_disabled:
            return None
        bundle = self._get_model_bundle()
        if bundle is None:
            return None
        try:
            self._feature_window.append(dict(features))

            cols = bundle.get("feature_columns") or bundle.get("feature_cols", [])
            if not cols:
                return None
            row = [features.get(c, 0.0) for c in cols]
            model = bundle["model"]
            proba = model.predict_proba([row])[0]
            best = int(np.argmax(proba))
            conf = float(proba[best])

            classes = getattr(model, "classes_", None)
            if classes is None:
                classes = bundle.get("labels", [])
            classes = list(classes)
            if not classes or best >= len(classes):
                return None

            le = bundle.get("label_encoder")
            if le is not None and hasattr(le, "inverse_transform"):
                try:
                    task = str(le.inverse_transform([best])[0])
                except (ValueError, IndexError):
                    task = str(classes[best])
            else:
                task = str(classes[best])

            threshold = float(bundle.get("config", {}).get("confidence_threshold", 0.6))
            if conf < threshold:
                return None
            return task, conf
        except Exception:
            return None

    def detect(
        self,
        keypoints: Sequence[Sequence[float]],
        features: Dict[str, float],
        image_width: int = 640,
        image_height: int = 480,
    ) -> Dict:
        """Detect task from keypoints and features.

        Args:
            keypoints: 33 keypoints in [x, y, z] or [x, y, z, visibility] format (normalized 0-1)
            features: Pre-computed feature dict (if available, otherwise computed from keypoints)
            image_width: Frame width for feature extraction
            image_height: Frame height for feature extraction

        Returns:
            Dict with task, confidence, reason, task_duration_seconds
        """
        # If features not provided, extract from keypoints
        if not features or len(features) < 5:
            features = extract_features_from_landmarks(keypoints, image_width, image_height)

        kps = (
            np.asarray(keypoints, dtype=float)
            if keypoints is not None and len(keypoints) > 0
            else np.zeros((33, 4))
        )

        # Try ML model first
        model_pred = self._predict_with_model(features)
        if model_pred is not None:
            self._using_model = True
            model_task, model_conf = model_pred
            return self._finalize(model_task, round(model_conf * 100.0, 1),
                                  f"Trained classifier ({self._model_version})", kps)

        # Geometric posture gate
        if len(kps) >= 29:
            lsh = kps[LEFT_SHOULDER]
            rsh = kps[RIGHT_SHOULDER]
            lhip = kps[LEFT_HIP]
            rhip = kps[RIGHT_HIP]
            lknee = kps[LEFT_KNEE]
            rknee = kps[RIGHT_KNEE]
            lankle = kps[LEFT_ANKLE]
            rankle = kps[RIGHT_ANKLE]

            mid_shoulder = midpoint(lsh, rsh)
            mid_hip = midpoint(lhip, rhip)
            mid_knee = midpoint(lknee, rknee)
            mid_ankle = midpoint(lankle, rankle)
            torso_height = dist_2d(mid_shoulder, mid_hip)

            if torso_height > 1e-6:
                thigh_ratio = abs(mid_hip[1] - mid_knee[1]) / torso_height
                leg_ratio = dist_2d(mid_hip, mid_ankle) / torso_height

                def _vis(p):
                    return p[3] if len(p) > 3 else 1.0

                legs_visible = min(_vis(lhip), _vis(rhip), _vis(lknee), _vis(rknee),
                                   _vis(lankle), _vis(rankle)) > 0.5
                knee_angle = features.get("knee_angle", 180)
                if legs_visible and 60.0 < knee_angle < 140.0 and thigh_ratio < 0.45 and leg_ratio < 1.2:
                    self._using_model = False
                    return self._finalize(
                        "Seated Work", 95.0,
                        "Knees bent - seated posture detected", kps, force=True)

        # Gaussian scorer fallback
        self._using_model = False
        neck = features.get("neck_flexion", 0.0)
        trunk = features.get("trunk_flexion", 0.0)
        knee = features.get("knee_angle", 180)
        shoulder_elev = max(features.get("left_shoulder_elev", 0), features.get("right_shoulder_elev", 0))
        movement_velocity = features.get("movement_velocity", 0.0)

        scores: Dict[str, float] = {}

        # Neutral Standing
        ns = 0.0
        ns += _gauss(trunk, 0, 8)
        ns += _gauss(neck, 0, 10)
        ns += _gauss(knee, 175, 10)
        ns -= _gauss(movement_velocity, 110, 55)
        scores["Neutral Standing"] = max(0.0, ns) / 3.0

        # Seated Work
        sw = 0.0
        sw += _gauss(knee, 100, 22)
        sw += _gauss(trunk, 5, 10)
        scores["Seated Work"] = max(0.0, sw) / 2.0

        # Assembly Work
        aw = 0.0
        aw += _gauss(trunk, 0, 12)
        aw += _gauss(knee, 140, 20)
        scores["Assembly Work"] = max(0.0, aw) / 2.0

        # Lifting/Carrying
        lf = 0.0
        lf += _gauss(trunk, 30, 15)
        lf += max(0.0, _gauss(knee, 150, 20))
        scores["Lifting/Carrying"] = max(0.0, lf) / 2.0

        # Inspection
        ip = 0.0
        ip += _gauss(neck, 25, 8)
        ip += _gauss(trunk, 0, 10)
        scores["Inspection"] = max(0.0, ip) / 2.0

        best_task = max(scores, key=scores.get)
        best_score = scores[best_task]

        if best_score < 0.3:
            best_task = "Unknown"
            best_score = max(best_score, 0.2)

        return self._finalize(best_task, round(best_score * 100, 1),
                              "Geometric analysis", kps)

    def _finalize(self, task: str, confidence: float, reason: str,
                  kps: np.ndarray, force: bool = False) -> Dict:
        """Apply temporal smoothing and dwell tracking."""
        self._current_task = task
        self._confidence = confidence
        self._reason = reason
        self._prev_kps = kps.copy() if kps is not None else None

        self._window.append((self._current_task, self._confidence))

        if len(self._window) >= 2 and not force:
            weights: Dict[str, float] = {}
            for t, c in self._window:
                weights[t] = weights.get(t, 0.0) + c
            smoothed_task = max(weights, key=weights.get)
            smoothed_conf = weights[smoothed_task] / len(self._window)

            if smoothed_task != self._current_task:
                second_best = max((t for t, c in weights.items() if t != smoothed_task),
                                  key=lambda t: weights[t], default=None)
                margin = weights[smoothed_task] - (weights.get(second_best, 0) if second_best else 0)
                if margin > 5.0:
                    self._current_task = smoothed_task
                    self._confidence = round(smoothed_conf, 1)

        now = time.time()
        if self._current_task != self._last_smoothed_task:
            self._task_start_time = now
            self._last_smoothed_task = self._current_task
        task_duration = now - self._task_start_time

        return {
            "task": self._current_task,
            "confidence": self._confidence,
            "reason": self._reason,
            "task_duration_seconds": round(task_duration, 1),
        }

    def reset(self):
        self._current_task = "Unknown"
        self._confidence = 0.0
        self._reason = "Insufficient data"
        self._prev_kps = None
        self._window.clear()
        self._feature_window.clear()
        self._last_smoothed_task = "Unknown"
        self._task_start_time = time.time()
