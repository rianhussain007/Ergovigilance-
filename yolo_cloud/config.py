"""YOLO Cloud Core — configuration."""

import json
import os
from dataclasses import dataclass, field


@dataclass
class CloudSettings:
    """Settings for the YOLO cloud ingestion service."""

    # Server
    HOST: str = os.getenv("CLOUD_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("CLOUD_PORT", "8100"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # YOLO model
    YOLO_MODEL: str = os.getenv("YOLO_MODEL", "yolov8s-pose.pt")
    YOLO_CONFIDENCE: float = float(os.getenv("YOLO_CONFIDENCE", "0.5"))
    YOLO_DEVICE: str = os.getenv("YOLO_DEVICE", "cpu")  # "cpu", "0", "cuda:0"
    INFERENCE_FPS: float = float(os.getenv("INFERENCE_FPS", "10"))

    # Trained ML models (risk + task classifiers for COCO_17 features)
    YOLO_RISK_MODEL: str = os.getenv(
        "YOLO_RISK_MODEL",
        os.path.join(os.path.dirname(__file__), "..", "models", "yolo_risk_model.pkl"),
    )
    YOLO_TASK_MODEL: str = os.getenv(
        "YOLO_TASK_MODEL",
        os.path.join(os.path.dirname(__file__), "..", "models", "yolo_task_model.pkl"),
    )

    # Tracking
    TRACK_THRESH: float = float(os.getenv("TRACK_THRESH", "0.5"))
    TRACK_BUFFER: int = int(os.getenv("TRACK_BUFFER", "60"))
    MATCH_THRESH: float = float(os.getenv("MATCH_THRESH", "0.8"))
    MIN_HITS: int = int(os.getenv("MIN_HITS", "3"))

    # RTSP ingestion
    RTSP_TRANSPORT: str = os.getenv("RTSP_TRANSPORT", "tcp")
    RTSP_TIMEOUT: int = int(os.getenv("RTSP_TIMEOUT", "5"))
    RTSP_RECONNECT_DELAY: float = float(os.getenv("RTSP_RECONNECT_DELAY", "2.0"))
    RTSP_MAX_RECONNECT: int = int(os.getenv("RTSP_MAX_RECONNECT", "10"))

    # Session management
    SESSION_IDLE_TIMEOUT: int = int(os.getenv("SESSION_IDLE_TIMEOUT", "60"))
    SESSION_CHECKPOINT_INTERVAL: int = int(os.getenv("SESSION_CHECKPOINT_INTERVAL", "120"))

    # Storage
    SESSIONS_DIR: str = os.getenv(
        "SESSIONS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "outputs", "sessions"),
    )
    RECORDINGS_DIR: str = os.getenv(
        "RECORDINGS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "recordings"),
    )

    # Cameras (JSON array of {id, name, url})
    RTSP_CAMERAS: list[dict] = field(default_factory=list)

    # CORS
    CORS_ORIGINS: list[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ])

    # Auth (shared with on-premise backend)
    AUTH_JWT_SECRET: str = os.getenv(
        "AUTH_JWT_SECRET",
        "local-dev-secret-not-for-production-12345678",
    )

    def __post_init__(self):
        raw = os.getenv("RTSP_CAMERAS", "")
        if raw:
            try:
                self.RTSP_CAMERAS = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                self.RTSP_CAMERAS = []
        # Ensure dirs exist
        os.makedirs(self.SESSIONS_DIR, exist_ok=True)
        os.makedirs(self.RECORDINGS_DIR, exist_ok=True)


settings = CloudSettings()
