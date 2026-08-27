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


# Temporal feature names (must match train_task_model_v3.py)
_TEMPORAL_FEATURES = [
    "neck_flexion_mean_5", "neck_flexion_mean_10",
    "trunk_flexion_mean_5", "trunk_flexion_mean_10",
    "knee_angle_mean_5", "knee_angle_mean_10",
    "left_shoulder_elev_mean_5", "left_shoulder_elev_mean_10",
    "movement_velocity_mean_5", "movement_velocity_mean_10",
    "neck_flexion_delta", "trunk_flexion_delta",
    "knee_angle_delta", "shoulder_elev_delta",
    "velocity_acceleration",
]


def _compute_temporal_features(window: list[dict]) -> dict:
    """Compute temporal features from a window of feature dictionaries."""
    temporal = {}
    if len(window) < 2:
        for feat in _TEMPORAL_FEATURES:
            temporal[feat] = 0.0
        return temporal

    for feat_name in ["neck_flexion", "trunk_flexion", "knee_angle",
                      "left_shoulder_elev", "movement_velocity"]:
        values = [f.get(feat_name, 0.0) for f in window]
        temporal[f"{feat_name}_mean_5"] = float(np.mean(values[-5:])) if len(values) >= 5 else float(np.mean(values))
        temporal[f"{feat_name}_mean_10"] = float(np.mean(values[-10:])) if len(values) >= 10 else float(np.mean(values))

    if len(window) >= 2:
        prev, curr = window[-2], window[-1]
        temporal["neck_flexion_delta"] = curr.get("neck_flexion", 0) - prev.get("neck_flexion", 0)
        temporal["trunk_flexion_delta"] = curr.get("trunk_flexion", 0) - prev.get("trunk_flexion", 0)
        temporal["knee_angle_delta"] = curr.get("knee_angle", 0) - prev.get("knee_angle", 0)
        temporal["shoulder_elev_delta"] = curr.get("left_shoulder_elev", 0) - prev.get("left_shoulder_elev", 0)

    if len(window) >= 3:
        v1 = window[-3].get("movement_velocity", 0)
        v2 = window[-2].get("movement_velocity", 0)
        v3 = window[-1].get("movement_velocity", 0)
        temporal["velocity_acceleration"] = (v3 - v2) - (v2 - v1)
    else:
        temporal["velocity_acceleration"] = 0.0

    return temporal


class TaskRecognition:
    """Task/activity recognition for the live pipeline.

    Model-primary with Gaussian fallback: when a trained classifier
    (models/task_model_v3.pkl or v2, loaded lazily) is available and its
    top prediction exceeds the confidence threshold (default 0.6), the
    model decides; otherwise the deterministic Gaussian scorer runs.
    v3 models include temporal features (frame-window averages, deltas)
    computed automatically from the feature history.
    """

    DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "task_model_v3.pkl"
    FALLBACK_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "task_model_v2.pkl"
    UPPER_BODY_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "upper_body_task_model.pkl"

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
        # Feature history for temporal features (v3)
        self._feature_window: deque[dict] = deque(maxlen=10)

        env_path = os.environ.get("ERGOVIGILANCE_TASK_MODEL")
        if model_path:
            self._model_path = Path(model_path)
        elif env_path:
            self._model_path = Path(env_path)
        else:
            # Prefer v3, fall back to v2
            self._model_path = self.DEFAULT_MODEL_PATH if self.DEFAULT_MODEL_PATH.exists() else self.FALLBACK_MODEL_PATH
        self._model_bundle: dict | None = None
        self._model_tried: bool = False
        self._confidence_threshold: float = 0.6
        self._using_model: bool = False
        self._model_version: str = "unknown"

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
                # Try fallback v2 if v3 doesn't exist
                if self._model_path == self.DEFAULT_MODEL_PATH and self.FALLBACK_MODEL_PATH.exists():
                    self._model_path = self.FALLBACK_MODEL_PATH
                else:
                    return None
            bundle = joblib.load(self._model_path)
            if not isinstance(bundle, dict) or "model" not in bundle:
                return None
            self._model_bundle = bundle
            self._confidence_threshold = float(
                bundle.get("config", {}).get("confidence_threshold", 0.6))
            # Detect model version from feature count
            n_features = len(bundle.get("feature_columns", []))
            self._model_version = bundle.get("version", "v2" if n_features <= 20 else "v3")
        except Exception:
            self._model_bundle = None
        return self._model_bundle

    def _predict_with_model(self, features: Dict[str, float]) -> tuple[str, float] | None:
        """Return (task, confidence) if the model is confident, else None.
        
        Automatically selects the best model based on feature availability:
        - If lower-body features are available: use full v3 model
        - If only upper-body features: use upper-body model
        """
        # Check which features are available (non-NaN, non-zero)
        lower_body_features = ["knee_angle", "trunk_flexion", "left_shoulder_elev",
                               "stance_stability", "weight_shift_offset"]
        upper_body_features = ["neck_flexion", "right_shoulder_elev", "shoulder_symmetry",
                               "alignment_deviation", "forward_head_posture", "head_tilt_angle"]
        
        has_lower = any(features.get(f, 0) != 0 and features.get(f, 0) == features.get(f, 0) 
                       for f in lower_body_features)
        has_upper = any(features.get(f, 0) != 0 and features.get(f, 0) == features.get(f, 0)
                       for f in upper_body_features)
        
        # Select model based on available features
        if has_lower and self.DEFAULT_MODEL_PATH.exists():
            model_path = self.DEFAULT_MODEL_PATH
        elif has_upper and self.UPPER_BODY_MODEL_PATH.exists():
            model_path = self.UPPER_BODY_MODEL_PATH
        elif self._model_path.exists():
            model_path = self._model_path
        else:
            return None
        
        # Load model bundle
        try:
            import joblib
            bundle = joblib.load(model_path)
            if not isinstance(bundle, dict) or "model" not in bundle:
                return None
        except Exception:
            return None
        
        try:
            # Add current features to window for temporal computation
            self._feature_window.append(dict(features))
            
            # For v3 models, compute temporal features
            model_version = bundle.get("version", "unknown")
            if "v3" in model_version:
                temporal = _compute_temporal_features(list(self._feature_window))
                features_with_temporal = {**features, **temporal}
            else:
                features_with_temporal = features
            
            cols = bundle["feature_columns"]
            row = [features_with_temporal.get(c, 0.0) for c in cols]
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
            task = str(classes[best])
        except Exception:
            return None
        
        threshold = float(bundle.get("config", {}).get("confidence_threshold", 0.6))
        if conf < threshold:
            return None
        return task, conf

    def reset(self) -> None:
        self._current_task = "Unknown"
        self._confidence = 0.0
        self._reason = "Insufficient data"
        self._prev_kps = None
        self._window.clear()
        self._feature_window.clear()
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

        # ── Fast path: try trained model first ──
        # This handles upper-body-only views where keypoints are degenerate
        # but features are valid (e.g. camera shows only upper body).
        model_pred = self._predict_with_model(features)
        if model_pred is not None:
            self._using_model = True
            model_task, model_conf = model_pred
            model_label = f"Trained task classifier ({self._model_version})"
            return self._finalize(model_task, round(model_conf * 100.0, 1),
                                  model_label, kps)

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

        # ── Geometric posture gate (authoritative, model-independent) ──
        # The trained classifier is trained on synthetic STANDING poses and
        # confidently mislabels bent-knee geometry (verified on real data:
        # a sitting worker with knee ~93° read "Neutral Standing" at 98.9%).
        # Unambiguous seating (knees bent, thighs horizontal, hips low) is
        # decided geometrically BEFORE the model, mirroring how RULA/REBA
        # gate posture risk. The model never overrides real geometry.
        mid_knee = _midpoint(lknee, rknee)
        mid_ankle = _midpoint(lankle, rankle)
        thigh_ratio = abs(mid_hip[1] - mid_knee[1]) / torso_height
        leg_ratio = _dist_2d(mid_hip, mid_ankle) / torso_height
        # Keypoints are [x, y, z, visibility]; visibility lives at index 3
        # when present (some callers pass bare [x, y, z] triples — treat
        # those as visible rather than gating on a missing column).
        def _vis(p):
            return p[3] if len(p) > 3 else 1.0

        legs_visible = min(_vis(lhip), _vis(rhip), _vis(lknee), _vis(rknee),
                           _vis(lankle), _vis(rankle)) > 0.5
        if legs_visible and 60.0 < knee < 140.0 and thigh_ratio < 0.45 and leg_ratio < 1.2:
            self._using_model = False
            return self._finalize(
                "Seated Work", 95.0,
                "Knees bent - seated posture detected", kps, force=True)

        # Model already tried above. Fall through to Gaussian scorer.
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
        # Requires relatively straight legs: a bent-knee pose (sitting,
        # squatting) must NOT score as standing. High frame-to-frame
        # movement also rules it out (that is Walking / Moving).
        ns = 0.0
        ns_reasons: List[str] = []
        ns += _gauss(trunk, 0, 8)
        ns += _gauss(neck, 0, 10)
        ns += _gauss(avg_elbow, 170, 15)
        l_wrist_side = 0.0 if lsh[0] <= lwr[0] <= rsh[0] else 1.0
        r_wrist_side = 0.0 if lsh[0] <= rwr[0] <= rsh[0] else 1.0
        wrists_at_sides = (l_wrist_side + r_wrist_side) / 2.0
        ns += wrists_at_sides
        ns += _gauss(knee, 175, 10)
        movement_velocity = features.get("movement_velocity", 0.0)
        ns -= _gauss(movement_velocity, 110, 55)
        ns_score = max(0.0, ns) / 5.0
        scores["Neutral Standing"] = ns_score
        if trunk < 12:
            ns_reasons.append("Minimal trunk flexion")
        if avg_elbow > 155:
            ns_reasons.append("Arms extended naturally")
        if avg_wrist_rel_y > 10:
            ns_reasons.append("Hands near hip level")
        if wrists_at_sides > 0.7:
            ns_reasons.append("Hands at sides")
        if knee > 160:
            ns_reasons.append("Legs straight")
        reasons["Neutral Standing"] = ns_reasons

        # --- Seated Work (desk / assembly at a chair) ---
        sw = 0.0
        sw_reasons: List[str] = []
        sw += _gauss(knee, 100, 22)
        sw += _gauss(thigh_ratio, 0.15, 0.15)
        sw += _gauss(trunk, 5, 10)
        sw += _gauss(wrist_height_ratio, 0.45, 0.25)
        sw_score = sw / 4.0
        scores["Seated Work"] = sw_score
        if knee < 140:
            sw_reasons.append("Knees bent")
        if thigh_ratio < 0.45:
            sw_reasons.append("Thighs horizontal (seated)")
        if trunk < 15:
            sw_reasons.append("Upright trunk")
        if 0.15 < wrist_height_ratio < 0.75:
            sw_reasons.append("Hands at desk level")
        reasons["Seated Work"] = sw_reasons

        # --- Walking / Moving ---
        wk = 0.0
        wk_reasons: List[str] = []
        wk += _gauss(movement_velocity, 110, 55)
        wk += _gauss(knee, 175, 10)
        wk += _gauss(trunk, 5, 10)
        wk += _gauss(wrist_height_ratio, 0.9, 0.35)
        wk_score = wk / 4.0
        scores["Walking / Moving"] = wk_score
        if movement_velocity > 60:
            wk_reasons.append("Continuous movement")
        if knee > 160:
            wk_reasons.append("Legs moving through stride")
        if trunk < 15:
            wk_reasons.append("Upright trunk")
        reasons["Walking / Moving"] = wk_reasons

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
                  kps: np.ndarray, force: bool = False) -> Dict:
        """Apply window smoothing + dwell tracking and build the result dict.

        Shared by the model-primary path and the Gaussian fallback so both
        get identical temporal behavior. ``force=True`` (used by the
        geometric posture gate) skips the smoothing override so an
        authoritative geometric decision (e.g. seated) cannot be smoothed
        away by recent standing predictions.
        """
        self._current_task = task
        self._confidence = confidence
        self._reason = reason
        self._prev_kps = kps.copy()

        # ── Temporal smoothing: confidence-weighted sliding window ──
        self._window.append((self._current_task, self._confidence))

        if len(self._window) >= 2 and not force:
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
