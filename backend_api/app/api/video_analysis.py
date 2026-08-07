"""Uploaded video analysis endpoints."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser
from app.schemas.api import VideoAnalysisFrame, VideoAnalysisResponse, VideoAnalysisSummary
from backend.context.engine import ContextIntelligenceEngine
from backend.services.features import unavailable_features_from_keypoints, lower_body_confidence
from backend.services.pose_engine import PoseEngine

router = APIRouter()

MAX_VIDEO_BYTES = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".m4v"}
MODEL_PATH = Path(os.environ.get("POSE_MODEL_PATH", ROOT / "models" / "pose_landmarker_lite.task"))


@router.post("/video/analyze", response_model=VideoAnalysisResponse)
async def analyze_video(
    file: UploadFile = File(...),
    _: AuthenticatedUser = Depends(get_current_user),
):
    filename = file.filename or "uploaded-video"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported video type. Upload MP4, AVI, MOV, or M4V.",
        )

    temp_path = await _save_limited_upload(file, suffix)
    try:
        return _analyze_video_file(temp_path, filename)
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


async def _save_limited_upload(file: UploadFile, suffix: str) -> str:
    total = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = tmp.name
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_VIDEO_BYTES:
                tmp.close()
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Video exceeds the 200MB upload limit.",
                )
            tmp.write(chunk)
    if total == 0:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded video is empty.")
    return temp_path


def _analyze_video_file(video_path: str, filename: str, frame_step: int = 10) -> VideoAnalysisResponse:
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Pose model not found at {MODEL_PATH}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not open the uploaded video.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    duration_seconds = total_frames / fps if fps > 0 and total_frames > 0 else 0.0
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)

    engine = PoseEngine(str(MODEL_PATH))
    context_engine = ContextIntelligenceEngine(session_id=f"VID-{uuid4().hex[:8]}")
    frames: list[VideoAnalysisFrame] = []
    frame_index = 0
    # Aggregate unavailable features tracking
    all_unavailable_features: set[str] = set()
    frames_with_unavailable_count = 0

    try:
        engine.initialize()
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_index % frame_step == 0:
                result = engine.process_frame(frame)
                if result.person_detected:
                    timestamp = frame_index / fps if fps > 0 else float(len(frames))
                    delta_seconds = frame_step / fps if fps > 0 else 0.033
                    task_name = "Neutral Standing"
                    task_confidence = 0.0
                    if result.task_info:
                        task_name = result.task_info.get("task", "Neutral Standing")
                        task_confidence = result.task_info.get("confidence", 0.0)

                    snapshot = context_engine.evaluate(
                        features=result.features,
                        issues=result.issues or [],
                        task_name=task_name,
                        task_confidence=task_confidence,
                        session_duration_seconds=timestamp,
                        camera_confidence=result.confidence,
                        delta_seconds=delta_seconds,
                        unavailable_features=result.unavailable_features,
                        lower_body_confidence=result.lower_body_confidence,
                    )

                    # Normalize keypoints to 0-1 for frontend
                    normalized_keypoints = []
                    for kp in result.keypoints:
                        x_norm = kp[0] / frame_width
                        y_norm = kp[1] / frame_height
                        normalized_keypoints.append([x_norm, y_norm, kp[2], kp[3]])

                    # Track aggregate unavailable features
                    all_unavailable_features.update(result.unavailable_features)
                    if len(result.unavailable_features) > 0:
                        frames_with_unavailable_count += 1

                    frames.append(
                        VideoAnalysisFrame(
                            frame_index=frame_index,
                            timestamp_seconds=round(timestamp, 3),
                            risk_level=snapshot.risk_level,
                            confidence=round(float(result.confidence), 2),
                            features={key: round(float(value), 4) for key, value in result.features.items()},
                            feature_scores=snapshot.feature_scores,
                            unavailable_features=list(result.unavailable_features),
                            lower_body_confidence=result.lower_body_confidence,
                            keypoints=normalized_keypoints,
                        )
                    )
            frame_index += 1
    finally:
        cap.release()
        engine.release()

    if not frames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No clear person was detected in the processed video frames.",
        )

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for frame in frames:
        risk_counts[frame.risk_level] = risk_counts.get(frame.risk_level, 0) + 1

    analyzed = len(frames)
    risk_percentages = {
        level: round(count / analyzed * 100, 1)
        for level, count in risk_counts.items()
    }
    feature_names = frames[0].features.keys()
    average_features = {}
    for name in feature_names:
        # Filter out any NaN values when calculating average
        valid_values = [
            frame.features[name]
            for frame in frames
            if frame.features[name] == frame.features[name]  # check not NaN
        ]
        avg = sum(valid_values) / len(valid_values) if valid_values else 0.0
        average_features[name] = round(avg, 4)

    # Calculate percentage of frames with unavailable features
    frames_with_unavailable_percentage = round(frames_with_unavailable_count / analyzed * 100, 1) if analyzed > 0 else 0.0

    return VideoAnalysisResponse(
        filename=filename,
        summary=VideoAnalysisSummary(
            analyzed_frames=analyzed,
            source_frames=total_frames,
            duration_seconds=round(duration_seconds, 3),
            fps=round(fps, 3),
            frame_step=frame_step,
            risk_counts=risk_counts,
            risk_percentages=risk_percentages,
            average_features=average_features,
            all_unavailable_features=list(all_unavailable_features),
            frames_with_unavailable_features=frames_with_unavailable_percentage,
        ),
        frames=frames,
    )
