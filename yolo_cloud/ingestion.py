"""Cloud Ingestion Service — orchestrates multi-camera YOLO processing.

Each camera gets its own processing thread that:
1. Pulls frames from the RTSP stream
2. Runs YOLOv8-pose inference
3. Tracks workers with ByteTrack
4. Computes risk scores
5. Stores results (session files + in-memory state)
6. Pushes alerts when risk exceeds thresholds
"""

import json
import logging
import math
import os
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from yolo_cloud.config import settings
from yolo_cloud.rtsp_manager import RTSPManager, CameraInfo, get_rtsp_manager
from yolo_cloud.pose_engine import (
    YOLOPoseEngine,
    ProcessedCloudFrame,
    TrackedPose,
    get_pose_engine,
)
from yolo_cloud.identity import get_identity_registry

logger = logging.getLogger(__name__)

# Per-processor sample buffer for latency/lag percentiles. 5000 samples at the
# measured ~1.7 FPS/stream is ~50 minutes of history, which is enough for a
# percentile to mean something without unbounded growth over a long soak.
LATENCY_SAMPLE_MAX = 5000

# End-to-end per-frame latency budget from the hardening spec (p95 must stay
# under this). Recorded next to the measurement so the verdict is not restated
# by hand in every report.
LATENCY_BUDGET_MS = 500.0

# Pre-alert clip capture. A rolling buffer of recent frames is kept per camera and
# written out as a short clip when a HIGH alert fires. Frames are held as JPEG at
# a reduced width: a 10 s window of raw 720p RGB would cost ~280 MB per camera,
# against ~0.4 MB encoded this way, which matters with several cameras running.
CLIP_BUFFER_SECONDS = 10.0
CLIP_FRAME_MAX_W = 640
CLIP_JPEG_QUALITY = 70
# Codec preference for the written clip. avc1 is not used: OpenH264 is absent on
# this stack and the writer reports success while producing an unusable file.
CLIP_CODECS = (("mp4v", ".mp4"), ("MJPG", ".avi"))


def _mp4_has_moov(path: str) -> bool:
    """True when an MP4 file carries its top-level ``moov`` (index) box.

    Walks the top-level box headers only — no decode, no full read. A writer
    that never finalized leaves no ``moov`` at all (ffmpeg: "moov atom not
    found"), and a half-written box header fails the size checks, so any
    uncertainty resolves to False rather than trusting the file.
    """
    try:
        file_size = os.path.getsize(path)
        with open(path, "rb") as handle:
            pos = 0
            while pos + 8 <= file_size:
                handle.seek(pos)
                header = handle.read(8)
                if len(header) < 8:
                    return False
                box_size = struct.unpack(">I", header[:4])[0]
                box_type = header[4:8]
                if box_size == 1:  # 64-bit size follows the header
                    extended = handle.read(8)
                    if len(extended) < 8:
                        return False
                    box_size = struct.unpack(">Q", extended)[0]
                elif box_size == 0:  # box claims to run to EOF
                    box_size = file_size - pos
                if box_size < 8 or box_size > file_size - pos:
                    return False  # truncated or corrupt: not a finalized file
                if box_type == b"moov":
                    return True
                pos += box_size
    except OSError:
        return False
    return False


def _avi_has_index(path: str) -> bool:
    """True when an AVI file carries its trailing ``idx1`` index chunk.

    Same fail-closed rules as the MP4 walk: a chunk whose declared size runs
    past EOF means the writer never finalized, so the file counts as broken.
    """
    try:
        file_size = os.path.getsize(path)
        if file_size < 12:
            return False
        with open(path, "rb") as handle:
            head = handle.read(12)
            if head[:4] != b"RIFF" or head[8:12] != b"AVI ":
                return False
            pos = 12
            while pos + 8 <= file_size:
                handle.seek(pos)
                header = handle.read(8)
                if len(header) < 8:
                    return False
                chunk_id = header[:4]
                chunk_size = struct.unpack("<I", header[4:8])[0]
                if chunk_size > file_size - pos - 8:
                    return False  # chunk runs past EOF: never finalized
                if chunk_id == b"idx1":
                    return True
                pos += 8 + chunk_size + (chunk_size & 1)  # chunks are even-padded
    except OSError:
        return False
    return False


def clip_file_complete(path: str) -> bool:
    """Post-write container check: does this clip carry its final index?

    ``moov`` for MP4, ``idx1`` for AVI. Called after the writer is released
    (the writer can "succeed" and still leave an unplayable file) and again
    when a clip is recovered from disk, so a truncated file is flagged instead
    of being served. Fail-closed: unreadable or unparsable = incomplete.
    """
    if not path or not os.path.exists(path):
        return False
    if path.lower().endswith(".avi"):
        return _avi_has_index(path)
    return _mp4_has_moov(path)


def percentiles(values, points=(50, 95, 99)) -> dict:
    """Nearest-rank percentiles over a sample buffer (``{}`` when empty).

    Nearest-rank rather than interpolated: for a latency budget the question is
    whether an actual observed frame breached 500 ms, so the reported p95 is a
    real sample, not a value between two samples.
    """
    data = sorted(float(v) for v in values)
    if not data:
        return {}
    out: dict = {}
    for point in points:
        rank = math.ceil((point / 100.0) * len(data))  # nearest-rank
        index = min(len(data) - 1, max(0, rank - 1))
        out[f"p{point}"] = round(data[index], 1)
    out["max"] = round(data[-1], 1)
    out["n"] = len(data)
    return out


def normalize_per_hour(count: int, elapsed_seconds: float) -> float:
    """Rate per hour, so a short run and a 4 h run are comparable."""
    if elapsed_seconds <= 0:
        return 0.0
    return round(count * 3600.0 / elapsed_seconds, 1)


@dataclass
class CloudSession:
    """A monitoring session for a single camera."""
    session_id: str
    camera_id: str
    camera_name: str
    start_time: float
    tenant_id: str = "default"
    end_time: Optional[float] = None
    frame_count: int = 0
    person_count: int = 0
    risk_summary: dict = field(default_factory=lambda: {
        "LOW": 0, "MEDIUM": 0, "HIGH": 0,
    })
    risk_scores: list[float] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    # Per-track sampled risk series, keyed by str(track_id) — persisted with the
    # session payload (Postgres JSONB or the on-disk JSON backup).
    track_timelines: dict[str, list[dict]] = field(default_factory=dict)
    is_active: bool = True

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def avg_risk_score(self) -> float:
        if not self.risk_scores:
            return 0.0
        return sum(self.risk_scores) / len(self.risk_scores)

    @property
    def highest_risk(self) -> str:
        if self.risk_summary.get("HIGH", 0) > 0:
            return "HIGH"
        if self.risk_summary.get("MEDIUM", 0) > 0:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "tenant_id": self.tenant_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 1),
            "frame_count": self.frame_count,
            "person_count": self.person_count,
            "risk_summary": self.risk_summary,
            "avg_risk_score": round(self.avg_risk_score, 1),
            "highest_risk": self.highest_risk,
            "alert_count": len(self.alerts),
            "track_timelines": self.track_timelines,
            "is_active": self.is_active,
        }


@dataclass
class CloudAlert:
    """An alert triggered by high risk."""
    alert_id: str
    camera_id: str
    camera_name: str
    session_id: str
    severity: str  # LOW, MEDIUM, HIGH
    message: str
    timestamp: float
    risk_score: float
    task: str
    track_id: int
    worker_id: Optional[str] = None
    tenant_id: str = "default"
    acknowledged: bool = False

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "session_id": self.session_id,
            "severity": self.severity,
            "message": self.message,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "risk_score": self.risk_score,
            "task": self.task,
            "track_id": self.track_id,
            "worker_id": self.worker_id,
            "tenant_id": self.tenant_id,
            "acknowledged": self.acknowledged,
        }


class CloudCameraProcessor:
    """Processes a single camera's frames through the YOLO pipeline."""

    # How long to wait between frame reads when no new frame is available
    FRAME_WAIT_MS = 10  # 100 fps polling
    # How often to save a checkpoint (seconds)
    CHECKPOINT_INTERVAL = 120
    # How many seconds of idle (no persons detected) before auto-stopping
    IDLE_TIMEOUT = settings.SESSION_IDLE_TIMEOUT
    # Minimum frames before creating an alert (avoid spam)
    ALERT_COOLDOWN = 10  # frames between same-type alerts
    # Timeline entry every N frames
    TIMELINE_SAMPLE_RATE = 5  # every 5th processed frame
    # Max sampled points retained per track (oldest dropped) to bound session size
    TRACK_TIMELINE_MAX = 2000

    def __init__(self, camera: CameraInfo, engine: YOLOPoseEngine, tenant_id: str = "default"):
        self.camera = camera
        self.engine = engine
        self.tenant_id = tenant_id
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[CloudSession] = None
        self._last_frame_time = 0.0
        self._last_checkpoint = 0.0
        self._last_alert_time: dict[int, float] = {}  # track_id -> timestamp
        self._alert_counter = 0
        self._frame_counter = 0
        # Frame-skip accounting (YOLO_SCORE_EVERY): frames pulled vs scored.
        self._pull_counter = 0
        self._frames_skipped = 0
        self._idle_start: Optional[float] = None
        self._identity = get_identity_registry()
        # Latest state for API consumption
        self.latest_poses: list[TrackedPose] = []
        self.latest_persons: list[dict] = []
        self.latest_frame_time: float = 0.0
        # Frame size of the most recent processed frame. Clients need it to map
        # the pixel bbox back to NORMALIZED space (station polygons and the
        # skeleton overlay are both normalized).
        self.frame_width: int = 0
        self.frame_height: int = 0
        # Load/QA instrumentation. Bounded buffers, so a four-hour soak reports
        # percentiles without growing memory without limit.
        self.latency_ms: deque = deque(maxlen=LATENCY_SAMPLE_MAX)
        self.inference_ms: deque = deque(maxlen=LATENCY_SAMPLE_MAX)
        self.source_lag_ms: deque = deque(maxlen=LATENCY_SAMPLE_MAX)
        # Rolling pre-alert clip buffer (JPEG frames) and the clips saved this
        # session, keyed by alert_id.
        self._clip_buffer: deque = deque(maxlen=self._clip_buffer_len())
        self.clips: dict[str, dict] = {}
        # Clips found truncated (no moov/idx1) after the writer was released:
        # deleted, never served, and surfaced in metrics_snapshot so a soak can
        # report the count instead of discovering broken files later.
        self._clips_truncated = 0

    def start(self) -> str:
        """Start processing. Returns the session ID."""
        now = datetime.now()
        session_id = f"CLOUD-{now.strftime('%Y-%m-%d_%H-%M-%S')}"
        self._session = CloudSession(
            session_id=session_id,
            camera_id=self.camera.id,
            camera_name=self.camera.name,
            start_time=time.time(),
            tenant_id=self.tenant_id,
        )
        self._running = True
        self._frame_counter = 0
        self._pull_counter = 0
        self._frames_skipped = 0
        self._idle_start = None
        self._thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
            name=f"cloud-proc-{self.camera.id}",
        )
        self._thread.start()
        logger.info("Cloud processing started for camera %s (session %s)", self.camera.id, session_id)
        return session_id

    def stop(self) -> Optional[CloudSession]:
        """Stop processing. Returns the final session."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._session:
            self._session.end_time = time.time()
            self._session.is_active = False
            self._save_session()
            session = self._session
            self._session = None
            logger.info(
                "Cloud session ended: %s (%d frames, %s)",
                session.session_id,
                session.frame_count,
                session.highest_risk,
            )
            return session
        return None

    @property
    def session(self) -> Optional[CloudSession]:
        return self._session

    def _process_loop(self) -> None:
        """Main processing loop — pulls frames and runs YOLO inference."""
        rtsp = get_rtsp_manager()
        while self._running:
            frame = rtsp.get_frame(self.camera.id)
            if frame is None:
                time.sleep(self.FRAME_WAIT_MS / 1000.0)
                # Check idle timeout
                if (
                    self._idle_start
                    and time.time() - self._idle_start > self.IDLE_TIMEOUT
                ):
                    logger.info(
                        "Camera %s: idle timeout reached, stopping session",
                        self.camera.id,
                    )
                    break
                continue

            self._idle_start = None  # Got a frame — not idle

            # Frame-skip knob (YOLO_SCORE_EVERY, default 1 = score every
            # frame): frames between scores are pulled — that is what keeps the
            # next scored frame fresh against the single-slot buffer — but not
            # scored, not captured into the clip buffer, and not counted in
            # latency. Clip cadence therefore stays equal to score cadence, as
            # it is today when every pull is scored.
            if not self._should_score():
                self._frames_skipped += 1
                continue

            self._capture_clip_frame(frame)

            # How stale the frame was when we picked it up: the single-slot
            # buffer means this is the pipeline falling behind the source.
            source = rtsp.get_camera(self.camera.id)
            if source is not None and source.last_frame_time:
                lag_ms = (time.time() - source.last_frame_time) * 1000.0
                if 0.0 <= lag_ms < 60_000.0:
                    self.source_lag_ms.append(lag_ms)

            # End-to-end per-frame latency: the frame handed to the scorer
            # through to the scored result being stored. This is the number the
            # p95 < 500 ms target applies to.
            frame_started = time.perf_counter()
            try:
                processed = self.engine.process_frame(frame, camera_id=self.camera.id)
                self._handle_result(processed)
                self.latency_ms.append((time.perf_counter() - frame_started) * 1000.0)
            except Exception as exc:
                logger.error(
                    "Camera %s: processing error: %s", self.camera.id, exc, exc_info=True
                )
                time.sleep(0.5)

    def _handle_result(self, result: ProcessedCloudFrame) -> None:
        """Handle a processed frame result."""
        if self._session is None:
            return

        self._frame_counter += 1
        self._session.frame_count += 1
        self.latest_poses = result.tracked_poses
        self._maintain_identities(result)
        self.latest_persons = self.build_persons(result)
        self.latest_frame_time = result.timestamp
        self.frame_width = int(result.frame_width or 0)
        self.frame_height = int(result.frame_height or 0)
        self.inference_ms.append(float(result.inference_ms or 0.0))

        # Track unique persons
        active_ids = {p.track_id for p in result.tracked_poses}
        self._session.person_count = max(self._session.person_count, len(active_ids))

        # Determine dominant risk across all tracked persons
        if result.tracked_poses:
            dominant = max(result.tracked_poses, key=lambda p: p.risk_score)
            risk_level = dominant.risk_level
            risk_score = dominant.risk_score
            task = dominant.task
            track_id = dominant.track_id

            self._session.risk_summary[risk_level] += 1
            self._session.risk_scores.append(risk_score)

            # Timeline entry (sampled)
            if self._frame_counter % self.TIMELINE_SAMPLE_RATE == 0:
                self._session.timeline.append({
                    "timestamp": result.timestamp,
                    "frame": self._frame_counter,
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "task": task,
                    "person_count": len(result.tracked_poses),
                })
                self._sample_track_timelines(result)

            # Alert check (cooldown is per track_id)
            if risk_level in ("MEDIUM", "HIGH"):
                self._check_alert(
                    risk_level, risk_score, task, track_id, result.timestamp,
                    worker_id=self._binding_for(track_id),
                    quality=dict(getattr(dominant, "quality", {}) or {}),
                )
            else:
                # Person is in safe zone — reset idle tracking
                self._idle_start = None

            # No persons detected for a while
            if not result.tracked_poses:
                if self._idle_start is None:
                    self._idle_start = time.time()
        else:
            if self._idle_start is None:
                self._idle_start = time.time()

        # Periodic checkpoint
        now = time.time()
        if now - self._last_checkpoint > self.CHECKPOINT_INTERVAL:
            self._save_checkpoint()
            self._last_checkpoint = now

    def _clip_buffer_len(self) -> int:
        """Frames held for the pre-alert clip.

        Sized from the CONFIGURED inference rate rather than the measured one,
        because the measured rate varies with load; the buffer therefore holds at
        least CLIP_BUFFER_SECONDS of video at the rate the engine is configured
        for, and more than that when the pipeline runs slower.
        """
        fps = max(1, int(getattr(settings, "INFERENCE_FPS", 10) or 10))
        return max(1, int(CLIP_BUFFER_SECONDS * fps))

    def _capture_clip_frame(self, frame) -> None:
        """Append the newest frame to the pre-alert clip buffer.

        Best-effort: clip capture must never break frame processing.
        """
        try:
            height, width = frame.shape[:2]
            if width > CLIP_FRAME_MAX_W:
                scale = CLIP_FRAME_MAX_W / float(width)
                frame = cv2.resize(
                    frame,
                    (CLIP_FRAME_MAX_W, max(1, int(height * scale))),
                    interpolation=cv2.INTER_AREA,
                )
            ok, encoded = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CLIP_JPEG_QUALITY]
            )
            if ok:
                self._clip_buffer.append(encoded.tobytes())
        except Exception as exc:  # noqa: BLE001 - never break a frame for a clip
            logger.debug("Clip frame capture skipped: %s", exc)

    def _save_clip(self, alert_id: str, timestamp: float) -> Optional[dict]:
        """Write the buffered pre-alert frames to a clip for this alert.

        Pre-roll only: the buffer holds the seconds BEFORE the alert, which is
        the evidence a supervisor reviews. There is no post-roll, so the clip
        ends at the alert rather than continuing past it.
        """
        frames = list(self._clip_buffer)
        if not frames:
            return None

        # Free-space watermark before writing: HIGH-alert clips are the one
        # path that can flood disk between backend retention passes (C4 guard).
        try:
            from yolo_cloud import disk_guard
            disk_guard.ensure_free_space(os.path.join(settings.RECORDINGS_DIR, "clips"))
        except Exception as exc:  # noqa: BLE001 - the guard must never block evidence
            logger.warning("Disk guard unavailable (%s)", exc)

        target_dir = os.path.join(settings.RECORDINGS_DIR, "clips", self.camera.id)
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as exc:
            logger.warning("Clip directory unavailable (%s): %s", target_dir, exc)
            return None

        first = cv2.imdecode(np.frombuffer(frames[0], np.uint8), cv2.IMREAD_COLOR)
        if first is None:
            return None
        height, width = first.shape[:2]
        fps = max(1.0, float(getattr(settings, "INFERENCE_FPS", 10) or 10))

        written = 0
        path = ""
        for codec, extension in CLIP_CODECS:
            candidate = os.path.join(target_dir, f"{alert_id}{extension}")
            writer = None
            written = 0
            try:
                # Construction lives INSIDE the try so every writer — including
                # one that fails to open — is released by the finally below.
                # A camera stop or any exception mid-encode must still finalize
                # the container: without release() the MP4 has no moov atom and
                # ffmpeg rejects the whole file (the 3/224 open defect).
                writer = cv2.VideoWriter(
                    candidate, cv2.VideoWriter_fourcc(*codec), fps, (width, height)
                )
                if not writer.isOpened():
                    continue
                for blob in frames:
                    image = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
                    if image is None:
                        continue
                    if image.shape[0] != height or image.shape[1] != width:
                        image = cv2.resize(image, (width, height))
                    writer.write(image)
                    written += 1
            except Exception as exc:  # noqa: BLE001 - one bad frame must not kill the alert
                logger.warning(
                    "Clip write for alert %s interrupted (%s codec): %s",
                    alert_id, codec, exc,
                )
            finally:
                if writer is not None:
                    writer.release()

            if not written:
                # Zero usable frames: drop the stray container, try next codec.
                try:
                    if os.path.exists(candidate):
                        os.remove(candidate)
                except OSError:
                    pass
                continue

            # Post-write verification. The writer can report success and still
            # leave an unplayable container (no moov/idx1), so the file is
            # checked here: a truncated clip is deleted and counted, never
            # served silently, and the next codec gets a chance.
            if not clip_file_complete(candidate):
                self._clips_truncated += 1
                logger.warning(
                    "Clip for alert %s is truncated (no moov/idx1 after %s "
                    "encode) — deleting it and counting as truncated",
                    alert_id, codec,
                )
                try:
                    os.remove(candidate)
                except OSError:
                    pass
                written = 0
                continue

            path = candidate
            break

        if not path:
            logger.warning("Clip save produced no playable clip for alert %s", alert_id)
            return None

        entry = {
            "alert_id": alert_id,
            "camera_id": self.camera.id,
            "path": path,
            "frames": written,
            "fps": fps,
            "duration_s": round(written / fps, 2),
            "bytes": os.path.getsize(path),
            "created_at": timestamp,
            "post_roll": False,
        }
        self.clips[alert_id] = entry
        logger.info("Clip saved for alert %s: %s (%d frames)", alert_id, path, written)
        return entry

    def _should_score(self) -> bool:
        """True when this pulled frame is due to be scored (frame-skip knob).

        Counts every pulled frame and scores every ``YOLO_SCORE_EVERY``-th,
        starting with the first pull, so a session always begins with a scored
        frame. Values < 1 are clamped to 1 (score everything).
        """
        self._pull_counter += 1
        every = max(1, int(getattr(settings, "YOLO_SCORE_EVERY", 1) or 1))
        return (self._pull_counter - 1) % every == 0

    def metrics_snapshot(self) -> dict:
        """Processing metrics for QA / soak reporting.

        ``dropped_frames`` is decoded minus processed: ``get_frame`` returns only
        the LATEST frame, so any frame the decoder overwrote before this
        processor read it was dropped. If the consumer ever outpaces the decoder
        it re-processes one image, which shows up as ``repeat_frames`` with
        ``processed > decoded`` — so the drop ratio is never read from that case
        without noticing.
        """
        decoded = int(getattr(self.camera, "frame_count", 0) or 0)
        processed = int(self._frame_counter)
        skipped = int(self._frames_skipped)
        # Frames intentionally skipped by YOLO_SCORE_EVERY are NOT decoder
        # drops — subtract them so the knob never reads as frame loss.
        dropped = max(0, decoded - processed - skipped)
        over_budget = sum(1 for v in self.latency_ms if v > LATENCY_BUDGET_MS)
        return {
            "camera_id": self.camera.id,
            "decoded_frames": decoded,
            "processed_frames": processed,
            "dropped_frames": dropped,
            "repeat_frames": max(0, processed - decoded),
            "drop_rate": round(dropped / decoded, 4) if decoded else 0.0,
            "latency_ms": percentiles(self.latency_ms),
            "inference_ms": percentiles(self.inference_ms),
            "source_lag_ms": percentiles(self.source_lag_ms),
            "latency_budget_ms": LATENCY_BUDGET_MS,
            "latency_over_budget_frames": over_budget,
            "fps": round(float(getattr(self.camera, "fps", 0.0) or 0.0), 2),
            "frames_scored": processed,
            "score_every": max(1, int(getattr(settings, "YOLO_SCORE_EVERY", 1) or 1)),
            "frames_skipped": int(self._frames_skipped),
            "clips_saved": len(self.clips),
            "clips_truncated": self._clips_truncated,
        }

    def _binding_for(self, track_id: int) -> Optional[str]:
        """Worker id currently bound to this track (badge or verified face)."""
        try:
            return self._identity.binding_for(self.camera.id, int(track_id))
        except Exception:  # noqa: BLE001 - identity is best-effort
            return None

    def build_persons(self, result: ProcessedCloudFrame) -> list[dict]:
        """Per-track snapshot for the multi-worker tile grid / WS payload.

        One entry per active ``track_id``; ``bbox`` is in PIXELS ``[x, y, w, h]``
        (the engine works in normalized xyxy). ``worker_id`` is null until an
        identity is bound via badge/QR or a consenting face match.
        """
        fw = float(result.frame_width or 1)
        fh = float(result.frame_height or 1)
        persons = []
        for p in result.tracked_poses:
            x1, y1, x2, y2 = p.bbox
            persons.append({
                "track_id": int(p.track_id),
                "bbox": [
                    int(round(x1 * fw)), int(round(y1 * fh)),
                    int(round((x2 - x1) * fw)), int(round((y2 - y1) * fh)),
                ],
                "risk_score": round(float(p.risk_score), 1),
                "risk_level": p.risk_level,
                "confidence": round(float(p.confidence), 3),
                "task": p.task,
                # Joint angles (neck/trunk/shoulder/...) in degrees for THIS
                # track, so two workers in one frame never share figures.
                "angles": {
                    str(k): round(float(v), 1)
                    for k, v in (getattr(p, "joint_angles", None) or {}).items()
                },
                # The 17 COCO keypoints as [x, y, conf] in NORMALIZED frame
                # coordinates, for the per-tile skeleton overlay. Index-aligned
                # with COCO_17 (a malformed point becomes [0, 0, 0], never a gap).
                "keypoints": [
                    [round(float(kp[0]), 4), round(float(kp[1]), 4), round(float(kp[2]), 3)]
                    if len(kp) >= 3 else [0.0, 0.0, 0.0]
                    for kp in list(getattr(p, "keypoints", None) or [])[:17]
                ],
                # Display-only capture-quality flags (low_light/occluded/too_small);
                # never inputs to risk or task scoring.
                "quality": dict(getattr(p, "quality", {}) or {}),
                # Workstation this person is standing at (null when no ROI covers
                # their centroid), so a tile can be labelled by station rather
                # than only by track_id.
                "station_id": getattr(p, "station_id", None),
                "station_name": getattr(p, "station_name", None),
                "worker_id": self._binding_for(p.track_id),
                "last_seen": result.timestamp,
            })
        return persons

    def _maintain_identities(self, result: ProcessedCloudFrame) -> None:
        """Keep identity state fresh each frame.

        Bound tracks refresh their remembered box; unbound tracks get one chance
        to re-attach to a recently-seen identity (a worker who left the frame and
        came back has a brand-new track_id). Best-effort: never breaks processing.
        """
        for p in result.tracked_poses:
            try:
                worker_id = self._identity.binding_for(self.camera.id, p.track_id)
                if worker_id:
                    self._identity.remember(
                        self.camera.id, worker_id, p.track_id, list(p.bbox),
                    )
                else:
                    self._identity.try_rebind(
                        self.camera.id, p.track_id, list(p.bbox),
                    )
            except Exception:  # noqa: BLE001 - identity is best-effort
                continue

    def refresh_person_bindings(self) -> None:
        """Overlay the latest identity bindings onto the cached persons snapshot.

        Without this a badge scan only shows up on the *next* processed frame;
        reading live state should reflect a scan immediately.
        """
        for person in self.latest_persons:
            person["worker_id"] = self._binding_for(person["track_id"])

    def _sample_track_timelines(self, result: ProcessedCloudFrame) -> None:
        """Append one sampled point per active track, keyed by track_id."""
        if self._session is None:
            return
        for p in result.tracked_poses:
            series = self._session.track_timelines.setdefault(str(int(p.track_id)), [])
            series.append({
                "timestamp": result.timestamp,
                "frame": self._frame_counter,
                "risk_level": p.risk_level,
                "risk_score": round(float(p.risk_score), 1),
                "confidence": round(float(p.confidence), 3),
                "task": p.task,
                "quality": dict(getattr(p, "quality", {}) or {}),
                "station_id": getattr(p, "station_id", None),
                "worker_id": self._binding_for(p.track_id),
            })
            if len(series) > self.TRACK_TIMELINE_MAX:
                del series[: len(series) - self.TRACK_TIMELINE_MAX]

    def _check_alert(
        self, risk_level: str, risk_score: float, task: str, track_id: int,
        timestamp: float, worker_id: Optional[str] = None,
        quality: Optional[dict] = None,
    ) -> None:
        """Check if we should fire an alert (cooldown is keyed by track_id)."""
        last = self._last_alert_time.get(track_id, 0)
        if timestamp - last < self.ALERT_COOLDOWN * (1.0 / settings.INFERENCE_FPS):
            return

        self._alert_counter += 1
        alert = CloudAlert(
            alert_id=f"ALT-{self._alert_counter:06d}",
            camera_id=self.camera.id,
            camera_name=self.camera.name,
            session_id=self._session.session_id,
            severity=risk_level,
            message=self._generate_alert_message(risk_level, task),
            timestamp=timestamp,
            risk_score=risk_score,
            task=task,
            track_id=track_id,
            worker_id=worker_id,
            tenant_id=self.tenant_id,
        )
        alert_dict = alert.to_dict()
        if risk_level == "HIGH":
            # HIGH alerts carry the pre-alert clip; MEDIUM is alert-only, so a
            # long medium-risk stretch cannot fill the disk with clips.
            clip = self._save_clip(alert.alert_id, timestamp)
            if clip:
                alert_dict["clip"] = clip
        if quality:
            # Display-only capture-quality flags at alert time (helps the
            # supervisor judge whether low light / occlusion caused the alert).
            alert_dict["quality"] = dict(quality)
        self._session.alerts.append(alert_dict)
        self._last_alert_time[track_id] = timestamp
        # Accelerator only: the 5 Hz WS snapshot stays the guaranteed path, so a
        # failure here is logged and dropped rather than retried.
        try:
            from yolo_cloud.api import push_alert_event

            push_alert_event(alert_dict)
        except Exception as exc:  # noqa: BLE001 - never break ingest for a push
            logger.debug("Alert event push unavailable: %s", exc)
        # Persist alert to PostgreSQL
        try:
            from yolo_cloud import storage
            if storage.pg_enabled():
                storage.save_alert(alert_dict, self.tenant_id)
        except Exception:
            pass
        logger.warning(
            "ALERT [%s] camera=%s worker=%d task=%s score=%.1f",
            risk_level,
            self.camera.id,
            track_id,
            task,
            risk_score,
        )

        # Send email/Slack notifications (non-blocking)
        try:
            from yolo_cloud.notifications import send_alert_notification
            send_alert_notification(
                title=f"[{risk_level}] {self.camera.name}",
                message=self._generate_alert_message(risk_level, task),
                severity=risk_level,
                session_id=self._session.session_id,
                camera_id=self.camera.id,
                risk_score=risk_score,
            )
            # Send webhooks
            try:
                from yolo_cloud.webhooks import send_webhook
                send_webhook(
                    tenant_id=self.tenant_id,
                    event="alert.fired",
                    alert_data=alert.to_dict(),
                )
            except Exception:
                pass
        except Exception as e:
            logger.debug("Notification send failed (non-fatal): %s", e)

    def _generate_alert_message(self, risk_level: str, task: str) -> str:
        """Generate a human-readable alert message."""
        messages = {
            "HIGH": {
                "lifting": "HIGH risk — worker lifting with bent back. Correct immediately.",
                "reaching": "HIGH risk — worker overextending overhead. Reposition.",
                "assembly": "HIGH risk — sustained awkward assembly posture.",
                "standing": "HIGH risk — worker standing with poor posture alignment.",
                "sitting": "HIGH risk — worker seated in strained position.",
                "unknown": "HIGH risk — unrecognized task with unsafe posture.",
            },
            "MEDIUM": {
                "lifting": "MEDIUM risk — lifting posture approaching unsafe range.",
                "reaching": "MEDIUM risk — arm elevation causing shoulder strain.",
                "assembly": "MEDIUM risk — assembly posture needs adjustment.",
                "standing": "MEDIUM risk — standing posture showing early fatigue.",
                "sitting": "MEDIUM risk — seated position causing trunk strain.",
                "unknown": "MEDIUM risk — posture requires review.",
            },
        }
        return messages.get(risk_level, {}).get(task, f"{risk_level} risk detected during {task}.")

    def _save_session(self) -> None:
        """Save the completed session to disk and PostgreSQL."""
        if not self._session:
            return
        session_dict = self._session.to_dict()
        # Save to PostgreSQL
        try:
            from yolo_cloud import storage
            if storage.pg_enabled():
                storage.save_session(session_dict, self.tenant_id)
        except Exception as exc:
            logger.debug("PostgreSQL session save failed (non-fatal): %s", exc)
        # Save to disk (backup)
        try:
            session_dir = os.path.join(
                settings.SESSIONS_DIR, f"cloud_{self.camera.id}"
            )
            os.makedirs(session_dir, exist_ok=True)
            filename = f"{self._session.session_id}.json"
            path = os.path.join(session_dir, filename)
            with open(path, "w") as f:
                json.dump(session_dict, f, indent=2)
            logger.info("Cloud session saved: %s", path)
        except Exception as exc:
            logger.error("Failed to save cloud session: %s", exc)

    def _save_checkpoint(self) -> None:
        """Save an in-progress checkpoint."""
        if not self._session:
            return
        try:
            checkpoint_dir = os.path.join(settings.SESSIONS_DIR, ".cloud_checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            path = os.path.join(
                checkpoint_dir, f"{self._session.session_id}.json"
            )
            with open(path, "w") as f:
                json.dump(self._session.to_dict(), f, indent=2)
        except Exception:
            pass


class CloudIngestionService:
    """Manages all cloud camera processors."""

    def __init__(self):
        self._processors: dict[str, CloudCameraProcessor] = {}
        self._lock = threading.Lock()
        self._rtsp = get_rtsp_manager()
        self._engine = get_pose_engine()
        self._alert_history: deque = deque(maxlen=1000)

    def initialize(self) -> None:
        """Initialize the YOLO model and start configured cameras."""
        logger.info("Initializing YOLO Cloud Ingestion Service...")
        self._engine.initialize()

        # Auto-start configured cameras
        for cam_config in settings.RTSP_CAMERAS:
            cam_id = cam_config.get("id", "")
            cam_name = cam_config.get("name", "IP Camera")
            cam_url = cam_config.get("url", "")
            if cam_id and cam_url:
                self.add_and_start_camera(cam_id, cam_name, cam_url)

        logger.info(
            "YOLO Cloud ready — %d cameras configured", len(settings.RTSP_CAMERAS)
        )

    def add_and_start_camera(
        self, camera_id: str, name: str, url: str, tenant_id: str = "default"
    ) -> dict:
        """Add a camera, start RTSP ingestion, and start processing."""
        # Add to RTSP manager
        self._rtsp.add_camera(camera_id, name, url, auto_start=True)

        # Start cloud processor
        with self._lock:
            if camera_id in self._processors:
                # Stop existing processor
                self._processors[camera_id].stop()

            camera = self._rtsp.get_camera(camera_id)
            processor = CloudCameraProcessor(camera, self._engine, tenant_id=tenant_id)
            session_id = processor.start()
            self._processors[camera_id] = processor

        return {
            "camera_id": camera_id,
            "session_id": session_id,
            "status": "started",
        }

    def stop_camera(self, camera_id: str) -> Optional[dict]:
        """Stop processing and RTSP ingestion for a camera."""
        with self._lock:
            processor = self._processors.pop(camera_id, None)
            if processor:
                session = processor.stop()
                self._rtsp.stop_camera(camera_id)
                return session.to_dict() if session else None
        return None

    def remove_camera(self, camera_id: str) -> bool:
        """Remove a camera entirely."""
        self.stop_camera(camera_id)
        return self._rtsp.remove_camera(camera_id)

    def get_camera_state(self, camera_id: str) -> Optional[dict]:
        """Get the current state of a camera's cloud processing."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor is None:
                return None
            camera = self._rtsp.get_camera(camera_id)
            processor.refresh_person_bindings()
            return {
                "camera_id": camera_id,
                "camera_name": camera.name if camera else "",
                "camera_state": camera.state.value if camera else "disconnected",
                "session_id": processor.session.session_id if processor.session else None,
                "is_active": processor._running,
                "frame_count": processor._frame_counter,
                "latest_poses": [
                    {
                        "track_id": p.track_id,
                        "risk_level": p.risk_level,
                        "risk_score": p.risk_score,
                        "task": p.task,
                        "confidence": p.confidence,
                    }
                    for p in processor.latest_poses
                ],
                # Per-track snapshots for the multi-worker tile grid: one entry
                # per active track_id, bbox in PIXELS [x, y, w, h].
                "persons": processor.latest_persons,
                "person_count": len(processor.latest_poses),
                "frame_width": processor.frame_width,
                "frame_height": processor.frame_height,
                "id_switch_count": processor._identity.switch_count(camera_id),
                "fps": camera.fps if camera else 0,
            }

    def get_clip(self, camera_id: str, alert_id: str) -> Optional[dict]:
        """Manifest entry for a saved pre-alert clip, or None.

        Falls back to a filesystem lookup so a clip stays downloadable after its
        camera has been stopped or removed.
        """
        with self._lock:
            processor = self._processors.get(camera_id)
            entry = None
            if processor is not None and alert_id in processor.clips:
                entry = dict(processor.clips[alert_id])
        # Verified, not just present: a file can outlive the process that was
        # writing it (a hard kill skips both release() and the save-time check),
        # so recovery from disk re-verifies the container instead of handing a
        # supervisor a file ffmpeg will reject.
        if entry and clip_file_complete(entry.get("path", "")):
            return entry

        target_dir = os.path.join(settings.RECORDINGS_DIR, "clips", str(camera_id))
        for _codec, extension in CLIP_CODECS:
            candidate = os.path.join(target_dir, f"{alert_id}{extension}")
            if os.path.exists(candidate) and clip_file_complete(candidate):
                return {
                    "alert_id": alert_id,
                    "camera_id": camera_id,
                    "path": candidate,
                    "bytes": os.path.getsize(candidate),
                    "recovered_from_disk": True,
                }
        return None

    def get_processing_metrics(self) -> list[dict]:
        """Per-camera processing metrics (latency percentiles, drop rate, lag).

        Read-only snapshot for QA / soak reporting; safe to call while cameras
        are running.
        """
        with self._lock:
            return [p.metrics_snapshot() for p in self._processors.values()]

    def get_camera_persons(self, camera_id: str) -> Optional[dict]:
        """Live per-track persons for one camera (multi-worker tile source)."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor is None:
                return None
            session = processor.session
            processor.refresh_person_bindings()
            return {
                "camera_id": camera_id,
                "camera_name": processor.camera.name,
                "session_id": session.session_id if session else None,
                "is_active": processor._running,
                "frame_count": processor._frame_counter,
                "person_count": len(processor.latest_persons),
                "persons": processor.latest_persons,
                "frame_width": processor.frame_width,
                "frame_height": processor.frame_height,
                "id_switch_count": processor._identity.switch_count(camera_id),
                "updated_at": processor.latest_frame_time,
            }

    def get_person_timeline(
        self, track_id: int, limit: int = 100,
        camera_id: Optional[str] = None, session_id: Optional[str] = None,
    ) -> dict:
        """Sampled per-track risk series, merged across sessions.

        Timeline points are stored per ``(session_id, track_id)``; this flattens
        them into one newest-``limit`` series and also reports which sessions
        contributed.
        """
        key = str(int(track_id))
        points: list[dict] = []
        contributing: list[dict] = []
        for sess in self.get_sessions(limit=1000):
            if session_id and sess.get("session_id") != session_id:
                continue
            if camera_id and sess.get("camera_id") != camera_id:
                continue
            series = (sess.get("track_timelines") or {}).get(key) or []
            if not series:
                continue
            contributing.append({
                "session_id": sess.get("session_id"),
                "camera_id": sess.get("camera_id"),
                "sample_count": len(series),
            })
            for pt in series:
                points.append({
                    "session_id": sess.get("session_id"),
                    "camera_id": sess.get("camera_id"),
                    **pt,
                })
        points.sort(key=lambda p: p.get("timestamp") or 0)
        if limit and limit > 0:
            points = points[-limit:]
        return {
            "track_id": int(track_id),
            "camera_id": camera_id,
            "session_id": session_id,
            "point_count": len(points),
            "sessions": contributing,
            "points": points,
        }

    def get_all_cameras(self) -> list[dict]:
        """Get state of all cameras."""
        cameras = self._rtsp.get_all_cameras()
        result = []
        for cam in cameras:
            state = self.get_camera_state(cam.id)
            if state:
                result.append(state)
            else:
                result.append({
                    "camera_id": cam.id,
                    "camera_name": cam.name,
                    "camera_state": cam.state.value,
                    "is_active": False,
                })
        return result

    def get_dashboard(self) -> dict:
        """Get aggregated dashboard data across all cameras."""
        all_cameras = self.get_all_cameras()
        total_persons = sum(c.get("person_count", 0) for c in all_cameras)
        active_cameras = sum(1 for c in all_cameras if c.get("is_active"))

        # Aggregate risk levels
        risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for cam in all_cameras:
            for pose in cam.get("latest_poses", []):
                level = pose.get("risk_level", "LOW")
                risk_counts[level] = risk_counts.get(level, 0) + 1

        # Flatten per-camera persons so a caller can drive a tile grid from one place.
        persons = []
        for cam in all_cameras:
            for person in cam.get("persons", []):
                persons.append({"camera_id": cam.get("camera_id"), **person})

        return {
            "total_cameras": len(all_cameras),
            "active_cameras": active_cameras,
            "total_workers": total_persons,
            "risk_distribution": risk_counts,
            "cameras": all_cameras,
            "persons": persons,
            "id_switch_count": get_identity_registry().switch_count(),
        }

    def get_sessions(self, limit: int = 50) -> list[dict]:
        """Get recent cloud sessions across all cameras."""
        sessions = []
        for processor in self._processors.values():
            if processor.session:
                sessions.append(processor.session.to_dict())

        # Also load from disk
        try:
            for cam_dir in os.listdir(settings.SESSIONS_DIR):
                if not cam_dir.startswith("cloud_"):
                    continue
                dir_path = os.path.join(settings.SESSIONS_DIR, cam_dir)
                if not os.path.isdir(dir_path):
                    continue
                for fname in os.listdir(dir_path):
                    if fname.startswith("CLOUD-") and fname.endswith(".json"):
                        fpath = os.path.join(dir_path, fname)
                        try:
                            with open(fpath) as f:
                                sessions.append(json.load(f))
                        except Exception:
                            pass
        except Exception:
            pass

        # Sort by start time, most recent first
        sessions.sort(key=lambda s: s.get("start_time", ""), reverse=True)
        return sessions[:limit]

    def get_alerts(self, limit: int = 100) -> list[dict]:
        """Get recent alerts across all cameras."""
        alerts = []
        for processor in self._processors.values():
            if processor.session:
                alerts.extend(processor.session.alerts)
        alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
        return alerts[:limit]

    def shutdown(self) -> None:
        """Shutdown all processors and RTSP streams."""
        with self._lock:
            for processor in self._processors.values():
                processor.stop()
            self._processors.clear()
        self._rtsp.stop_all()
        logger.info("Cloud ingestion service shut down")


# Global singleton
_service: Optional[CloudIngestionService] = None


def get_cloud_service() -> CloudIngestionService:
    global _service
    if _service is None:
        _service = CloudIngestionService()
    return _service
