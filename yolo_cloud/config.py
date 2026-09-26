"""YOLO Cloud Core — configuration."""

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CloudSettings:
    """Settings for the YOLO cloud ingestion service."""

    # Server
    HOST: str = os.getenv("CLOUD_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("CLOUD_PORT", "8100"))
    # Secure-by-default: false unless local dev explicitly sets DEBUG=true.
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # YOLO model
    YOLO_MODEL: str = os.getenv("YOLO_MODEL", "yolov8s-pose.pt")
    YOLO_CONFIDENCE: float = float(os.getenv("YOLO_CONFIDENCE", "0.5"))
    YOLO_DEVICE: str = os.getenv("YOLO_DEVICE", "cpu")  # "cpu", "0", "cuda:0"
    # Inference input size in pixels. 640 is ultralytics' own default, so the
    # default here changes nothing — it exists to make the size an ops knob
    # (smaller = faster on CPU, coarser keypoints). The measured trade-off is
    # in docs/SIZING_SOAK_CLOUD.md.
    YOLO_IMGSZ: int = int(os.getenv("YOLO_IMGSZ", "640"))
    INFERENCE_FPS: float = float(os.getenv("INFERENCE_FPS", "10"))
    # Frame-skip: the processing loop scores only every Nth frame it pulls
    # (1 = score every frame — the default, behavior unchanged). The skipped
    # frames are consumed so the next scored frame is fresh, but never scored,
    # clipped, or counted in latency — every reported rate stays a
    # SCORED-frame rate. Cost: every window measured in frames (task smoothing,
    # tracker hits, dwell) stretches in wall time, so time-to-alert grows as N.
    # Measured trade-off: docs/DEPLOYMENT_TOPOLOGY.md.
    YOLO_SCORE_EVERY: int = max(1, int(os.getenv("YOLO_SCORE_EVERY", "1")))

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

    # ── Deployment behind a reverse proxy ───────────────────────────────
    # X-Forwarded-For / X-Forwarded-Proto are honoured ONLY when TRUST_PROXY is
    # on. Trusting them unconditionally lets any client pick its own rate-limit
    # bucket and spoof its address.
    TRUST_PROXY: bool = os.getenv("TRUST_PROXY", "false").lower() == "true"
    TRUSTED_PROXY_HOPS: int = int(os.getenv("TRUSTED_PROXY_HOPS", "1"))
    REQUIRE_TLS: bool = os.getenv("REQUIRE_TLS", "false").lower() == "true"
    TLS_CERTFILE: str = os.getenv("TLS_CERTFILE", "")
    TLS_KEYFILE: str = os.getenv("TLS_KEYFILE", "")

    # ── Rate limits (per client IP, sliding window) ─────────────────────
    # Sized for 4 concurrent RTSP streams: one 5 Hz WS + 5 s polls per operator
    # screen fit comfortably; camera add/start/stop and identity scans get a
    # stricter bucket of their own.
    RATE_LIMIT_WINDOW_S: int = int(os.getenv("RATE_LIMIT_WINDOW_S", "60"))
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "600"))
    RATE_LIMIT_CAMERA_WRITES: int = int(os.getenv("RATE_LIMIT_CAMERA_WRITES", "60"))

    # ── Single-worker guard ─────────────────────────────────────────────
    # Camera ingestion (RTSP manager, processors, identity registry) is
    # in-process singleton state. A second uvicorn worker would open a second
    # FFmpeg per camera and double-process every frame, so >1 worker is refused
    # unless explicitly overridden. EXPECTED_CAMERAS sizes the box; it does NOT
    # enable clustering.
    EXPECTED_CAMERAS: int = int(os.getenv("EXPECTED_CAMERAS", "4"))
    STRICT_SINGLE_WORKER: bool = os.getenv("STRICT_SINGLE_WORKER", "true").lower() == "true"

    # ── Per-tile quality flags (display only; never inputs to scoring) ──
    LOW_LIGHT_LUMA: float = float(os.getenv("LOW_LIGHT_LUMA", "40"))
    QUALITY_MIN_TILE_H_PX: int = int(os.getenv("QUALITY_MIN_TILE_H_PX", "64"))
    QUALITY_KEYPOINT_CONF: float = float(os.getenv("QUALITY_KEYPOINT_CONF", "0.3"))

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
    # Station ROI polygons — per-camera workstation boundaries drawn by a
    # supervisor (JSON; see yolo_cloud/stations.py).
    STATIONS_FILE: str = os.getenv(
        "STATIONS_FILE",
        os.path.join(os.path.dirname(__file__), "..", "config", "stations.json"),
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
        os.makedirs(os.path.dirname(os.path.abspath(self.STATIONS_FILE)), exist_ok=True)


settings = CloudSettings()

# Dashboard-persisted overrides (POST /settings): file values apply only
# where the environment is silent — env always wins. Never break boot on
# a bad override file.
try:
    from yolo_cloud.cloud_settings import apply_overrides

    _applied = apply_overrides(settings)
    if _applied:
        logger.info("Applied dashboard settings overrides: %s", ",".join(_applied))
except Exception as exc:  # pragma: no cover - defensive, boot must continue
    logger.warning("Ignoring cloud_settings.json: %s", exc)
