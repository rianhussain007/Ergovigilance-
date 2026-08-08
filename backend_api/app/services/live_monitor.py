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
from backend.services.session_analytics import SessionAnalytics, save_session_summary
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

RECORDINGS_DIR = os.environ.get(
    "RECORDINGS_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")),
)


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
        "frame_width": state.frame_width,
        "frame_height": state.frame_height,
        "features": clean_feature_values(state.features),
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
        self.current_session_timestamp: Optional[str] = None
        self.video_recorder: Optional[_SessionVideoRecorder] = None
        self.video_recording_metadata: dict = {}
        self._timeline: list[dict] = []
        self._frame_counter: int = 0

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

        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera at index {camera_index}")

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
        self.current_camera_index = camera_index
        self.current_camera_id = camera_id
        self.current_session_timestamp = session_timestamp
        self.video_recording_metadata = {}

        camera_fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        worker_dir = worker_id or "unknown"
        rec_dir = os.path.join(RECORDINGS_DIR, worker_dir, f"{session_timestamp}_{session_id}")
        os.makedirs(rec_dir, exist_ok=True)
        video_path = os.path.join(rec_dir, "original.mp4")
        self.video_recorder = _SessionVideoRecorder(video_path, fw, fh, camera_fps)
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
            json.dump(self._timeline, f, indent=2)

        summary_payload = {
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
            # Invalidate session cache so new session appears immediately
            from app.services.session_cache import invalidate_session_cache
            invalidate_session_cache()
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
        if video_metadata:
            payload.update(video_metadata)
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

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
        recorder.write(frame)

    def _process_loop(self):
        sample_counter = 0
        session_neck = deque(maxlen=900)
        session_trunk = deque(maxlen=900)
        max_risk = "LOW"
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

        while self._running:
            if self.cap is None:
                time.sleep(0.01)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            self._record_video_frame(frame)
            inference_start = time.perf_counter()
            result = self.engine.process_frame(frame)
            inference_end = time.perf_counter()
            inference_latency_ms = (inference_end - inference_start) * 1000

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

            sample_counter += 1
            risk_score = 0.0
            if result.person_detected:
                risk_score = risk_order.get(result.risk_level, 0) * 50.0

                session_neck.append(result.features.get("neck_flexion", 0.0))
                session_trunk.append(result.features.get("trunk_flexion", 0.0))
                if risk_order.get(result.risk_level, 0) > risk_order.get(max_risk, 0):
                    max_risk = result.risk_level

            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.analytics.update(result.features, result.risk_level, result.issues,
                                 result.person_detected, timestamp_str)

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
            )

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

            avg_neck = float(np.mean(session_neck)) if session_neck else 0.0
            avg_trunk = float(np.mean(session_trunk)) if session_trunk else 0.0

            with self._lock:
                self.state.current_frame = frame
                self.state.frame_number = self._frame_counter
                self.state.features = dict(result.features)
                self.state.risk_level = context_snapshot.risk_level
                self.state.risk_score = round(context_snapshot.final_risk, 2)
                self.state.confidence = result.confidence
                self.state.person_detected = result.person_detected
                self.state.keypoints = result.keypoints
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

            time.sleep(0.01)

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self.state.current_frame.copy() if self.state.current_frame is not None else None

    def get_frame_number(self) -> Optional[int]:
        """Return the current frame's counter, or ``None`` before the first frame.

        Lets stream consumers check for a new frame WITHOUT copying the frame
        (the copy only happens once a new frame is detected).
        """
        with self._lock:
            if self.state.current_frame is None:
                return None
            return self.state.frame_number

    def get_overlay_payload(self) -> dict:
        """Lightweight overlay data — avoids deep-copying the full state (incl. frame)."""
        with self._lock:
            return {
                "keypoints": list(self.state.keypoints),
                "risk_level": self.state.risk_level,
                "features": dict(self.state.features),
            }

    def get_ws_payload(self) -> dict:
        """JSON-safe dashboard payload for WebSocket pushes — no full-frame deepcopy."""
        with self._lock:
            return build_ws_payload(self.state)

    def get_state_snapshot(self) -> LiveState:
        import copy
        with self._lock:
            return copy.deepcopy(self.state)

    def get_recent_timeline(self, n: int = 200) -> list[dict]:
        """Return the last *n* timeline entries from the current session."""
        return list(self._timeline[-n:])

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
