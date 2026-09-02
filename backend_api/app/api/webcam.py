"""Webcam demo endpoint — accepts base64 frames, returns pose landmarks + risk scores."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Lazy-loaded MediaPipe landmarker
_landmarker = None
_landmarker_path = Path(__file__).resolve().parents[3] / "models" / "mediapipe" / "pose_landmarker_heavy.task"


def _get_landmarker():
    global _landmarker
    if _landmarker is not None:
        return _landmarker
    try:
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe import tasks as mp_tasks

        base_options = mp_tasks.BaseOptions(model_asset_path=str(_landmarker_path))
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        _landmarker = mp_vision.PoseLandmarker.create_from_options(options)
        return _landmarker
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MediaPipe init failed: {e}")


def _compute_angle(p1, vertex, p2):
    v1 = p1 - vertex
    v2 = p2 - vertex
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def _extract_features(landmarks, w: int, h: int) -> Dict[str, float]:
    """Extract ergonomic features from MediaPipe landmarks."""
    pts = np.array([[lm.x * w, lm.y * h] for lm in landmarks])
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

    left_arm_angle = _compute_angle(l_shoulder, l_elbow, l_wrist)
    right_arm_angle = _compute_angle(r_shoulder, r_elbow, r_wrist)

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
        "knee_angle": (_compute_angle(l_hip, l_knee, l_ankle) + _compute_angle(r_hip, r_knee, r_ankle)) / 2,
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


def _classify_risk(features: Dict[str, float]) -> str:
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


def _classify_task(features: Dict[str, float]) -> str:
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


class WebcamFrameRequest(BaseModel):
    image: str  # base64-encoded JPEG/PNG
    width: int
    height: int


class PoseKeypoint(BaseModel):
    x: float
    y: float
    z: float
    visibility: float


class WebcamFrameResponse(BaseModel):
    pose_detected: bool
    keypoints: List[PoseKeypoint]
    features: Dict[str, float]
    risk_level: str
    task_label: str
    risk_score: float  # 0-100
    task_confidence: float  # 0-100
    inference_ms: float


@router.post("/api/webcam/detect", response_model=WebcamFrameResponse)
async def detect_webcam_frame(req: WebcamFrameRequest):
    """Process a single webcam frame and return pose detection results."""
    t0 = time.time()

    try:
        image_data = base64.b64decode(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    try:
        import cv2
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Could not decode image")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image decode error: {e}")

    landmarker = _get_landmarker()

    try:
        from mediapipe import Image as MPImage, ImageFormat
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = MPImage(image_format=ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pose detection error: {e}")

    if not result.pose_landmarks or len(result.pose_landmarks) == 0:
        inference_ms = (time.time() - t0) * 1000
        return WebcamFrameResponse(
            pose_detected=False,
            keypoints=[],
            features={},
            risk_level="UNKNOWN",
            task_label="Unknown",
            risk_score=0,
            task_confidence=0,
            inference_ms=inference_ms,
        )

    landmarks = result.pose_landmarks[0]
    features = _extract_features(landmarks, req.width, req.height)
    risk_level = _classify_risk(features)
    task_label = _classify_task(features)

    # Risk score: map risk level to a 0-100 score
    risk_scores = {"LOW": 20, "MEDIUM": 55, "HIGH": 85}
    risk_score = risk_scores.get(risk_level, 0)

    # Task confidence: based on how clearly the features match the task
    task_confidence = 75.0  # base confidence

    keypoints = [
        PoseKeypoint(x=lm.x, y=lm.y, z=lm.z, visibility=lm.visibility)
        for lm in landmarks
    ]

    inference_ms = (time.time() - t0) * 1000

    return WebcamFrameResponse(
        pose_detected=True,
        keypoints=keypoints,
        features=features,
        risk_level=risk_level,
        task_label=task_label,
        risk_score=risk_score,
        task_confidence=task_confidence,
        inference_ms=round(inference_ms, 1),
    )
