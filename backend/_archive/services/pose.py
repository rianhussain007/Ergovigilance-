from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np

from backend.services.features import (
    FEATURE_COLUMNS,
    RISK_COLORS_BGR,
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
)


POSE_CONNECTIONS = [
    (0, 7, "neck"),
    (0, 8, "neck"),
    (7, 11, "neck"),
    (8, 12, "neck"),
    (11, 12, "shoulder"),
    (11, 13, "shoulder"),
    (13, 15, "shoulder"),
    (12, 14, "shoulder"),
    (14, 16, "shoulder"),
    (11, 23, "trunk"),
    (12, 24, "trunk"),
    (23, 24, "trunk"),
    (23, 25, "trunk"),
    (25, 27, "trunk"),
    (24, 26, "trunk"),
    (26, 28, "trunk"),
]

ROOT = Path(__file__).resolve().parents[2]
POSE_TASK_MODEL = ROOT / "models" / "pose_landmarker_lite.task"
_TASK_POSE_LANDMARKER = None


class NoPersonDetectedError(ValueError):
    pass


class ImageQualityError(ValueError):
    pass


def detect_pose_from_bgr(image: np.ndarray) -> Dict[str, Any]:
    quality_issue = assess_image_quality(image)
    if quality_issue:
        raise ImageQualityError(quality_issue)

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = _detect_with_mediapipe(rgb)

    if not result["landmarks"]:
        raise NoPersonDetectedError("No person detected. Please upload a clear full-body image")

    height, width = image.shape[:2]
    keypoints = mediapipe_landmarks_to_keypoints(result["landmarks"], width, height)
    features = extract_features_from_keypoints(keypoints)
    return {
        "keypoints": keypoints,
        "features": {name: features[name] for name in FEATURE_COLUMNS},
        "unavailable_features": [],
    }


def assess_image_quality(image: np.ndarray) -> str | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if brightness < 35 or sharpness < 12:
        return "Image quality too low for accurate analysis"
    return None


def _detect_with_mediapipe(rgb: np.ndarray) -> Dict[str, Any]:
    import mediapipe as mp

    if hasattr(mp, "solutions"):
        with mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1, min_detection_confidence=0.5) as pose:
            result = pose.process(rgb)
        return {"landmarks": result.pose_landmarks.landmark if result.pose_landmarks else []}

    return _detect_with_mediapipe_tasks(rgb, mp)


def _detect_with_mediapipe_tasks(rgb: np.ndarray, mp: Any) -> Dict[str, Any]:
    global _TASK_POSE_LANDMARKER

    if not POSE_TASK_MODEL.exists():
        raise RuntimeError(
            f"MediaPipe Tasks is installed, but the pose model file is missing: {POSE_TASK_MODEL}. "
            "Download pose_landmarker_lite.task into the models folder."
        )

    if _TASK_POSE_LANDMARKER is None:
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=str(POSE_TASK_MODEL))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
        )
        _TASK_POSE_LANDMARKER = vision.PoseLandmarker.create_from_options(options)

    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    result = _TASK_POSE_LANDMARKER.detect(image)
    if not result.pose_landmarks:
        return {"landmarks": []}
    return {"landmarks": result.pose_landmarks[0]}


def annotate_pose(image: np.ndarray, keypoints: list[list[float]], features: Dict[str, float], risk_level: str) -> np.ndarray:
    output = image.copy()
    green = RISK_COLORS_BGR["LOW"]
    red = RISK_COLORS_BGR["HIGH"]
    neck_color = red if features["neck_flexion"] > 30 else green
    trunk_color = red if features["trunk_flexion"] > 60 else green
    shoulder_color = red if max(features["left_shoulder_elev"], features["right_shoulder_elev"]) > 60 else green

    segment_colors = {
        "neck": neck_color,
        "shoulder": shoulder_color,
        "trunk": trunk_color,
    }

    for a, b, segment in POSE_CONNECTIONS:
        if a >= len(keypoints) or b >= len(keypoints):
            continue
        color = segment_colors.get(segment, green)
        p1 = tuple(np.round(keypoints[a][:2]).astype(int))
        p2 = tuple(np.round(keypoints[b][:2]).astype(int))
        cv2.line(output, p1, p2, color, 3, lineType=cv2.LINE_AA)

    for idx, point in enumerate(keypoints):
        if idx >= 33:
            continue
        color = green
        if idx in {7, 8}:
            color = neck_color
        elif idx in {11, 12, 13, 14, 15, 16}:
            color = shoulder_color
        elif idx in {23, 24, 25, 26, 27, 28}:
            color = trunk_color
        cv2.circle(output, tuple(np.round(point[:2]).astype(int)), 4, color, -1, lineType=cv2.LINE_AA)

    return output
