"""Reusable pose estimation pipeline.

Extracted from scripts/live_demo.py to be shared by:
- scripts/live_demo.py (desktop demo)
- backend_api/app/services/live_monitor.py (FastAPI server)
"""

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
                    # Wrist movement velocity: frame-to-frame wrist position change
                    if self._prev_features.get("left_wrist") is not None and len(keypoints) > 16:
                        lw = keypoints[15]  # left wrist
                        rw = keypoints[16]  # right wrist
                        prev_lw = self._prev_features["left_wrist"]
                        prev_rw = self._prev_features["right_wrist"]
                        d_lw = ((lw[0] - prev_lw[0])**2 + (lw[1] - prev_lw[1])**2) ** 0.5
                        d_rw = ((rw[0] - prev_rw[0])**2 + (rw[1] - prev_rw[1])**2) ** 0.5
                        features["wrist_movement_velocity"] = round(max(d_lw, d_rw) / dt, 2)
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

            risk_level = risk_from_features(features, unavailable)
            confidence = _compute_confidence(landmarks)
            task_info = self.task_recognizer.detect_task(keypoints, features)

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

    def release(self):
        if self.pose_landmarker:
            self.pose_landmarker.close()
            self.pose_landmarker = None
        self._initialized = False
