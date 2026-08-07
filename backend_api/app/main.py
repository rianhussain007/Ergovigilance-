"""ErgoVigilance API — FastAPI application entry point.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""

import json
import logging
import math
import os
import subprocess
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
from app.api.websocket import router as ws_router
from app.services.live_monitor import init_live_service
from app.core.database import init_local_database
from backend.services.assistant import load_corpus

setup_logging()
logger = logging.getLogger(__name__)

MODEL_PATH = os.environ.get(
    "POSE_MODEL_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "models", "pose_landmarker_lite.task"),
)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    init_local_database()

    _ensure_ollama_running()

    model_path = os.path.abspath(MODEL_PATH)
    if not os.path.exists(model_path):
        logger.warning("Pose model not found at %s — live mode unavailable", model_path)
    else:
        logger.info("Initializing LiveMonitoringService with model: %s", model_path)
        init_live_service(model_path, sessions_dir=os.path.abspath(SESSIONS_DIR))

    logger.info("Loading AI Assistant knowledge corpus...")
    try:
        load_corpus()
    except Exception as exc:
        logger.warning("Assistant corpus load failed (non-fatal): %s", exc)

    logger.info("Initializing Playwright browser for PDF export...")
    try:
        from backend.services.report_pdf import init_browser
        await init_browser()
    except Exception as exc:
        logger.warning("Playwright browser init failed (PDF export unavailable): %s", exc)

    yield

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
