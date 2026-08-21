"""Live monitoring service — controls the CV pipeline lifecycle.

Owns the webcam and PoseEngine. Runs processing in a background thread.
Maintains LiveState with the latest processed results for the API to read.

Pipeline: Camera -> PoseEngine -> ProcessedFrame -> ContextIntelligenceEngine -> ContextSnapshot -> LiveState
Events: EventBus publishes lifecycle and snapshot events for future consumers.
Alerts: AlertEngine subscribes to ContextSnapshotCreatedEvent and produces alerts.
History: HistoryEngine subscribes to ContextSnapshotCreatedEvent and records snapshots.
Recommendations: RecommendationEngine subscribes to ContextSnapshotCreatedEvent and produces recommendations.
"""

import logging
import os
import sys
import time
import threading
import json
from collections import deque
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.pose_engine import PoseEngine, ProcessedFrame, RISK_LEVELS
from backend.services.session_analytics import (
    SessionAnalytics,
    save_session_checkpoint,
    save_session_summary,
)
from backend.context.engine import ContextIntelligenceEngine
from backend.events.event_bus import EventBus, get_event_bus
from backend.events.events import (
    SessionStartedEvent,
    SessionEndedEvent,
    ContextSnapshotCreatedEvent,
)
from backend.alerts.engine import AlertEngine
from backend.history.engine import HistoryEngine
from backend.recommendations.engine import RecommendationEngine

# Canonical definitions live in backend.core.types.
# Re-exported here for backward compatibility.
from backend.core.types import LiveState  # noqa: F401
try:
    from app.services.pose_overlay import draw_skeleton
except ImportError:  # pragma: no cover - local layout where only the repo root is on sys.path
    from backend_api.app.services.pose_overlay import draw_skeleton

try:
    from app.services.person_detector import detect_persons, PERSON_DETECT_INTERVAL_S
except ImportError:  # pragma: no cover - local layout where only the repo root is on sys.path
    from backend_api.app.services.person_detector import detect_persons, PERSON_DETECT_INTERVAL_S

try:
    from app.services.worker_faces import identify_persons_in_frame
except ImportError:  # pragma: no cover - local layout where only the repo root is on sys.path
    from backend_api.app.services.worker_faces import identify_persons_in_frame

try:
    from app.services.liveness import FaceLivenessTracker
except ImportError:  # pragma: no cover - local layout where only the repo root is on sys.path
    from backend_api.app.services.liveness import FaceLivenessTracker

RECORDINGS_DIR = os.environ.get(
    "RECORDINGS_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")),
)

# Bound the in-memory live timeline so long sessions can't grow it unboundedly.
# ~20k entries at 10 fps covers ~33 minutes of history for the LiveMonitoring
# timeline bar; the full record is persisted to disk on stop anyway.
_TIMELINE_MAX = 20000
# Consecutive `cap.read()` failures before the capture loop attempts to reopen
# the camera source. Factory IP cameras (RTSP) drop constantly — a single
# failed read is normal jitter, but a persistent failure means the stream is
# dead and must be reopened with backoff instead of spinning forever.
_CAPTURE_FAILURE_THRESHOLD = 3
_CAPTURE_RECONNECT_BASE_S = 0.5
_CAPTURE_RECONNECT_MAX_S = 10.0

# Capture/processing decoupling (Tier 0). A dedicated capture thread reads the
# camera at its native rate into a bounded ring buffer; the process thread pops
# the LATEST frame and drops the backlog, so a slow pose inference can never
# stall the raw video recorder or let the camera buffer overflow. 8 frames is
# ~0.25s of slack at 30fps — enough to absorb inference jitter without ever
# serving a stale frame.
_FRAME_QUEUE_MAX = 8

# Cap how often the capture loop runs full pose inference. MediaPipe at the
# camera's native fps (usually 30) saturates a CPU core and starves every API
# request (Python GIL), which made the whole site feel frozen during live
# monitoring. 15 fps is plenty for posture risk; the raw feed still records
# every frame for video. Override with POSE_PROCESS_FPS.
def _process_fps_target() -> float:
    try:
        return max(2.0, min(30.0, float(os.environ.get("POSE_PROCESS_FPS", "15"))))
    except (TypeError, ValueError):
        return 15.0


# Downscale the pose-inference input below the camera's native resolution.
# MediaPipe at 1280x720 takes ~380 ms/frame on this CPU (~2.6 fps); at ~640
# wide it drops to ~300 ms and at ~480 wide ~180 ms (~5.6 fps) — the skeleton
# then refreshes ~2x faster so it tracks the person instead of visibly
# lagging. Default is 480 wide for maximum overlay fps (the whole point of
# this knob); keypoints are normalized to 0-1 and the overlay is drawn on the
# full-resolution display frame, so inference resolution does not affect
# output quality. Override with POSE_INFERENCE_WIDTH.
def _inference_max_width() -> int:
    try:
        return max(256, int(os.environ.get("POSE_INFERENCE_WIDTH", "320")))
    except (TypeError, ValueError):
        return 480


def _resolve_camera_source(camera_index: int, camera_id: str | None) -> int | str:
    """Resolve the actual camera source to open with ``cv2.VideoCapture``.

    Priority:
      1. ``camera_id`` matching a configured ``CAMERA_SOURCES`` entry -> its URL
      2. ``camera_id`` that is itself an RTSP/HTTP URL -> used as-is
      3. ``camera_id == "demo"`` -> ``DEMO_VIDEO_PATH`` (sales demo: replay a
         recorded video through the live pipeline, no camera needed)
      4. ``camera_id`` naming an existing local video file -> used as-is
      5. numeric ``camera_id`` -> int index
      6. fallback -> ``camera_index``
    """
    if camera_id:
        cid = camera_id.strip()
        from app.core.config import settings
        for cam in settings.CAMERA_SOURCES:
            if cam["id"] == cid:
                return cam["url"]
        if cid.lower().startswith(("rtsp://", "rtmp://", "http://", "https://")):
            return cid
        if cid == "demo":
            # Empty path -> open fails with a clear error in start_session.
            return os.environ.get("DEMO_VIDEO_PATH", "") or "demo"
        if os.path.isfile(cid):
            return cid
        try:
            return int(cid)
        except (ValueError, TypeError):
            pass
    return camera_index


def clean_feature_values(features: dict) -> dict:
    """Return a JSON-safe copy of a feature dict.

    Coerces numpy scalars to plain floats (``float32``/``float64`` are not
    JSON-serializable in all cases) and maps NaN to ``None`` so WebSocket
    pushes / API payloads never break JSON serialization.
    """
    out = {}
    for key, value in (features or {}).items():
        try:
            out[key] = None if (value is None or value != value) else float(value)
        except (TypeError, ValueError):
            out[key] = None
    return out


def build_ws_payload(state) -> dict:
    """Serialize ``LiveState`` into a JSON-safe dashboard payload (no frame).

    All scalar fields are coerced to plain floats and feature values to
    float/None so WebSocket pushes can never break JSON serialization with
    numpy scalars or NaN.
    """
    def _f(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    return {
        "session_active": bool(state.session_active),
        "session_id": state.session_id,
        "risk_level": state.risk_level,
        "risk_score": _f(state.risk_score),
        "confidence": _f(state.confidence),
        "person_detected": bool(state.person_detected),
        "task_name": state.task_name,
        "task_confidence": _f(state.task_confidence),
        "task_duration_seconds": _f(state.task_duration_seconds),
        "issues": list(state.issues),
        "worker_recommendation": state.worker_recommendation,
        "supervisor_recommendation": state.supervisor_recommendation,
        "fps": _f(state.fps),
        "inference_latency_ms": _f(state.inference_latency_ms),
        "timestamp": state.timestamp,
        "camera_status": state.camera_status,
        "camera_reconnecting": bool(getattr(state, "camera_reconnecting", False)),
        "frame_width": state.frame_width,
        "frame_height": state.frame_height,
        "features": clean_feature_values(state.features),
        # Tier 3 framing intelligence + person count
        "framing": dict(getattr(state, "framing", {}) or {}),
        "person_count": int(getattr(state, "person_count", 1) or 1),
        # YOLO person boxes + face-recognized worker identity.
        "person_boxes": list(getattr(state, "person_boxes", []) or []),
        "person_identities": [
            dict(r) for r in (getattr(state, "person_identities", []) or [])
        ],
        "identified_worker": dict(getattr(state, "identified_worker", {}) or {}),
        # Per-person risk (station view): every detected pose, primary marked.
        "person_risks": [
            dict(r) for r in (getattr(state, "person_risks", []) or [])
        ],
    }


def export_recommendations_from_bundle(rec_bundle) -> list[dict]:
    """Flatten RecommendationEngine.export()'s dict-shaped bundle into timeline rows.

    ``export()`` serializes via ``RecommendationBundle.to_dict()``, so each
    recommendation is a plain dict — access by key, never by attribute.
    """
    if not rec_bundle:
        return []
    return [
        {
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "category": r.get("category", ""),
            "priority": r.get("priority", ""),
        }
        for r in rec_bundle.get("bundle", {}).get("recommendations", [])
        if isinstance(r, dict)
    ]


class _SessionVideoRecorder:
    """Best-effort MP4 sidecar recorder for the raw camera feed."""

    def __init__(self, output_path: str, width: int, height: int, fps: float):
        self.output_path = os.path.abspath(output_path)
        self.width = width
        self.height = height
        self.fps = fps if 1.0 <= fps <= 60.0 else 15.0
        self.writer: Optional[cv2.VideoWriter] = None
        self.codec: Optional[str] = None
        self.frame_count = 0
        self.status = "pending"
        self.error: Optional[str] = None
        try:
            self._simulate_failure_after_frames = int(
                os.environ.get("ERGOVIGILANCE_VIDEO_FAIL_AFTER_FRAMES", "0") or "0"
            )
        except ValueError as exc:
            logger.warning("Failed to parse ERGOVIGILANCE_VIDEO_FAIL_AFTER_FRAMES, defaulting to 0: %s", exc)
            self._simulate_failure_after_frames = 0

    def start(self) -> None:
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        # Prefer H.264 for long-session storage. Some OpenCV builds lack an
        # encoder, so fall back to MPEG-4 Part 2 while keeping the MP4 container.
        for codec in ("avc1", "H264", "mp4v"):
            writer = cv2.VideoWriter(
                self.output_path,
                cv2.VideoWriter_fourcc(*codec),
                self.fps,
                (self.width, self.height),
            )
            if writer.isOpened():
                self.writer = writer
                self.codec = codec
                self.status = "recording"
                return
            writer.release()

        self.status = "failed"
        self.error = "Unable to open MP4 VideoWriter with avc1/H264/mp4v codecs"

    def write(self, frame: np.ndarray) -> None:
        if self.status != "recording" or self.writer is None:
            return
        try:
            if (
                self._simulate_failure_after_frames > 0
                and self.frame_count >= self._simulate_failure_after_frames
            ):
                raise OSError("Simulated video write failure")

            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))
            self.writer.write(frame)
            self.frame_count += 1
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
            self._release_writer()

    def finalize(self) -> dict:
        if self.status == "recording":
            self.status = "completed"
        self._release_writer()

        has_file = os.path.exists(self.output_path) and os.path.getsize(self.output_path) > 0
        if self.status == "completed" and not has_file:
            self.status = "failed"
            self.error = "Video writer closed without producing a non-empty file"

        return {
            "video_path": self.output_path if self.status == "completed" and has_file else None,
            "video_recording_status": self.status,
            "video_recording_error": self.error,
            "video_frame_count": self.frame_count,
            "video_codec": self.codec,
        }

    def _release_writer(self) -> None:
        if self.writer is not None:
            self.writer.release()
            self.writer = None


class LiveMonitoringService:
    """Controls the live posture monitoring pipeline."""

    def __init__(self, model_path: str, sessions_dir: Optional[str] = None, event_bus: Optional[EventBus] = None, db_enabled: bool = True):
        self.model_path = model_path
        self.sessions_dir = sessions_dir or os.path.join(
            os.path.dirname(model_path), "..", "outputs", "sessions"
        )
        self.engine = PoseEngine(model_path)
        self.context_engine = ContextIntelligenceEngine()
        self.event_bus = event_bus or get_event_bus()
        self.alert_engine = AlertEngine(self.event_bus, db_enabled=db_enabled)
        self.history_engine = HistoryEngine(self.event_bus)
        self.recommendation_engine = RecommendationEngine(
            self.event_bus, self.alert_engine, self.history_engine
        )
        self.cap: Optional[cv2.VideoCapture] = None
        self.thread: Optional[threading.Thread] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_queue: deque[np.ndarray] = deque(maxlen=_FRAME_QUEUE_MAX)
        self._running = False
        self._lock = threading.Lock()
        self.state = LiveState()
        self.analytics = SessionAnalytics()
        self._fps_start = time.perf_counter()
        self._fps_count = 0
        self._session_duration: float = 0.0
        self._last_frame_time: float = 0.0
        self.current_worker_id: Optional[str] = None
        self.current_created_by_user_id: Optional[int] = None
        self.current_camera_index: Optional[int] = None
        self.current_camera_id: Optional[str] = None
        self.current_camera_source: int | str | None = None
        # Demo mode: the source is a video FILE (DEMO_VIDEO_PATH or a direct
        # path) — the capture loop loops it instead of treating end-of-file as
        # a camera failure, and throttles to the file's own frame rate.
        self._is_demo_source: bool = False
        self._demo_fps: float = 15.0
        self.current_session_timestamp: Optional[str] = None
        self.video_recorder: Optional[_SessionVideoRecorder] = None
        self.video_recording_metadata: dict = {}
        self._timeline: deque = deque(maxlen=_TIMELINE_MAX)
        self._frame_counter: int = 0
        self._capture_counter: int = 0
        self._last_process_time: float = 0.0
        self._process_interval: float = 1.0 / _process_fps_target()
        # History of the last few processed poses, tagged with the capture
        # counter at the time they were computed. The MJPEG generator
        # interpolates keypoints between these so the skeleton tracks the
        # body smoothly at video rate even though inference runs slower.
        self._pose_history: deque = deque(maxlen=4)
        self._ai_explanation_cache: str = ""
        self._ai_expl_last_attempt: float = 0.0
        # Guards against spawning overlapping AI-explanation threads (one in
        # flight at a time; a hung Ollama call can never accumulate threads).
        self._ai_expl_running: bool = False
        # Person detection + face recognition state. Detection is throttled to
        # PERSON_DETECT_INTERVAL_S so YOLO never contends with pose inference.
        self._person_detect_last: float = 0.0
        self._person_boxes: list = []
        # One entry per detected person: {"box": {...}, "worker_id", "name",
        # "confidence", "matched"} — ALL persons, not just the primary.
        self._person_identities: list = []
        # Primary (largest) recognized worker — kept for the dashboard card.
        self._identified_worker: dict = {}
        self._worker_name_cache: dict[str, str] = {}
        # Anti-photo-spoof liveness. Sampled at its own faster throttle (the
        # identity pass runs every ~2s; blinks last ~150-400ms and would be
        # missed at that rate). FaceLivenessTracker associates boxes across
        # samples by IoU and counts blinks + face-region motion per person.
        self._liveness_tracker = FaceLivenessTracker()
        self._liveness_last: float = 0.0
        self._liveness_interval: float = 0.4
        # Background thread handles for non-blocking person detection + liveness
        self._person_detect_thread = None
        self._person_detect_result = None
        self._liveness_thread = None
        # When the primary identified face is flagged as a spoof (photo /
        # screen), the posture skeleton must NOT be drawn over it — showing
        # MediaPipe landmarks on a photo makes it look like a monitored,
        # physically-present worker. Re-computed each processed frame.
        self._skeleton_suppressed: bool = False
        # Crash-safe session checkpoints: periodically persist the in-flight
        # summary so a power cut loses at most SESSION_CHECKPOINT_SECONDS
        # instead of the whole shift (recovered on next startup).
        self._checkpoint_last: float = 0.0
        try:
            self._checkpoint_interval: float = max(
                0.0, float(os.environ.get("SESSION_CHECKPOINT_SECONDS", "120"))
            )
        except (TypeError, ValueError):
            self._checkpoint_interval = 120.0
        # Camera reconnect bookkeeping (capture thread only).
        self._read_failures: int = 0
        self._reconnect_delay: float = _CAPTURE_RECONNECT_BASE_S

    def start_session(
        self,
        camera_index: int = 0,
        worker_id: str | None = None,
        created_by_user_id: int | None = None,
        camera_id: str | None = None,
    ) -> str:
        now = datetime.now()
        session_id = f"SESH-{now.strftime('%Y-%m-%d_%H-%M-%S')}"
        session_timestamp = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds

        # A camera_id that names a configured IP/RTSP source (or is itself an
        # RTSP URL) overrides the numeric index. cv2.VideoCapture accepts both
        # int indices and URL strings, so a single call handles USB + IP cams.
        source = _resolve_camera_source(camera_index, camera_id)
        self._is_demo_source = isinstance(source, str) and os.path.isfile(source)
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera at source {source}")
        if self._is_demo_source:
            self._demo_fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 15.0) or 15.0

        for pw, ph in [(1280, 720), (640, 480)]:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, pw)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ph)
            if int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == pw:
                break

        fw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.engine.initialize()
        self.analytics.reset()
        self.context_engine = ContextIntelligenceEngine(session_id=session_id)
        self._session_duration = 0.0
        self._last_frame_time = time.perf_counter()
        self.current_worker_id = worker_id
        self.current_created_by_user_id = created_by_user_id
        self.current_camera_index = source if isinstance(source, int) else camera_index
        self.current_camera_id = camera_id
        self.current_camera_source = source
        self.current_session_timestamp = session_timestamp
        self.video_recording_metadata = {}

        camera_fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        worker_dir = worker_id or "unknown"
        rec_dir = os.path.join(RECORDINGS_DIR, worker_dir, f"{session_timestamp}_{session_id}")
        os.makedirs(rec_dir, exist_ok=True)
        video_path = os.path.join(rec_dir, "original.mp4")
        # Recording at the camera's full native rate (1280x720 H.264 encode
        # on every captured frame) is a significant GIL cost that competes
        # with pose inference. Evidence review doesn't need 30 fps — cap the
        # recorder at RECORD_FPS (default 15) so the encode work is halved.
        rec_fps = camera_fps
        try:
            rec_fps = max(5.0, min(30.0, float(os.environ.get("RECORD_FPS", "15"))))
        except (TypeError, ValueError):
            rec_fps = 15.0
        self._rec_target_fps = rec_fps
        self._rec_camera_fps = camera_fps
        self.video_recorder = _SessionVideoRecorder(video_path, fw, fh, rec_fps)
        try:
            self.video_recorder.start()
        except Exception as exc:
            self.video_recording_metadata = {
                "video_path": None,
                "video_recording_status": "failed",
                "video_recording_error": str(exc),
                "video_frame_count": 0,
                "video_codec": None,
            }
        self._timeline.clear()
        self._frame_counter = 0
        self._capture_counter = 0
        self._last_process_time = 0.0
        self._checkpoint_last = 0.0
        self._frame_queue.clear()

        self.state = LiveState(
            session_active=True,
            session_id=session_id,
            session_start=time.time(),
            camera_status="active",
            frame_width=fw,
            frame_height=fh,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._fps_start = time.perf_counter()
        self._fps_count = 0

        self._running = True
        self._read_failures = 0
        self._reconnect_delay = _CAPTURE_RECONNECT_BASE_S
        self.state.camera_reconnecting = False
        # Capture runs on its own thread so the camera is drained continuously
        # (raw recording + ring buffer) regardless of inference latency.
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="live-capture"
        )
        self._capture_thread.start()
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

        self.event_bus.publish(SessionStartedEvent(
            session_id=session_id,
            camera_index=camera_index,
        ))
        return session_id

    def _save_recording_files(self, worker_id, session_timestamp, summary, video_metadata, session_id):
        if not session_timestamp:
            session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        worker_dir = worker_id or "unknown"
        rec_dir = os.path.join(RECORDINGS_DIR, worker_dir, f"{session_timestamp}_{session_id}")
        os.makedirs(rec_dir, exist_ok=True)

        timeline_path = os.path.join(rec_dir, "timeline.json")
        with open(timeline_path, "w") as f:
            json.dump(list(self._timeline), f, indent=2)

        summary_payload = {
            "disclaimer": (
                "Heuristic posture-risk thresholds, not clinically validated. "
                "Screening and awareness tool only; not a medical device; "
                "not a professional ergonomic assessment. Risk scores are "
                "estimates for prioritization and do not establish causation "
                "of injury."
            ),
            "session_id": session_id,
            "session_timestamp": session_timestamp,
            "worker_id": worker_id,
            "session_duration_seconds": summary.get("session_duration_seconds", 0),
            "total_frames": summary.get("total_frames", 0),
            "risk_percentages": summary.get("risk_percentages", {}),
            "most_frequent_issue": summary.get("most_frequent_issue"),
            "most_frequent_issue_count": summary.get("most_frequent_issue_count", 0),
            "highest_risk_level": summary.get("highest_risk_level", "LOW"),
            "highest_risk_timestamp": summary.get("highest_risk_timestamp"),
            "avg_neck_flexion": summary.get("avg_neck_flexion", 0),
            "avg_trunk_flexion": summary.get("avg_trunk_flexion", 0),
            "avg_shoulder_symmetry": summary.get("avg_shoulder_symmetry", 0),
            "avg_knee_angle": summary.get("avg_knee_angle", 0),
            "alerts": self.alert_engine.export().get("history", []),
            "video_recording_status": video_metadata.get("video_recording_status"),
            "video_frame_count": video_metadata.get("video_frame_count", 0),
            "video_codec": video_metadata.get("video_codec"),
        }
        summary_path = os.path.join(rec_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary_payload, f, indent=2)

    def stop_session(self) -> dict:
        session_id = self.state.session_id or ""
        worker_id = self.current_worker_id
        created_by_user_id = self.current_created_by_user_id
        camera_id = self.current_camera_id
        session_timestamp = self.current_session_timestamp
        total_frames = self.analytics.get_summary().get("total_frames", 0) if hasattr(self.analytics, 'get_summary') else 0

        self._running = False
        # Join capture FIRST (it owns cap.read()), then the process thread —
        # otherwise the process loop may try to pop frames while the camera is
        # being released.
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3)
        if self.thread:
            self.thread.join(timeout=3)

        summary = self.analytics.get_summary() if hasattr(self.analytics, 'get_summary') else {}
        video_metadata = self._finalize_video_recorder()

        self.engine.release()
        if self.cap:
            self.cap.release()
            self.cap = None

        self.state.session_active = False
        self.state.camera_status = "disconnected"
        self.state.camera_reconnecting = False

        # Post-process: burn the skeleton overlay into the recorded video
        # in a background thread so the API response isn't blocked.
        raw_video = video_metadata.get("video_path")
        if raw_video and os.path.exists(raw_video):
            threading.Thread(
                target=self._burn_overlay_into_recording,
                args=(raw_video,),
                daemon=True,
                name="overlay-burn",
            ).start()

        saved_path = None
        try:
            self._save_recording_files(worker_id, session_timestamp, summary, video_metadata, session_id)
        except Exception as exc:
            logger.error("Failed to save recording files: %s", exc, exc_info=True)

        try:
            os.makedirs(self.sessions_dir, exist_ok=True)
            ts = session_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            saved_path = save_session_summary(summary, self.sessions_dir, ts, alerts_data=self.alert_engine.export(), session_id=session_id)
            if saved_path:
                self._tag_saved_session(
                    saved_path=saved_path,
                    session_id=session_id,
                    worker_id=worker_id,
                    created_by_user_id=created_by_user_id,
                    camera_id=camera_id,
                    video_metadata=video_metadata,
                )
                # Mirror into the Postgres telemetry store when configured
                # (Tier 1) — the file stays authoritative for replay/evidence.
                self._mirror_to_postgres(saved_path, session_id)
            # Invalidate session cache so new session appears immediately
            from app.services.session_cache import invalidate_session_cache
            invalidate_session_cache()
            # Recordings are written above; invalidate so the listing refreshes.
            try:
                from app.api.recordings import invalidate_recordings_cache
                invalidate_recordings_cache()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed to invalidate recordings cache: %s", exc)
        except Exception as exc:
            logger.error("Failed to save session summary for %s: %s", session_id, exc, exc_info=True)

        self.current_worker_id = None
        self.current_created_by_user_id = None
        self.current_camera_index = None
        self.current_camera_id = None
        self.current_session_timestamp = None
        self.video_recording_metadata = video_metadata

        self.event_bus.publish(SessionEndedEvent(
            session_id=session_id,
            total_frames=total_frames,
            duration_seconds=self._session_duration,
        ))
        return {"summary": summary, "saved_path": saved_path}

    def _tag_saved_session(
        self,
        saved_path: str,
        session_id: str,
        worker_id: str | None,
        created_by_user_id: int | None,
        camera_id: str | None,
        video_metadata: dict | None = None,
    ) -> None:
        with open(saved_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["session_id"] = session_id
        payload["worker_id"] = worker_id
        payload["created_by_user_id"] = created_by_user_id
        payload["camera_id"] = camera_id
        # Persist the last detected task classification so the session list can
        # show the real task — task recognition is live-only otherwise.
        payload["task_name"] = getattr(self.state, "task_name", None) or None
        if video_metadata:
            payload.update(video_metadata)
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _mirror_to_postgres(self, saved_path: str, session_id: str) -> None:
        """Best-effort mirror of a saved session into Postgres (Tier 1).

        Non-fatal: a missing/overloaded DB leaves the JSON file as the source
        of truth and the session still appears in the UI via the file path.
        """
        try:
            from app.core.postgres import pg_enabled, init_postgres_schema, \
                upsert_session, bulk_insert_frames
            if not pg_enabled():
                return
            with open(saved_path, "r", encoding="utf-8") as f:
                import json as _json
                payload = _json.load(f)
            payload["session_id"] = session_id
            init_postgres_schema()
            ok_sess = upsert_session(payload)
            ok_frames = bulk_insert_frames(payload, list(self._timeline))
            if ok_sess:
                logger.debug(
                    "Session %s mirrored to Postgres (frames=%s)",
                    session_id, ok_frames,
                )
        except Exception as exc:
            logger.warning("Postgres mirror for %s failed (non-fatal): %s", session_id, exc)

    def _finalize_video_recorder(self) -> dict:
        recorder = self.video_recorder
        self.video_recorder = None
        if recorder is None:
            return self.video_recording_metadata or {
                "video_path": None,
                "video_recording_status": "unavailable",
                "video_recording_error": "Video recorder was not initialized",
                "video_frame_count": 0,
                "video_codec": None,
            }
        try:
            return recorder.finalize()
        except Exception as exc:
            return {
                "video_path": None,
                "video_recording_status": "failed",
                "video_recording_error": str(exc),
                "video_frame_count": recorder.frame_count,
                "video_codec": recorder.codec,
            }

    def _record_video_frame(self, frame: np.ndarray) -> None:
        recorder = self.video_recorder
        if recorder is None:
            return
        # Cap the recording frame rate (RECORD_FPS, default 15): skip every
        # other captured frame when the camera out-runs the target, so the
        # H.264 encode + disk write cost drops (the main GIL/I-O contention
        # with the pose pipeline). The recorder was created with the capped
        # fps, so playback timing stays correct.
        if recorder.fps < self._rec_camera_fps - 0.5 and self._capture_counter % 2 == 1:
            return
        recorder.write(frame)

    def _burn_overlay_into_recording(self, raw_video_path: str) -> None:
        """Post-process the raw recording to burn in the pose skeleton overlay.

        Runs in a background thread after the session ends. Reads the raw
        MP4, runs each frame through MediaPipe + draw_skeleton, and writes
        to overlay.mp4 alongside the original. The replay endpoint serves
        this overlaid version when available.
        """
        try:
            overlay_path = os.path.join(os.path.dirname(raw_video_path), "overlay.mp4")
            cap = cv2.VideoCapture(raw_video_path)
            if not cap.isOpened():
                logger.warning("Could not open raw video for overlay: %s", raw_video_path)
                return

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 15.0

            # Re-initialize a fresh pose engine for the re-processing pass
            overlay_engine = PoseEngine(self.model_path)
            overlay_engine.initialize()

            writer = None
            for codec in ("avc1", "H264", "mp4v"):
                writer = cv2.VideoWriter(overlay_path, cv2.VideoWriter_fourcc(*codec), fps, (w, h))
                if writer.isOpened():
                    break
                writer.release()
                writer = None
            if writer is None:
                logger.warning("Could not open VideoWriter for overlay: %s", overlay_path)
                cap.release()
                overlay_engine.release()
                return

            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                result = overlay_engine.process_frame(frame)
                # Mirror for natural selfie display, same as live pipeline
                frame = cv2.flip(frame, 1)
                if result.person_detected and result.keypoints:
                    kps = [
                        [1.0 - kp[0] / w, kp[1] / h, kp[2], kp[3]]
                        for kp in result.keypoints
                    ]
                    draw_skeleton(
                        frame, kps, result.risk_level, result.features,
                        standard_assessment=result.standard_assessment,
                    )
                writer.write(frame)
                frame_count += 1

            writer.release()
            cap.release()
            overlay_engine.release()
            logger.info("Overlay video written: %s (%d frames)", overlay_path, frame_count)
        except Exception as exc:
            logger.error("Failed to burn overlay into recording: %s", exc, exc_info=True)

    def _capture_loop(self):
        """Drain the camera continuously into the ring buffer + raw recorder.

        Runs on its own thread so frame capture (and the evidence-grade raw
        video recording) proceeds at the camera's native rate no matter how
        slow pose inference gets — the root cause of the "feed freezes /
        backend hangs" symptom during live monitoring.

        Camera resilience: a factory IP camera (RTSP) drops constantly. After
        ``_CAPTURE_FAILURE_THRESHOLD`` consecutive read failures the loop stops
        spinning on a dead handle and reopens the source with exponential
        backoff, setting ``state.camera_reconnecting`` so the UI can show the
        operator that the feed is temporarily down. The session keeps running
        the whole time; frames resume as soon as the camera is back.
        """
        while self._running:
            if self.cap is None:
                time.sleep(0.01)
                continue
            try:
                ret, frame = self.cap.read()
                if not ret:
                    if self._is_demo_source:
                        # Video file ended — loop back to the start so the
                        # demo keeps playing instead of tripping the reconnect
                        # path (which would reopen the file pointlessly).
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        time.sleep(0.1)
                        continue
                    self._handle_camera_read_failure()
                    continue
                # Camera is delivering frames again — reset reconnect state.
                if self._read_failures > 0 or self.state.camera_reconnecting:
                    logger.info(
                        "Camera recovered after %d read failures",
                        self._read_failures,
                    )
                self._read_failures = 0
                self._reconnect_delay = _CAPTURE_RECONNECT_BASE_S
                self.state.camera_reconnecting = False
                # Record the RAW camera frame — evidence-grade, and video-review
                # re-analysis expects the raw (non-mirrored) stream so
                # MediaPipe's left/right labels stay anatomically correct.
                # Cap the recording rate (RECORD_FPS, default 15): skipping
                # every other frame halves the H.264 encode + disk I/O, the
                # main GIL contention with the pose pipeline.
                self._record_video_frame(frame)
                # Ring buffer: drop-oldest when full (maxlen handles that).
                # Flip OUTSIDE the lock — cv2.flip on a full-res frame takes
                # time; holding the lock during it blocks the process thread
                # and video feed generator, causing visible lag.
                flipped = cv2.flip(frame, 1)
                with self._lock:
                    self._frame_queue.append(frame)
                    self._capture_counter += 1
                    self.state.current_frame = flipped
                # Demo playback runs at the video's own frame rate so the
                # replay feels like a live feed instead of fast-forwarding.
                if self._is_demo_source and self._demo_fps > 0:
                    time.sleep(1.0 / self._demo_fps)
                else:
                    time.sleep(0.001)
            except Exception as exc:
                logger.error(
                    "Capture loop error: %s", exc, exc_info=True,
                )
                self._handle_camera_read_failure()
                time.sleep(0.5)

    def _handle_camera_read_failure(self) -> None:
        """Count consecutive read failures and reopen the camera with backoff.

        Called from the capture thread when ``cap.read()`` fails. Below the
        threshold we treat it as jitter and retry immediately; at/above it we
        release the dead handle, reopen the configured source, and back off
        exponentially (0.5s → 1s → … capped at 10s) between attempts.
        """
        self._read_failures += 1
        if self._read_failures < _CAPTURE_FAILURE_THRESHOLD:
            time.sleep(0.05)
            return

        if not self.state.camera_reconnecting:
            logger.warning(
                "Camera read failing (%d consecutive) — attempting reconnect",
                self._read_failures,
            )
            self.state.camera_reconnecting = True

        delay = min(self._reconnect_delay, _CAPTURE_RECONNECT_MAX_S)
        time.sleep(delay)
        self._reconnect_delay = min(delay * 2, _CAPTURE_RECONNECT_MAX_S)
        self._try_reopen_camera()

    def _try_reopen_camera(self) -> None:
        """Release the dead handle and reopen the session's camera source.

        ``current_camera_source`` is the resolved source (int index or RTSP
        URL) recorded at session start, so reconnects target the same camera.
        Bounded open/read timeouts keep a dead RTSP stream from blocking the
        capture thread forever.
        """
        source = self.current_camera_source
        if source is None:
            return
        try:
            if self.cap is not None:
                self.cap.release()
            self.cap = cv2.VideoCapture(source)
            # Bound the connect + read so a dead stream fails fast instead of
            # hanging the capture thread (guarded for older OpenCV builds).
            open_timeout = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
            read_timeout = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
            for prop, ms in ((open_timeout, 3000), (read_timeout, 3000)):
                if prop is not None:
                    self.cap.set(prop, ms)
            if self.cap.isOpened():
                logger.info("Camera reconnected at source %s", source)
                self._read_failures = 0
                self._reconnect_delay = _CAPTURE_RECONNECT_BASE_S
                self.state.camera_reconnecting = False
            else:
                logger.warning(
                    "Camera reopen failed at source %s — will retry in %.1fs",
                    source, self._reconnect_delay,
                )
        except Exception as exc:
            logger.warning(
                "Camera reopen error at source %s: %s", source, exc,
            )

    def _process_loop(self):
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        # Per-session rolling averages (reset every session).
        self._session_neck = deque(maxlen=900)
        self._session_trunk = deque(maxlen=900)

        while self._running:
            # Latest-frame-wins: pop the newest frame and drop the backlog so
            # inference never chases stale frames (low latency, bounded queue).
            with self._lock:
                if not self._frame_queue:
                    frame = None
                else:
                    frame = self._frame_queue.pop()
                    self._frame_queue.clear()
            if frame is None:
                time.sleep(0.002)
                continue
            try:
                self._process_one_frame(frame, risk_order)
            except Exception as exc:
                logger.error(
                    "Live process loop error at frame %s: %s",
                    self._frame_counter, exc, exc_info=True,
                )
                # Keep the session alive: log + continue instead of letting
                # an unhandled exception silently kill the daemon thread,
                # which froze the MJPEG feed and "collapsed" the UI mid-session.
                time.sleep(0.5)

    def _derive_identified_worker(self) -> None:
        """Set ``self._identified_worker`` from the current person identities.

        The primary card worker = the largest box that matched an enrolled
        face. Liveness is attached so the UI can show "photo?" instead of
        "present" when the face is a spoof (no blinks, no motion).
        """
        matched = [
            r for r in self._person_identities
            if r.get("matched") and r.get("worker_id")
        ]
        if not matched:
            self._identified_worker = {}
            return
        primary = max(
            matched,
            key=lambda r: (r["box"]["x2"] - r["box"]["x1"]) * (r["box"]["y2"] - r["box"]["y1"]),
        )
        wid = primary["worker_id"]
        name = self._worker_name_cache.get(wid) or primary.get("name")
        if not name:
            try:
                from app.core.database import get_worker as _gw
                _row = _gw(wid)
                name = _row["name"] if _row else wid
            except Exception:
                name = wid
        self._worker_name_cache[wid] = name
        self._identified_worker = {
            "worker_id": wid,
            "name": name,
            "employee_id": primary.get("employee_id"),
            "confidence": primary.get("confidence", 0.0),
            "matched": True,
            # Liveness verdict from the anti-spoof tracker: "live",
            # "suspicious" (likely photo/video), or "unverified".
            "liveness": primary.get("liveness", "unverified"),
            "blinks": primary.get("blinks", 0),
            "observed_seconds": primary.get("observed_seconds", 0.0),
        }

    def _process_one_frame(self, frame: np.ndarray, risk_order: dict[str, int]) -> None:
        """Process one camera frame: pose inference -> context -> state.

        Frames arrive from the ring buffer (captured on the capture thread at
        camera rate); this method only runs inference + state updates. Wrapped
        in try/except by ``_process_loop`` so no engine/DB/WS error can
        silently kill the session thread.
        """
        now = time.perf_counter()
        if now - self._last_process_time < self._process_interval:
            return
        self._last_process_time = now
        # Fresh verdict each frame — a blink can flip a photo back to "live"
        # within one sample, so suppression must never persist stale.
        self._skeleton_suppressed = False

        inference_start = time.perf_counter()
        # Process the RAW frame: MediaPipe labels landmarks by the body as
        # seen in the image, so flipping the input first silently swaps
        # left/right features ("left elev shows right"). Infer on the raw
        # frame so left/right match the person's actual anatomy.
        # Downscale only the INFERENCE input (keypoints stay normalized), so
        # the skeleton refreshes faster without losing display resolution.
        max_w = _inference_max_width()
        inference_frame = frame
        if frame.shape[1] > max_w:
            scale = max_w / float(frame.shape[1])
            inference_frame = cv2.resize(
                frame, (max_w, max(1, int(frame.shape[0] * scale)))
            )
        result = self.engine.process_frame(inference_frame)
        w_i, h_i = inference_frame.shape[1], inference_frame.shape[0]

        # Mirror the frame for the natural selfie display, and mirror +
        # normalize the keypoints so the overlay skeleton aligns with the
        # mirrored feed (pose_overlay.draw_skeleton expects 0-1 coords).
        # Normalize against the INFERENCE dims so downscaling is transparent.
        frame = cv2.flip(frame, 1)
        h_f, w_f = frame.shape[:2]
        if result.keypoints:
            result.keypoints = [
                [1.0 - kp[0] / w_i, kp[1] / h_i, kp[2], kp[3]]
                for kp in result.keypoints
            ]
        inference_end = time.perf_counter()
        inference_latency_ms = (inference_end - inference_start) * 1000

        # ── Person detection + face identification (non-blocking) ────
        # YOLO + SFace + YuNet run in a background thread so they NEVER
        # block the pose pipeline. The process loop fires a thread every
        # PERSON_DETECT_INTERVAL_S and collects results on the next cycle.
        try:
            now_detect = time.perf_counter()
            # Collect results from previous background detection run
            if self._person_detect_thread is not None and not self._person_detect_thread.is_alive():
                self._person_detect_thread = None
                if self._person_detect_result is not None:
                    boxes, identified = self._person_detect_result
                    self._person_boxes = boxes
                    self._person_identities = identified or []
                    self._derive_identified_worker()
                    self._person_detect_result = None
            # Launch new detection if interval elapsed and no thread running
            if (now_detect - self._person_detect_last >= PERSON_DETECT_INTERVAL_S
                    and self._person_detect_thread is None):
                self._person_detect_last = now_detect
                if inference_frame is frame:
                    det_frame = frame.copy()
                else:
                    det_frame = cv2.flip(inference_frame, 1)
                self._person_detect_result = None
                def _bg_detect():
                    try:
                        boxes = detect_persons(det_frame)
                        identified = identify_persons_in_frame(det_frame, boxes)
                        self._person_detect_result = (boxes, identified)
                    except Exception as exc:
                        logger.warning("Person detection failed (skipped): %s", exc)
                        self._person_detect_result = ([], [])
                self._person_detect_thread = threading.Thread(target=_bg_detect, daemon=True)
                self._person_detect_thread.start()
        except Exception as exc:
            logger.warning("Person detection scheduling failed (skipped): %s", exc)

        # ── Liveness (anti-photo-spoof) sampling (non-blocking) ──────
        # Runs at ~1 Hz so blinks (150-400ms events) are observed. Moved
        # to background thread so it never blocks the pose pipeline.
        try:
            now_live = time.perf_counter()
            if (now_live - self._liveness_last >= self._liveness_interval
                    and self._liveness_thread is None and self._person_boxes):
                self._liveness_last = now_live
                if inference_frame is frame:
                    live_frame = frame.copy()
                else:
                    live_frame = cv2.flip(inference_frame, 1)
                boxes_copy = list(self._person_boxes)
                identities_ref = self._person_identities
                def _bg_liveness():
                    try:
                        verdicts = self._liveness_tracker.update(live_frame, boxes_copy)
                        if verdicts and identities_ref:
                            for idx, verdict in verdicts.items():
                                if idx < len(identities_ref):
                                    identities_ref[idx].update(verdict)
                            self._derive_identified_worker()
                            self._skeleton_suppressed = bool(
                                self._identified_worker.get("liveness") == "suspicious"
                            )
                    except Exception as exc:
                        logger.warning("Liveness sampling failed (skipped): %s", exc)
                self._liveness_thread = threading.Thread(target=_bg_liveness, daemon=True)
                self._liveness_thread.start()
            # Collect finished liveness thread
            if self._liveness_thread is not None and not self._liveness_thread.is_alive():
                self._liveness_thread = None
        except Exception as exc:
            logger.warning("Liveness scheduling failed (skipped): %s", exc)
    
        self._fps_count += 1
        elapsed = time.perf_counter() - self._fps_start
        fps = self.state.fps
        if elapsed >= 0.5:
            fps = self._fps_count / elapsed
            self._fps_count = 0
            self._fps_start = time.perf_counter()
    
        # ── Context Intelligence: compute delta and session duration ──
        now = time.perf_counter()
        delta_seconds = now - self._last_frame_time if self._last_frame_time > 0 else 0.033
        self._last_frame_time = now
        self._session_duration += delta_seconds
    
        risk_score = 0.0
        if result.person_detected:
            risk_score = risk_order.get(result.risk_level, 0) * 50.0
    
            self._session_neck.append(result.features.get("neck_flexion", 0.0))
            self._session_trunk.append(result.features.get("trunk_flexion", 0.0))
    
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
        # ── Context Intelligence: evaluate ────────────────────────────
        task_name = "Unknown"
        task_conf = 0.0
        task_duration = 0.0
        if result.task_info:
            task_name = result.task_info.get("task", "Unknown")
            task_conf = result.task_info.get("confidence", 0.0)
            task_duration = result.task_info.get("task_duration_seconds", 0.0)
    
        context_snapshot = self.context_engine.evaluate(
            features=result.features,
            issues=result.issues,
            task_name=task_name,
            task_confidence=task_conf,
            session_duration_seconds=self._session_duration,
            camera_confidence=result.confidence,
            delta_seconds=delta_seconds,
            unavailable_features=result.unavailable_features,
            approximate_features=result.approximate_features,
            lower_body_confidence=result.lower_body_confidence,
            standard_assessment=result.standard_assessment,
            joint_uncertainty=(result.framing or {}).get("joint_uncertainty"),
        )
    
        # Feed the analytics the SAME risk level the UI/timeline displays
        # (the context-moderated snapshot level), so saved session summaries
        # can never disagree with the live timeline. The raw pose-engine
        # level previously produced "100% HIGH" summaries on sessions whose
        # timeline showed LOW everywhere.
        self.analytics.update(result.features, context_snapshot.risk_level, result.issues,
                             result.person_detected, timestamp_str)

        # ── Ollama explanation (post-scoring, NON-blocking) ──────────
        # Generates a plain-language explanation for the AI Insights panel.
        # This MUST run in a background thread: Ollama takes multiple seconds
        # per generation on this hardware, and calling it inline in the
        # process loop froze the whole pipeline at ~1 processed frame every
        # 5s — the live feed looked like a dead stream. Rate-limited to one
        # call every 8s; the last cached explanation is reused meanwhile.
        try:
            from dataclasses import replace as _ds_replace
            if self._ai_explanation_cache:
                context_snapshot = _ds_replace(
                    context_snapshot, ai_explanation=self._ai_explanation_cache
                )
            if time.perf_counter() - self._ai_expl_last_attempt >= 8.0 and not self._ai_expl_running:
                self._ai_expl_last_attempt = time.perf_counter()
                snapshot_copy = context_snapshot

                def _generate_explanation_in_background():
                    self._ai_expl_running = True
                    try:
                        from backend.context.engine import generate_ai_explanation
                        expl = generate_ai_explanation(snapshot_copy)
                        if expl:
                            self._ai_explanation_cache = expl
                    except Exception as exc:
                        # Best-effort: never block the pipeline, but surface the
                        # failure in logs instead of swallowing it silently.
                        logger.warning("AI explanation generation failed: %s", exc, exc_info=True)
                    finally:
                        self._ai_expl_running = False

                threading.Thread(
                    target=_generate_explanation_in_background,
                    daemon=True,
                    name="ai-explanation",
                ).start()
        except Exception as exc:
            # Best-effort: never block the pipeline, but surface the failure.
            logger.warning("AI explanation setup failed: %s", exc, exc_info=True)

        self.event_bus.publish(ContextSnapshotCreatedEvent(
            snapshot=context_snapshot,
        ))
    
        self._frame_counter += 1
        active_alerts = [
            {
                "id": a.id,
                "severity": a.severity.value,
                "title": a.title,
                "message": a.message,
                "trigger_rule": a.trigger_rule,
            }
            for a in self.alert_engine.active_alerts
        ]
        recs_from_engine = []
        try:
            rec_bundle = self.recommendation_engine.export() if hasattr(self.recommendation_engine, 'export') else {}
            recs_from_engine = export_recommendations_from_bundle(rec_bundle)
        except Exception as exc:
            logger.error("Failed to export recommendations for %s: %s", self.state.session_id, exc, exc_info=True)
    
        timeline_entry = {
            "timestamp": round(self._session_duration, 3),
            "frame_number": self._frame_counter,
            "risk_score": round(context_snapshot.final_risk, 2),
            "risk_level": context_snapshot.risk_level,
            "confidence": round(result.confidence, 2),
            "features": {k: (None if v != v else round(float(v), 4)) for k, v in result.features.items()},
            "fatigue": round(context_snapshot.fatigue_score, 2),
            "exposure": round(context_snapshot.exposure_score, 2),
            "context_score": round(context_snapshot.final_risk, 2),
            "current_task": task_name,
            "task_duration_seconds": task_duration,
            "recommendations": recs_from_engine,
            "alerts": active_alerts,
            "unavailable_features": result.unavailable_features,
            "lower_body_confidence": round(result.lower_body_confidence, 2),
            "assessment_method": (result.standard_assessment or {}).get("method"),
            "assessment_score": (result.standard_assessment or {}).get("score"),
            "assessment_band": (result.standard_assessment or {}).get("risk_level"),
            "framing_state": (result.framing or {}).get("framing_state"),
            "framing_guidance": (result.framing or {}).get("guidance", []),
            "framing_quality": (result.framing or {}).get("quality_score"),
            "person_count": result.person_count,
            "keypoints": [
                [float(kp[0]), float(kp[1]), float(kp[2]) if len(kp) > 2 else 0.0,
                 float(kp[3]) if len(kp) > 3 else 1.0]
                for kp in (result.keypoints or [])
            ],
        }
        self._timeline.append(timeline_entry)
    
        worker_rec = ""
        supervisor_rec = ""
        if result.recommendations:
            r = result.recommendations[0]
            worker_rec = r.get("worker_actions", [""])[0] if r.get("worker_actions") else ""
            supervisor_rec = r.get("supervisor_actions", [""])[0] if r.get("supervisor_actions") else ""
    
        if not worker_rec and result.features:
            from backend.services.guidance import actionable_recommendations
            guidance_recs = actionable_recommendations(result.features)
            if guidance_recs:
                worker_rec = guidance_recs[0]
    
        avg_neck = float(np.mean(self._session_neck)) if self._session_neck else 0.0
        avg_trunk = float(np.mean(self._session_trunk)) if self._session_trunk else 0.0
    
        # The MJPEG generator draws the skeleton itself on the downscaled
        # stream frame (it needs the freshest video + interpolated keypoints,
        # which a precomputed full-res overlay can't provide). Precomputing a
        # full-res overlay here cost ~13 ms/frame of pure overhead for a
        # consumer that only exists in tests, and starved inference (GIL).
        # get_frame(overlaid=True) falls back to the raw mirrored frame.
        overlaid_frame = frame

        with self._lock:
            # NB: do NOT write self.state.current_frame here. The capture
            # loop owns current_frame (the freshest mirrored frame, written
            # at camera rate). Overwriting it here with this processed frame
            # — which is up to one inference latency (~400ms) old — made the
            # MJPEG stream alternate between fresh and stale frames, so the
            # video visibly jumped backward every inference cycle.
            self.state.overlaid_frame = overlaid_frame
            self.state.frame_number = self._frame_counter
            self.state.features = dict(result.features)
            self.state.risk_level = context_snapshot.risk_level
            self.state.risk_score = round(context_snapshot.final_risk, 2)
            self.state.confidence = result.confidence
            self.state.person_detected = result.person_detected
            self.state.keypoints = result.keypoints
            # Tag this pose with the capture counter at processing time so the
            # MJPEG generator can interpolate between consecutive poses.
            self._pose_history.append((self._capture_counter, list(result.keypoints)))
            self.state.task_name = task_name
            self.state.task_confidence = task_conf
            self.state.task_duration_seconds = task_duration
            self.state.issues = list(result.issues)
            self.state.worker_recommendation = worker_rec
            self.state.supervisor_recommendation = supervisor_rec
            self.state.fps = fps
            self.state.inference_latency_ms = inference_latency_ms
            self.state.timestamp = timestamp_str
            self.state.context_snapshot = context_snapshot
            self.state.unavailable_features = list(result.unavailable_features)
            self.state.lower_body_confidence = result.lower_body_confidence
            self.state.standard_assessment = dict(result.standard_assessment or {})
            self.state.framing = dict(result.framing or {})
            self.state.person_count = result.person_count
            self.state.person_boxes = list(self._person_boxes)
            self.state.person_identities = [dict(r) for r in self._person_identities]
            self.state.identified_worker = dict(self._identified_worker)
            # Per-person risk for the station view (every detected pose).
            self.state.person_risks = [dict(r) for r in (result.person_risks or [])]

        # ── Crash-safe checkpoint (throttled) ────────────────────────
        # A power cut mid-shift normally loses the session: the summary JSON
        # is only written on stop_session. Persist every
        # SESSION_CHECKPOINT_SECONDS so a crash loses at most the interval.
        # Small JSON write (few ms), throttled — never blocks the pipeline
        # meaningfully; a failure only degrades crash recovery, never the
        # live loop.
        try:
            now_ck = time.perf_counter()
            if (
                self._checkpoint_interval > 0
                and now_ck - self._checkpoint_last >= self._checkpoint_interval
            ):
                self._checkpoint_last = now_ck
                if hasattr(self.analytics, "get_summary") and self.state.session_id:
                    summary = self.analytics.get_summary()
                    save_session_checkpoint(
                        summary,
                        self.sessions_dir,
                        self.current_session_timestamp,
                        self.state.session_id,
                        alerts_data=self.alert_engine.export(),
                        meta={
                            "worker_id": self.current_worker_id,
                            "created_by_user_id": self.current_created_by_user_id,
                            "camera_id": self.current_camera_id,
                            "task_name": getattr(self.state, "task_name", None) or None,
                        },
                    )
        except Exception as exc:
            logger.warning("Session checkpoint failed (skipped): %s", exc)
        # No sleep here — the _process_interval throttle above already pacing.
    
    def get_frame(self, overlaid: bool = True) -> Optional[np.ndarray]:
        """Return a copy of the current frame.

        When *overlaid* is True (default), returns the pre-computed frame
        with the pose skeleton overlay already drawn — the MJPEG generator
        uses this to avoid redrawing the skeleton for every client. When
        False, returns the raw camera frame (used for video recording and
        screenshot capture).
        """
        with self._lock:
            if overlaid:
                if self.state.overlaid_frame is not None:
                    frame = self.state.overlaid_frame
                else:
                    frame = self.state.current_frame
            else:
                frame = self.state.current_frame
            return frame.copy() if frame is not None else None

    def get_frame_number(self) -> Optional[int]:
        """Return the current frame's counter, or ``None`` before the first frame.

        Lets stream consumers check for a new frame WITHOUT copying the frame
        (the copy only happens once a new frame is detected).
        """
        with self._lock:
            if self.state.current_frame is None:
                return None
            return self.state.frame_number

    def get_capture_counter(self) -> Optional[int]:
        """Return how many camera frames have been captured, or ``None`` before the first.

        Incremented in the capture loop at the camera's native rate — NOT the
        processed-frame counter. The MJPEG generator keys off this so the
        stream stays continuous (every captured frame) even when pose
        inference runs at a fraction of the camera rate.
        """
        with self._lock:
            if self.state.current_frame is None:
                return None
            return self._capture_counter

    def get_overlay_payload(self, capture_counter: Optional[int] = None) -> dict:
        """Lightweight overlay data — avoids deep-copying the full state (incl. frame).

        When *capture_counter* is given, keypoints are interpolated between the
        two most recent processed poses so the skeleton tracks the body at
        video rate instead of jumping once per inference. Inference runs at
        ~8 fps while the stream runs at ~30 fps — without interpolation the
        overlay visibly lags the person between processed frames.
        """
        with self._lock:
            # standard_assessment is set dynamically after the first processed
            # frame (it is not a LiveState field), so read it defensively — a
            # stream consumer may call this before the first frame completes.
            std = getattr(self.state, "standard_assessment", None) or {}
            keypoints = list(self.state.keypoints)
            hist = list(self._pose_history)
            person_boxes = list(self._person_boxes)
            person_identities = [dict(r) for r in self._person_identities]
            identified_worker = dict(self._identified_worker)

        if capture_counter is not None and keypoints and len(hist) >= 2:
            (c0, k0), (c1, k1) = hist[-2], hist[-1]
            span = c1 - c0
            if span > 0:
                # t < 0 (before the newer pose): interpolate toward it.
                # t > 0 (after the newer pose): extrapolate briefly using the
                # motion between the two poses — this is what keeps the
                # skeleton glued to a moving body between inferences.
                t = (capture_counter - c0) / span
                # Clamp to avoid wild extrapolation on pose switches/re-detect.
                t = max(-0.5, min(t, 1.5))
                interp = []
                for a, b in zip(k0, k1):
                    interp.append([
                        a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t,
                        b[2] if len(b) > 2 else a[2] if len(a) > 2 else 0.0,
                        b[3] if len(b) > 3 else a[3] if len(a) > 3 else 1.0,
                    ])
                keypoints = interp

        return {
            "keypoints": keypoints,
            "risk_level": self.state.risk_level,
            "features": dict(self.state.features),
            # The standard RULA/REBA assessment lets the overlay color
            # regions from the same per-joint sub-scores that produced
            # the overall level — the skeleton and badge stay consistent.
            "standard_assessment": dict(std),
            "person_boxes": person_boxes,
            "person_identities": person_identities,
            "identified_worker": identified_worker,
            # False when the primary face is a confirmed photo/screen — the
            # feed must not paint MediaPipe landmarks on a spoof.
            "skeleton_visible": not self._skeleton_suppressed,
        }

    def get_ws_payload(self) -> dict:
        """JSON-safe dashboard payload for WebSocket pushes — no full-frame deepcopy."""
        with self._lock:
            return build_ws_payload(self.state)

    def get_state_snapshot(self) -> LiveState:
        """Return a snapshot of the live state WITHOUT the raw video frame.

        Deep-copying the numpy ``current_frame`` (1280x720x3) on every API
        request was a hidden cost that compounded with the poll fan-out while
        a session was active. The frame is only consumed through ``get_frame()``
        (which copies it on demand for the MJPEG feed); every other reader
        (dashboard, cameras, deployment, context, session status) only needs the
        scalars/lists, so the frame is dropped from the copy.
        """
        import copy
        with self._lock:
            state = copy.deepcopy(self.state)
            state.current_frame = None
            state.overlaid_frame = None
            return state

    def get_recent_timeline(self, n: int = 200) -> list[dict]:
        """Return the last *n* timeline entries from the current session."""
        return list(self._timeline)[-n:]

    def is_running(self) -> bool:
        return self._running and self.state.session_active

    @property
    def has_frame(self) -> bool:
        with self._lock:
            return self.state.current_frame is not None


# Global singleton — initialized during app startup
_service_instance: Optional[LiveMonitoringService] = None


def init_live_service(model_path: str, sessions_dir: Optional[str] = None) -> LiveMonitoringService:
    global _service_instance
    _service_instance = LiveMonitoringService(model_path, sessions_dir)
    return _service_instance


def is_live_service_initialized() -> bool:
    global _service_instance
    return _service_instance is not None

def get_live_service() -> LiveMonitoringService:
    if _service_instance is None:
        raise RuntimeError("LiveMonitoringService not initialized. Call init_live_service() during app startup.")
    return _service_instance

def get_live_service_or_none() -> Optional[LiveMonitoringService]:
    global _service_instance
    return _service_instance
