"""Uploaded video analysis endpoints — background job queue.

``POST /video/analyze`` now accepts the upload, persists it to a temp file,
queues a background analysis job and returns immediately with a ``job_id``.
The heavy pose/context work runs in a daemon thread so the HTTP request never
blocks for minutes. Poll ``GET /video/analyze/{job_id}`` for progress and the
final result.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Optional
from uuid import uuid4

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
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

from app.services.pose_overlay import compute_region_levels, draw_skeleton

router = APIRouter()

MAX_VIDEO_BYTES = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".m4v"}
MODEL_PATH = Path(os.environ.get("POSE_MODEL_PATH", ROOT / "models" / "pose_landmarker_lite.task"))

JOB_TTL_SECONDS = 30 * 60  # completed/errored jobs are kept for 30 minutes

# Burned-in overlay videos are written here and deleted when the job expires.
OVERLAY_OUTPUT_DIR = Path(ROOT) / "outputs" / "video_review"


# ── SQLite-backed job store (survives restarts) ─────────────────────────────
def _job_db_path() -> Path:
    """Persist jobs next to the auth DB (same volume in containers)."""
    db_env = os.environ.get("AUTH_DB_PATH", "")
    if db_env:
        return Path(db_env).parent / "video_analysis_jobs.db"
    return ROOT / "backend_api" / "video_analysis_jobs.db"


_JOB_DB = _job_db_path()


def _job_db_connection() -> sqlite3.Connection:
    _JOB_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_JOB_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _job_db():
    """Context manager that closes the connection (sqlite's own CM only commits)."""
    return closing(_job_db_connection())


def _init_job_db() -> None:
    with _job_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS video_analysis_jobs (
                job_id      TEXT PRIMARY KEY,
                status      TEXT NOT NULL,
                progress    TEXT NOT NULL DEFAULT '{}',
                result      TEXT,
                error       TEXT,
                finished_at REAL NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL
            )
            """
        )
        conn.commit()


def _persist_job(job: "VideoAnalysisJob") -> None:
    """Write the job row to SQLite (best-effort; never raises at runtime).

    Serializes with ``model_dump(mode="json")`` so numpy-typed values from the
    analysis result (e.g. float32 features) convert to plain JSON numbers — the
    default ``mode="python"`` keeps numpy scalars, which ``json.dumps`` rejects.
    """
    try:
        result_json = None
        if job.result is not None:
            result_json = json.dumps(job.result.model_dump(mode="json"))
        with _job_db() as conn:
            conn.execute(
                """
                INSERT INTO video_analysis_jobs (job_id, status, progress, result, error, finished_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    progress = excluded.progress,
                    result = excluded.result,
                    error = excluded.error,
                    finished_at = excluded.finished_at
                """,
                (
                    job.job_id,
                    job.status,
                    json.dumps(job.progress),
                    result_json,
                    job.error,
                    job._finished_at,
                    time.time(),
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 - persistence is best-effort
        logging.getLogger(__name__).warning("Failed to persist analysis job %s: %s", job.job_id, exc)


def _load_jobs_from_db() -> None:
    """Rehydrate the in-memory store from SQLite at startup.

    Jobs that were still ``queued``/``processing`` when the process died are
    marked ``error`` (their worker thread is gone) so clients polling them get
    a definitive answer instead of an eternal spinner.
    """
    try:
        _init_job_db()
        with _job_db() as conn:
            rows = conn.execute("SELECT * FROM video_analysis_jobs").fetchall()
        for row in rows:
            job = VideoAnalysisJob(
                job_id=row["job_id"],
                status=row["status"],
                progress=json.loads(row["progress"] or "{}"),
                result=VideoAnalysisResponse.model_validate_json(row["result"]) if row["result"] else None,
                error=row["error"],
            )
            job._finished_at = float(row["finished_at"] or 0)
            if job.status in ("queued", "processing"):
                job.status = "error"
                job.error = "Server restarted while this job was running — please re-upload the video."
                job._finished_at = time.time()
                _persist_job(job)
            with _jobs_lock:
                _jobs[job.job_id] = job
    except Exception:  # noqa: BLE001 - recovery is best-effort
        pass


# ── In-memory job store (single-process; mirrors the SQLite rows) ───────────
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

# Rehydrate persisted jobs from SQLite at import time so analysis jobs survive
# backend restarts (in-flight ones are marked error).
_load_jobs_from_db()


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
        # The burned overlay video has the same lifecycle as the job.
        try:
            (OVERLAY_OUTPUT_DIR / f"{jid}.mp4").unlink(missing_ok=True)
        except OSError:
            pass
    if stale:
        try:
            with _job_db() as conn:
                conn.executemany(
                    "DELETE FROM video_analysis_jobs WHERE job_id = ?", [(jid,) for jid in stale]
                )
                conn.commit()
        except Exception:  # noqa: BLE001 - cleanup is best-effort
            pass


def _run_job(job_id: str, temp_path: str, filename: str) -> None:
    """Background worker: analyze the video and update the job record."""
    try:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id].status = "processing"
                _persist_job(_jobs[job_id])

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

        result = _analyze_video_file(
            temp_path,
            filename,
            progress_cb=progress_cb,
            output_video_path=str(OVERLAY_OUTPUT_DIR / f"{job_id}.mp4"),
        )
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
                _persist_job(job)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the job
        detail = getattr(exc, "detail", None) or str(exc)
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.status = "error"
                job.error = str(detail)
                job._finished_at = time.time()
                _persist_job(job)
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
            _persist_job(_jobs[job_id])
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


@router.post("/video/analyze/recording/{session_id}", response_model=VideoAnalysisJobStart)
async def analyze_recording(
    session_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Queue the same ML pose-analysis pipeline on a recorded session's video.

    Copies ``original.mp4`` from the session's recording directory into a temp
    file and runs the identical background job as an uploaded video, so admins
    can re-review any past session with full keypoints, features, risk
    timeline, and a downloadable overlay video.
    """
    import shutil

    from app.api.recordings import _find_recording_dir

    rec_dir = _find_recording_dir(session_id)
    if not rec_dir:
        raise HTTPException(status_code=404, detail=f"Recording {session_id} not found")
    video_path = Path(rec_dir) / "original.mp4"
    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No video was recorded for this session — only sessions with a recording can be analyzed.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        temp_path = tmp.name
    shutil.copyfile(video_path, temp_path)

    job_id = f"VIDJOB-{uuid4().hex[:8]}"
    try:
        with _jobs_lock:
            _cleanup_expired_jobs()
            _jobs[job_id] = VideoAnalysisJob(job_id=job_id, status="queued")
            _persist_job(_jobs[job_id])
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

    threading.Thread(
        target=_run_job,
        args=(job_id, temp_path, f"{session_id}.mp4"),
        daemon=True,
        name=f"video-analysis-{job_id}",
    ).start()

    return VideoAnalysisJobStart(job_id=job_id, status="queued")


@router.get("/video/analyze/{job_id}/download")
async def download_video_with_overlay(
    job_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Download the analyzed video with the ML pose overlay burned in."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Analysis job not found (expired after 30 minutes).",
            )
        if job.status != "complete":
            raise HTTPException(
                status_code=409,
                detail=f"Analysis is {job.status} — the overlay video is not ready yet.",
            )
    overlay_path = OVERLAY_OUTPUT_DIR / f"{job_id}.mp4"
    if not overlay_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Overlay video not found for this job (encoding may have been skipped).",
        )
    return FileResponse(
        str(overlay_path),
        media_type="video/mp4",
        filename=f"{job_id}_overlay.mp4",
    )


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


def _burn_overlay(video_path: str, frames: list[VideoAnalysisFrame], frame_step: int, output_path: str) -> bool:
    """Re-encode the video with the ML pose overlay burned into all frames.

    Pose was analyzed only every ``frame_step``th frame; to keep the skeleton
    continuously visible (no flicker), the last analyzed frame's overlay is
    held and re-drawn on every intermediate frame until a newer analyzed
    frame replaces it (sample retention). Uses the same ``draw_skeleton``
    rendering as the live MJPEG feed, so the downloaded video is pixel-
    identical to what the operator sees live. Returns True when the output
    file was written.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)
            if width < 1 or height < 1:
                return False
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            writer = cv2.VideoWriter(
                output_path,
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )
            if not writer.isOpened():
                return False
            by_index = {frame.frame_index: frame for frame in frames}
            # Sample retention: pose was analyzed only every ``frame_step``th
            # frame, so drawing only on those indices made the overlay blink
            # on/off (1 analyzed frame, then 9 raw frames at 25 fps). Hold the
            # last analyzed frame and keep its skeleton on the video until a
            # newer analyzed frame replaces it — zero flicker, and the overlay
            # tracks the person between samples instead of vanishing.
            last_analyzed = None
            frame_index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                analyzed = by_index.get(frame_index)
                if analyzed is not None:
                    last_analyzed = analyzed
                if last_analyzed is not None and last_analyzed.keypoints:
                    try:
                        frame = draw_skeleton(
                            frame,
                            last_analyzed.keypoints,
                            last_analyzed.risk_level,
                            features=last_analyzed.features,
                            region_levels=last_analyzed.region_risks,
                        )
                    except Exception:  # noqa: BLE001 - never fail the whole job on one frame
                        pass
                writer.write(frame)
                frame_index += 1
            writer.release()
        finally:
            cap.release()
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:  # noqa: BLE001 - overlay burn is best-effort
        return False


def _analyze_video_file(
    video_path: str,
    filename: str,
    frame_step: int = 10,
    progress_cb=None,
    output_video_path: str | None = None,
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
                        standard_assessment=result.standard_assessment,
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

                    # Same per-region risk bands the live overlay uses, so the
                    # replay skeleton colors exactly like the live feed. The
                    # standard assessment is threaded through so the colors
                    # derive from the RULA/REBA sub-scores, matching the level.
                    region_risks = compute_region_levels(
                        result.features, snapshot.risk_level, result.standard_assessment
                    )

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
                            region_risks=region_risks,
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

    # Burn the ML pose overlay into a downloadable copy (best-effort; the
    # analysis result is already complete even if encoding fails).
    if output_video_path:
        _burn_overlay(video_path, frames, frame_step, output_video_path)

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
