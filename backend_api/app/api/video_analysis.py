"""Uploaded video analysis endpoints — background job queue.

``POST /video/analyze`` now accepts the upload, persists it to a temp file,
queues a background analysis job and returns immediately with a ``job_id``.
The heavy pose/context work runs in a daemon thread so the HTTP request never
blocks for minutes. Poll ``GET /video/analyze/{job_id}`` for progress and the
final result.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

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

JOB_TTL_SECONDS = 30 * 60  # completed/errored jobs are kept for 30 minutes


# ── In-memory job store (single-process; survives for the app lifetime) ─────
class VideoAnalysisJob(BaseModel):
    job_id: str
    status: str  # queued | processing | complete | error
    progress: dict = {"frames_processed": 0, "total_frames": 0, "percent": 0.0}
    result: Optional[VideoAnalysisResponse] = None
    error: Optional[str] = None
    # Private bookkeeping (never serialized to clients — underscore attrs are
    # private in Pydantic v2 by default).
    _finished_at: float = 0.0


class VideoAnalysisJobStart(BaseModel):
    job_id: str
    status: str = "queued"


_jobs: dict[str, VideoAnalysisJob] = {}
_jobs_lock = threading.Lock()


def _cleanup_expired_jobs() -> None:
    """Drop finished jobs older than the TTL (called on each new submission)."""
    now = time.time()
    stale = [
        jid
        for jid, job in list(_jobs.items())
        if job.status in ("complete", "error") and job._finished_at
        and now - job._finished_at > JOB_TTL_SECONDS
    ]
    for jid in stale:
        _jobs.pop(jid, None)


def _run_job(job_id: str, temp_path: str, filename: str) -> None:
    """Background worker: analyze the video and update the job record."""
    try:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id].status = "processing"

        def progress_cb(processed: int, total: int) -> None:
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job is None:
                    return
                job.progress = {
                    "frames_processed": processed,
                    "total_frames": total,
                    "percent": round(processed / total * 100, 1) if total else 0.0,
                }

        result = _analyze_video_file(temp_path, filename, progress_cb=progress_cb)
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.result = result
                job.status = "complete"
                job.progress = {
                    "frames_processed": len(result.frames),
                    "total_frames": result.summary.source_frames,
                    "percent": 100.0,
                }
                job._finished_at = time.time()
    except Exception as exc:  # noqa: BLE001 - surface any failure to the job
        detail = getattr(exc, "detail", None) or str(exc)
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.status = "error"
                job.error = str(detail)
                job._finished_at = time.time()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


@router.post("/video/analyze", response_model=VideoAnalysisJobStart)
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
    job_id = f"VIDJOB-{uuid4().hex[:8]}"
    try:
        with _jobs_lock:
            _cleanup_expired_jobs()
            _jobs[job_id] = VideoAnalysisJob(job_id=job_id, status="queued")
    except Exception:
        # Never leak the uploaded temp file if job registration fails.
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

    threading.Thread(
        target=_run_job,
        args=(job_id, temp_path, filename),
        daemon=True,
        name=f"video-analysis-{job_id}",
    ).start()

    return VideoAnalysisJobStart(job_id=job_id, status="queued")


@router.get("/video/analyze/{job_id}", response_model=VideoAnalysisJob)
async def get_video_analysis_job(
    job_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis job not found (expired after 30 minutes).",
            )
        # Snapshot under the lock: the worker thread may keep mutating the
        # live job (progress/status) — serialize a stable copy, not the same
        # object the background thread is writing.
        return job.model_copy(deep=True)


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


def _analyze_video_file(
    video_path: str,
    filename: str,
    frame_step: int = 10,
    progress_cb=None,
) -> VideoAnalysisResponse:
    """Analyze a video file synchronously (runs inside the background job).

    ``progress_cb(processed, total)`` is invoked once per frame read so the
    job store can surface a live percentage to the polling UI.
    """
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

            if progress_cb is not None and frame_index % max(frame_step, 10) == 0:
                progress_cb(frame_index, total_frames)

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
