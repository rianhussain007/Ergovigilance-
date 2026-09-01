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
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

from yolo_cloud.config import settings
from yolo_cloud.rtsp_manager import RTSPManager, CameraInfo, get_rtsp_manager
from yolo_cloud.pose_engine import (
    YOLOPoseEngine,
    ProcessedCloudFrame,
    TrackedPose,
    get_pose_engine,
)

logger = logging.getLogger(__name__)


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
        self._idle_start: Optional[float] = None
        # Latest state for API consumption
        self.latest_poses: list[TrackedPose] = []
        self.latest_frame_time: float = 0.0

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

            try:
                processed = self.engine.process_frame(frame)
                self._handle_result(processed)
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
        self.latest_frame_time = result.timestamp

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

            # Alert check
            if risk_level in ("MEDIUM", "HIGH"):
                self._check_alert(risk_level, risk_score, task, track_id, result.timestamp)
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

    def _check_alert(
        self, risk_level: str, risk_score: float, task: str, track_id: int, timestamp: float
    ) -> None:
        """Check if we should fire an alert."""
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
            tenant_id=self.tenant_id,
        )
        alert_dict = alert.to_dict()
        self._session.alerts.append(alert_dict)
        self._last_alert_time[track_id] = timestamp
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
                "person_count": len(processor.latest_poses),
                "fps": camera.fps if camera else 0,
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

        return {
            "total_cameras": len(all_cameras),
            "active_cameras": active_cameras,
            "total_workers": total_persons,
            "risk_distribution": risk_counts,
            "cameras": all_cameras,
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
