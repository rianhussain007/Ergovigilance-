"""ErgoVigilance API — FastAPI application entry point.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""

import asyncio
import json
import logging
import math
import os
import subprocess
import threading
import time
from contextlib import asynccontextmanager

# Track backend process start time
BACKEND_START_TIME = time.time()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.health import health_status
from app.api.router import api_router
from app.api.ops import router as ops_router
from app.api.ops import http_metrics_middleware as metrics_middleware
from app.api.websocket import router as ws_router
from app.services.live_monitor import init_live_service
from app.services.retention import run_retention
from app.core.database import init_local_database
from backend.services.assistant import load_corpus

setup_logging()
logger = logging.getLogger(__name__)

MODEL_PATH = settings.POSE_MODEL_PATH
SESSIONS_DIR = os.environ.get(
    "SESSIONS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "sessions"),
)


def _ensure_ollama_running():
    """Check if Ollama is running and start it if not."""
    import requests
    ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            logger.info("Ollama is already running")
            return
    except requests.ConnectionError:
        pass

    logger.info("Ollama not running — attempting to start it...")
    ollama_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if not os.path.exists(ollama_path):
        logger.warning("Ollama not found at %s — AI assistant will be unavailable", ollama_path)
        return

    try:
        subprocess.Popen(
            [ollama_path, "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Ollama process started")
    except Exception as exc:
        logger.warning("Failed to start Ollama: %s", exc)


RETENTION_INTERVAL_HOURS = float(os.getenv("RETENTION_INTERVAL_HOURS", "6"))
# How often the background loop writes the risk digest (default: nightly).
# Set to 0 to disable the scheduled digest (on-demand endpoint still works).
DIGEST_INTERVAL_HOURS = float(os.getenv("DIGEST_INTERVAL_HOURS", "24"))


async def _digest_loop():
    """Periodically write the risk digest (runs in the event loop)."""
    if DIGEST_INTERVAL_HOURS <= 0:
        return
    while True:
        try:
            from app.services.report_digest import generate_digest
            result = await asyncio.to_thread(generate_digest, 24.0, True)
            if result["saved"]:
                logger.info("Risk digest written: %s", result["path"])
            else:
                logger.info("Risk digest: no sessions in the last 24h — skipped")
        except Exception as exc:  # never take the service down over a digest
            logger.exception("Risk digest pass failed: %s", exc)
        await asyncio.sleep(DIGEST_INTERVAL_HOURS * 3600)


async def _retention_loop():
    """Periodically enforce the data-retention policy (runs in the event loop)."""
    while True:
        try:
            stats = await asyncio.to_thread(run_retention)
            logger.info("Retention pass complete: %s", stats)
        except Exception as exc:  # never take the service down over cleanup
            logger.exception("Retention pass failed: %s", exc)
        await asyncio.sleep(RETENTION_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    if settings.DEBUG:
        logger.warning(
            "Running in DEBUG mode (DEBUG=true) — dev defaults for JWT are in effect. "
            "Set DEBUG=false and a strong AUTH_JWT_SECRET before any non-local deployment "
            "(see backend_api/.env.production.example)."
        )
    init_local_database()

    # Tier 1: when DATABASE_URL is configured, create the Postgres telemetry
    # tables (non-blocking, never raises — file mode continues if it fails).
    try:
        from app.core.postgres import pg_enabled, init_postgres_schema
        if pg_enabled():
            if init_postgres_schema():
                logger.info("PostgreSQL telemetry store ready")
            else:
                logger.warning("Postgres unavailable at startup — sessions stay in file mode")
    except Exception as exc:
        logger.warning("Postgres init skipped: %s", exc)

    retention_task = asyncio.create_task(_retention_loop())
    digest_task = asyncio.create_task(_digest_loop())
    logger.info(
        "Data retention active (session_days=%.0f recording_days=%.0f cap=%.0f GB, interval=%.1fh)",
        float(os.getenv("SESSION_RETENTION_DAYS", "30")),
        float(os.getenv("RECORDING_RETENTION_DAYS", "30")),
        float(os.getenv("RECORDINGS_MAX_GB", "20")),
        RETENTION_INTERVAL_HOURS,
    )

    # Crash-safe session recovery: finalize any orphaned .checkpoints from a
    # hard power cut into real session files (flagged interrupted: true) so
    # the shift's data survives. Run BEFORE the prewarm threads so recovery
    # and the cache warmer never race on the same directory.
    try:
        from backend.services.session_analytics import recover_interrupted_sessions
        recovered = recover_interrupted_sessions(SESSIONS_DIR)
        if recovered:
            logger.info(
                "Recovered %d interrupted session(s) from crash checkpoints",
                len(recovered),
            )
            from app.services.session_cache import invalidate_session_cache
            invalidate_session_cache()
    except Exception as exc:
        logger.warning("Session checkpoint recovery failed (non-fatal): %s", exc)

    # Non-blocking startup: Ollama check has a network timeout and the corpus
    # load can take seconds — neither should delay first request readiness.
    threading.Thread(target=_ensure_ollama_running, daemon=True, name="ollama-watchdog").start()

    # Prewarm slow caches in the background so the first request that touches
    # them is fast: the session-file scan takes seconds (~3s for 66 files) and
    # probing physical cameras takes ~9s on Windows. Without this, the first
    # /api/sessions and /api/deployment calls block for seconds. Both warmers
    # guard their own errors, so a failure just falls back to lazy probing.
    # Run them in parallel — the camera probe is the slower one.
    from app.repositories.live import warm_camera_cache
    from app.services.session_cache import prewarm_session_cache
    from app.api.recordings import prewarm_recordings_cache

    threading.Thread(target=warm_camera_cache, daemon=True, name="camera-prewarm").start()
    threading.Thread(target=prewarm_session_cache, daemon=True, name="session-prewarm").start()
    threading.Thread(target=prewarm_recordings_cache, daemon=True, name="recordings-prewarm").start()

    model_path = os.path.abspath(MODEL_PATH)
    if not os.path.exists(model_path):
        logger.warning("Pose model not found at %s — live mode unavailable", model_path)
    else:
        logger.info("Initializing LiveMonitoringService with model: %s", model_path)
        init_live_service(model_path, sessions_dir=os.path.abspath(SESSIONS_DIR))

    async def _load_corpus_async() -> None:
        try:
            await asyncio.to_thread(load_corpus)
            logger.info("AI Assistant knowledge corpus loaded")
        except Exception as exc:
            logger.warning("Assistant corpus load failed (non-fatal): %s", exc)

    corpus_task = asyncio.create_task(_load_corpus_async())

    # Playwright is intentionally NOT launched at startup: the browser is
    # started lazily on first PDF export (see report_pdf._get_browser), so a
    # slow/missing Chromium binary never blocks service readiness.

    yield

    corpus_task.cancel()

    retention_task.cancel()
    try:
        await retention_task
    except asyncio.CancelledError:
        pass

    try:
        from backend.services.report_pdf import close_browser
        await close_browser()
    except Exception as exc:
        logger.warning("Error closing Playwright browser: %s", exc)

    from app.services.live_monitor import get_live_service
    try:
        service = get_live_service()
        if service.is_running():
            logger.info("Stopping active session during shutdown...")
            service.stop_session()
    except RuntimeError:
        pass

    logger.info("Shutting down %s", settings.APP_NAME)


class _SafeJSONEncoder(json.JSONEncoder):
    """Convert NaN/inf floats to null for JSON compliance."""

    def default(self, o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        return super().default(o)

    def encode(self, o):
        return super().encode(self._sanitize(o))

    def _sanitize(self, o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        if isinstance(o, dict):
            return {k: self._sanitize(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [self._sanitize(v) for v in o]
        return o


class _SafeJSONResponse(JSONResponse):
    """JSONResponse that converts NaN/inf floats to null for compliance."""

    def render(self, content) -> bytes:
        return json.dumps(content, cls=_SafeJSONEncoder).encode("utf-8")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for the ErgoVigilance AI ergonomic monitoring platform. "
    "Provides REST endpoints and WebSocket streams consumed by the React dashboard. "
    "Connects to the live OpenCV/MediaPipe pipeline via LiveMonitoringService.",
    lifespan=lifespan,
    default_response_class=_SafeJSONResponse,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(api_router)
app.include_router(ws_router)

# Operational endpoints at the root: /healthz, /readyz, /metrics
app.include_router(ops_router)

# --- Metrics middleware (counts every HTTP request) ---
app.middleware("http")(metrics_middleware)


# --- Health ---
@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint — used by Deployment Center and load balancers."""
    status = health_status()
    try:
        from app.services.live_monitor import get_live_service
        service = get_live_service()
        status["live_session"] = service.is_running()
    except RuntimeError:
        status["live_session"] = False
    status["model_available"] = os.path.exists(MODEL_PATH)
    return status


@app.get("/", tags=["System"])
async def root():
    """Root redirect to API docs."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
