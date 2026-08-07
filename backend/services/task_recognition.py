from __future__ import annotations

import math
import os
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

# Canonical definitions live in backend.core.utils.
# Re-exported here for backward compatibility.
from backend.core.utils import (  # noqa: F401
    angle_between as _angle_between,
    midpoint as _midpoint,
    dist_2d as _dist_2d,
)

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


class TaskRecognition:
    """Task/activity recognition for the live pipeline.

    Model-primary with Gaussian fallback: when a trained classifier
    (models/task_model_v2.pkl, loaded lazily) is available and its top
    prediction exceeds the confidence threshold (default 0.6), the model
    decides; otherwise the deterministic Gaussian scorer runs. A missing
    or unreadable model file never raises — the Gaussian covers it.
    """

    DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "task_model_v2.pkl"

    def __init__(self, window_size: int = 10,
                 model_path: Optional[str] = None) -> None:
        self._current_task: str = "Unknown"
        self._confidence: float = 0.0
        self._reason: str = "Insufficient data"
        self._prev_kps: np.ndarray | None = None
        self._window_size = max(1, window_size)
        self._window: deque[tuple[str, float]] = deque(maxlen=self._window_size)
        self._last_smoothed_task: str = "Unknown"
        self._task_start_time: float = time.time()

        env_path = os.environ.get("ERGOVIGILANCE_TASK_MODEL")
        self._model_path = Path(model_path) if model_path else (
            Path(env_path) if env_path else self.DEFAULT_MODEL_PATH)
        self._model_bundle: dict | None = None
        self._model_tried: bool = False
        self._confidence_threshold: float = 0.6
        self._using_model: bool = False

    def get_current_task(self) -> str:
        return self._current_task

    def get_confidence(self) -> float:
        return self._confidence

    def get_reason(self) -> str:
        return self._reason

    @property
    def using_model(self) -> bool:
        """True when the last prediction came from the trained classifier."""
        return self._using_model

    def _get_model_bundle(self) -> dict | None:
        """Load the trained task model once; never raise on absence/corruption."""
        if self._model_tried:
            return self._model_bundle
        self._model_tried = True
        try:
            import joblib  # optional runtime dep — degrades to Gaussian if absent
            if not self._model_path.exists():
                return None
            bundle = joblib.load(self._model_path)
            if not isinstance(bundle, dict) or "model" not in bundle:
                return None
            self._model_bundle = bundle
            self._confidence_threshold = float(
                bundle.get("config", {}).get("confidence_threshold", 0.6))
        except Exception:
            self._model_bundle = None
        return self._model_bundle

    def _predict_with_model(self, features: Dict[str, float]) -> tuple[str, float] | None:
        """Return (task, confidence) if the model is confident, else None."""
        bundle = self._get_model_bundle()
        if bundle is None:
            return None
        try:
            cols = bundle["feature_columns"]
            row = [features.get(c, 0.0) for c in cols]
            proba = bundle["model"].predict_proba([row])[0]
            best = int(np.argmax(proba))
            conf = float(proba[best])
            task = str(bundle["labels"][best])
        except Exception:
            return None
        if conf < self._confidence_threshold:
            return None
        return task, conf

    def reset(self) -> None:
        self._current_task = "Unknown"
        self._confidence = 0.0
        self._reason = "Insufficient data"
        self._prev_kps = None
        self._window.clear()
        self._last_smoothed_task = "Unknown"
        self._task_start_time = time.time()

    def detect_task(
        self,
        keypoints: Sequence[Sequence[float]],
        features: Dict[str, float],
    ) -> Dict:
        kps = np.asarray(keypoints, dtype=float)

        neck = features.get("neck_flexion", 0.0)
        trunk = features.get("trunk_flexion", 0.0)
        shoulder_l = features.get("left_shoulder_elev", 0.0)
        shoulder_r = features.get("right_shoulder_elev", 0.0)
        shoulder_sym = features.get("shoulder_symmetry", 0.0)
        knee = features.get("knee_angle", 0.0)
        alignment = features.get("alignment_deviation", 0.0)

        lsh = kps[LEFT_SHOULDER]
        rsh = kps[RIGHT_SHOULDER]
        lel = kps[LEFT_ELBOW]
        rel = kps[RIGHT_ELBOW]
        lwr = kps[LEFT_WRIST]
        rwr = kps[RIGHT_WRIST]
        lhip = kps[LEFT_HIP]
        rhip = kps[RIGHT_HIP]
        lknee = kps[LEFT_KNEE]
        rknee = kps[RIGHT_KNEE]
        lankle = kps[LEFT_ANKLE]
        rankle = kps[RIGHT_ANKLE]

        mid_shoulder = _midpoint(lsh, rsh)
        mid_hip = _midpoint(lhip, rhip)
        torso_height = _dist_2d(mid_shoulder, mid_hip)

        if torso_height < 1e-6:
            self._current_task = "Unknown"
            self._confidence = 0.0
            self._reason = "Degenerate keypoints - no person detected"
            self._using_model = False
            return {
                "task": "Unknown",
                "confidence": 0.0,
                "reason": "Degenerate keypoints - no person detected",
            }

        # ── Model-primary path: confident trained classifier wins ──
        model_pred = self._predict_with_model(features)
        if model_pred is not None:
            self._using_model = True
            model_task, model_conf = model_pred
            return self._finalize(model_task, round(model_conf * 100.0, 1),
                                  "Trained task classifier (v2)", kps)
        self._using_model = False

        l_elbow_angle = _angle_between(lsh, lel, lwr)
        r_elbow_angle = _angle_between(rsh, rel, rwr)
        avg_elbow = (l_elbow_angle + r_elbow_angle) / 2.0

        l_wrist_rel_y = lwr[1] - lsh[1]
        r_wrist_rel_y = rwr[1] - rsh[1]
        avg_wrist_rel_y = (l_wrist_rel_y + r_wrist_rel_y) / 2.0
        wrist_height_ratio = avg_wrist_rel_y / torso_height if torso_height > 0 else 0.0

        l_wrist_torso_dist = _dist_2d(lwr, mid_shoulder)
        r_wrist_torso_dist = _dist_2d(rwr, mid_shoulder)
        avg_hand_dist = (l_wrist_torso_dist + r_wrist_torso_dist) / 2.0

        l_arm_len = _dist_2d(lsh, lel) + _dist_2d(lel, lwr)
        r_arm_len = _dist_2d(rsh, rel) + _dist_2d(rel, rwr)
        avg_arm_len = (l_arm_len + r_arm_len) / 2.0
        l_extension = _dist_2d(lsh, lwr) / l_arm_len if l_arm_len > 0 else 0.5
        r_extension = _dist_2d(rsh, rwr) / r_arm_len if r_arm_len > 0 else 0.5
        avg_extension = (l_extension + r_extension) / 2.0

        scores: Dict[str, float] = {}
        reasons: Dict[str, List[str]] = {}

        # --- Neutral Standing ---
        ns = 0.0
        ns_reasons: List[str] = []
        ns += _gauss(trunk, 0, 8)
        ns += _gauss(neck, 0, 10)
        ns += _gauss(avg_elbow, 170, 15)
        l_wrist_side = 0.0 if lsh[0] <= lwr[0] <= rsh[0] else 1.0
        r_wrist_side = 0.0 if lsh[0] <= rwr[0] <= rsh[0] else 1.0
        wrists_at_sides = (l_wrist_side + r_wrist_side) / 2.0
        ns += wrists_at_sides
        ns_score = ns / 4.0
        scores["Neutral Standing"] = ns_score
        if trunk < 12:
            ns_reasons.append("Minimal trunk flexion")
        if avg_elbow > 155:
            ns_reasons.append("Arms extended naturally")
        if avg_wrist_rel_y > 10:
            ns_reasons.append("Hands near hip level")
        if wrists_at_sides > 0.7:
            ns_reasons.append("Hands at sides")
        reasons["Neutral Standing"] = ns_reasons

        # --- Assembly Work ---
        aw = 0.0
        aw_reasons: List[str] = []
        aw += _gauss(trunk, 0, 12)
        aw += _gauss(wrist_height_ratio, 0.2, 0.25)
        aw += _gauss(avg_elbow, 110, 18)
        aw_score = aw / 3.0
        scores["Assembly Work"] = aw_score
        if -0.3 < wrist_height_ratio < 0.6:
            aw_reasons.append("Hands near chest level")
        if trunk < 15:
            aw_reasons.append("Upright trunk")
        if 60 < avg_elbow < 150:
            aw_reasons.append("Moderate arm flexion")
        reasons["Assembly Work"] = aw_reasons

        # --- Reaching ---
        rw = 0.0
        rw_reasons: List[str] = []
        rw += _gauss(avg_extension, 0.9, 0.15)
        rw += _gauss(avg_hand_dist, torso_height * 1.2, torso_height * 0.3)
        rw += _gauss(trunk, 10, 10)
        # Wrist velocity: reaching involves rapid arm extension movement
        wrist_vel = features.get("wrist_movement_velocity", 0.0)
        wrist_velocity_score = _gauss(wrist_vel, 150, 80)
        rw += wrist_velocity_score
        rw_score = rw / 4.0
        scores["Reaching"] = rw_score
        if avg_extension > 0.8:
            rw_reasons.append("Arms extended")
        if avg_hand_dist > torso_height:
            rw_reasons.append("Hands far from body")
        if trunk > 8:
            rw_reasons.append("Forward lean")
        if wrist_vel > 100:
            rw_reasons.append("Rapid wrist movement")
        reasons["Reaching"] = rw_reasons

        # --- Lifting / Picking ---
        lf = 0.0
        lf_reasons: List[str] = []
        lf += _gauss(trunk, 30, 15)
        lf += _gauss(avg_wrist_rel_y, 30, 15)
        lf += max(0.0, _gauss(knee, 150, 20))
        lf_score = lf / 3.0
        scores["Lifting / Picking"] = lf_score
        if trunk > 20:
            lf_reasons.append("Significant trunk flexion")
        if avg_wrist_rel_y > 25:
            lf_reasons.append("Hands below waist")
        if knee < 150:
            lf_reasons.append("Knees bent")
        reasons["Lifting / Picking"] = lf_reasons

        # --- Inspection ---
        ip = 0.0
        ip_reasons: List[str] = []
        ip += _gauss(neck, 25, 8)
        ip += _gauss(wrist_height_ratio, -0.4, 0.3)
        ip += _gauss(trunk, 0, 10)
        ip_score = ip / 3.0
        scores["Inspection"] = ip_score
        if neck > 15:
            ip_reasons.append("Looking down")
        if wrist_height_ratio < -0.2:
            ip_reasons.append("Hands raised to face level")
        if trunk < 12:
            ip_reasons.append("Upright trunk")
        reasons["Inspection"] = ip_reasons

        best_task = max(scores, key=scores.get)
        best_score = scores[best_task]

        if best_score < 0.3 or features.get("neck_flexion", 0) < -1:
            best_task = "Unknown"
            best_score = max(best_score, 0.2)

        self._current_task = best_task
        self._confidence = round(best_score * 100, 1)

        chosen_reasons = reasons.get(best_task, [])
        self._reason = "; ".join(chosen_reasons[:3]) if chosen_reasons else "No specific indicators"
        if not chosen_reasons and best_task == "Unknown":
            self._reason = "No clear task pattern detected"

        return self._finalize(self._current_task, self._confidence, self._reason, kps)

    def _finalize(self, task: str, confidence: float, reason: str,
                  kps: np.ndarray) -> Dict:
        """Apply window smoothing + dwell tracking and build the result dict.

        Shared by the model-primary path and the Gaussian fallback so both
        get identical temporal behavior.
        """
        self._current_task = task
        self._confidence = confidence
        self._reason = reason
        self._prev_kps = kps.copy()

        # ── Temporal smoothing: confidence-weighted sliding window ──
        self._window.append((self._current_task, self._confidence))

        if len(self._window) >= 2:
            weights: Dict[str, float] = {}
            for t, c in self._window:
                weights[t] = weights.get(t, 0.0) + c
            smoothed_task = max(weights, key=weights.get)
            smoothed_conf = weights[smoothed_task] / len(self._window)

            # Apply smoothing only when the window has a clear preference
            if smoothed_task != self._current_task:
                second_best = max((t for t, c in weights.items() if t != smoothed_task),
                                  key=lambda t: weights[t], default=None)
                margin = weights[smoothed_task] - (weights.get(second_best, 0) if second_best else 0)
                # Only override raw if the smoothed winner has a meaningful margin
                if margin > 5.0:
                    self._current_task = smoothed_task
                    self._confidence = round(smoothed_conf, 1)

        # ── Dwell-time tracking ────────────────────────────────────
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


def _gauss(value: float, mean: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return math.exp(-0.5 * ((value - mean) / sigma) ** 2)
