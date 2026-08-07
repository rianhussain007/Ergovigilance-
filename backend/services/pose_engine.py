"""Reusable pose estimation pipeline.

Extracted from scripts/live_demo.py to be shared by:
- scripts/live_demo.py (desktop demo)
- backend_api/app/services/live_monitor.py (FastAPI server)
"""

import os
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from backend.services.features import (
    FEATURE_COLUMNS,
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
    risk_from_features,
    unavailable_features_from_keypoints,
    lower_body_confidence,
)
from backend.services.issue_detection import detect_posture_issues
from backend.services.recommendation_engine import get_recommendations
from backend.services.task_recognition import TaskRecognition

# Canonical definitions live in backend.core.constants and backend.core.types.
# Re-exported here for backward compatibility.
from backend.core.constants import RISK_LEVELS_DICT as RISK_LEVELS  # noqa: F401
from backend.core.constants import CONFIDENCE_LANDMARKS  # noqa: F401
from backend.core.types import ProcessedFrame  # noqa: F401
from backend.core.utils import wrist_movement_velocity_px


def _compute_confidence(landmarks) -> float:
    vals = [
        landmarks[i].visibility
        for i in CONFIDENCE_LANDMARKS
        if i < len(landmarks) and hasattr(landmarks[i], "visibility")
    ]
    return float(np.mean(vals)) * 100 if vals else 0.0


def _compute_lower_body_confidence(keypoints) -> float:
    """Confidence score for lower-body landmarks (hips, knees, ankles)."""
    if not keypoints or len(keypoints) < 29:
        return 0.0
    lower_indices = [23, 24, 25, 26, 27, 28]
    vis_vals = [keypoints[i][3] for i in lower_indices if i < len(keypoints)]
    return float(np.mean(vis_vals)) * 100 if vis_vals else 0.0


# Feature keys that are pure motion signals — never smoothed (they ARE the
# frame-to-frame delta).
_UNSMOOTHED_FEATURES = {"movement_velocity", "wrist_movement_velocity"}


class PoseEngine:
    """Reusable CV pipeline: frame -> MediaPipe -> features -> issues -> recs -> task."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.pose_landmarker = None
        self.task_recognizer = TaskRecognition()
        self.timestamp_ms = 0
        self._initialized = False
        self._prev_features: dict | None = None
        self._prev_timestamp: float = 0.0
        self._smoothed_features: dict | None = None
        # EMA weight for posture features (new sample share). Lower = smoother.
        # Configurable via env so deployments can tune jitter vs. responsiveness.
        try:
            self._smooth_alpha = float(os.environ.get("ERGOVIGILANCE_FEATURE_SMOOTHING", "0.7"))
        except (TypeError, ValueError):
            self._smooth_alpha = 0.7
        self._smooth_alpha = min(1.0, max(0.1, self._smooth_alpha))

    def initialize(self):
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self.model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.pose_landmarker = vision.PoseLandmarker.create_from_options(options)
        self._initialized = True

    def process_frame(self, frame: np.ndarray) -> ProcessedFrame:
        if not self._initialized or self.pose_landmarker is None:
            raise RuntimeError("PoseEngine not initialized. Call initialize() first.")

        self.timestamp_ms += 33
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.pose_landmarker.detect_for_video(mp_image, self.timestamp_ms)

        features = {c: 0.0 for c in FEATURE_COLUMNS}
        risk_level = "LOW"
        confidence = 0.0
        person_detected = False
        task_info = None
        issues = []
        recommendations = []
        keypoints = []
        features: dict[str, float] = {}
        unavailable: list[str] = []
        approximate: list[str] = []
        lb_conf = 0.0

        if result.pose_landmarks:
            person_detected = True
            landmarks = result.pose_landmarks[0]
            h_f, w_f = frame.shape[:2]
            keypoints = mediapipe_landmarks_to_keypoints(landmarks, w_f, h_f)
            features, unavailable, approximate = extract_features_from_keypoints(keypoints)
            lb_conf = _compute_lower_body_confidence(keypoints)

            current_time = time.time()
            if self._prev_features is not None:
                dt = current_time - self._prev_timestamp
                if dt > 1e-6:
                    neck_val = features["neck_flexion"]
                    trunk_val = features["trunk_flexion"]
                    prev_neck = self._prev_features["neck_flexion"]
                    prev_trunk = self._prev_features["trunk_flexion"]
                    # Skip velocity if either value is NaN (unavailable)
                    if neck_val == neck_val and trunk_val == trunk_val:
                        d_neck = abs(neck_val - prev_neck)
                        d_trunk = abs(trunk_val - prev_trunk)
                        features["movement_velocity"] = round(max(d_neck, d_trunk) / dt, 2)
                    else:
                        features["movement_velocity"] = 0.0
                    # Wrist movement velocity: frame-to-frame wrist position
                    # change in pixels/second — the physical scale the task
                    # classifier's Reaching gaussian expects (~150 px/s).
                    # Helper guards against missing wrists from either frame.
                    if len(keypoints) > 16:
                        features["wrist_movement_velocity"] = wrist_movement_velocity_px(
                            prev_left=self._prev_features.get("left_wrist"),
                            prev_right=self._prev_features.get("right_wrist"),
                            curr_left=keypoints[15],
                            curr_right=keypoints[16],
                            dt=dt,
                            width=w_f,
                            height=h_f,
                        )
                    else:
                        features["wrist_movement_velocity"] = 0.0
                else:
                    features["movement_velocity"] = 0.0
                    features["wrist_movement_velocity"] = 0.0
            else:
                features["movement_velocity"] = 0.0
                features["wrist_movement_velocity"] = 0.0

            self._prev_features = {
                "neck_flexion": features["neck_flexion"],
                "trunk_flexion": features["trunk_flexion"],
                "left_wrist": keypoints[15] if len(keypoints) > 15 else None,
                "right_wrist": keypoints[16] if len(keypoints) > 16 else None,
            }
            self._prev_timestamp = current_time

            # Phase B: EMA-smooth static posture features (kills jitter ->
            # fewer false alerts). Motion signals and NaN pass through.
            features = self._apply_smoothing(features)

            risk_level = risk_from_features(features, unavailable)
            confidence = _compute_confidence(landmarks)
            task_info = self.task_recognizer.detect_task(keypoints, features)
        else:
            # No person this frame: reset smoothing so a re-detection
            # starts fresh instead of interpolating against a stale pose.
            self._smoothed_features = None

        if person_detected:
            issues = detect_posture_issues(features)
            recommendations = get_recommendations(issues)

        return ProcessedFrame(
            keypoints=keypoints,
            features=features,
            risk_level=risk_level,
            confidence=confidence,
            person_detected=person_detected,
            task_info=task_info,
            issues=issues,
            recommendations=recommendations,
            timestamp=time.time(),
            unavailable_features=unavailable,
            approximate_features=approximate,
            lower_body_confidence=lb_conf,
        )

    def _apply_smoothing(self, features: dict[str, float]) -> dict[str, float]:
        """Exponentially smooth the static posture features in place.

        Motion features (movement_velocity, wrist_movement_velocity) and NaN
        (unavailable) values are passed through untouched. Smoothing state is
        reset whenever a person is not detected, so a re-detection starts fresh
        instead of interpolating against a stale pose.
        """
        if self._smoothed_features is None:
            self._smoothed_features = dict(features)
            return self._smoothed_features
        alpha = self._smooth_alpha
        for key in FEATURE_COLUMNS:
            if key in _UNSMOOTHED_FEATURES:
                continue
            raw = features.get(key)
            if raw is None:
                continue  # missing key -> keep previous
            if raw != raw:
                # NaN this frame (landmark unavailable): propagate the NaN so
                # downstream consumers (issues, task recognition) see the
                # unavailable state instead of a stale high value that keeps
                # firing false alerts.
                self._smoothed_features[key] = float("nan")
                continue
            prev = self._smoothed_features.get(key)
            self._smoothed_features[key] = round(alpha * raw + (1.0 - alpha) * (prev if prev is not None and prev == prev else raw), 4)
        return self._smoothed_features

    def release(self):
        if self.pose_landmarker:
            self.pose_landmarker.close()
            self.pose_landmarker = None
        self._initialized = False
        self._smoothed_features = None
