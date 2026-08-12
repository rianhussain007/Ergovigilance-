"""Application configuration — loads from environment variables with sensible defaults."""

import json
import os
from typing import Literal


def parse_camera_sources(raw: str) -> list[dict]:
    """Parse the CAMERA_SOURCES env var (JSON array) into a list of camera dicts.

    Each entry: ``{"id": "dock-1", "name": "Loading Dock", "url": "rtsp://..."}``.
    Entries without both an id and a URL are dropped so a malformed row can never
    take down the whole list.
    """
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or "").strip()
        name = str(item.get("name") or cid or "IP Camera").strip()
        url = str(item.get("url") or "").strip()
        if cid and url:
            out.append({"id": cid, "name": name, "url": url})
    return out


class Settings:
    APP_NAME: str = "ErgoVigilance API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost"
    ).split(",")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    USE_MOCK_REPOSITORY: bool = (
        os.getenv("USE_MOCK_REPOSITORY", "false").lower() == "true"
    )
    # When true, client IPs are read from the X-Forwarded-For header (only set
    # this when the API sits behind a trusted reverse proxy that overwrites it).
    TRUST_PROXY_HEADERS: bool = (
        os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"
    )
    MOCK_DATA_DIR: str = os.getenv(
        "MOCK_DATA_DIR", "app/utils/mock_data"
    )
    AUTH_DB_PATH: str = os.getenv("AUTH_DB_PATH", "")
    # PostgreSQL/ TimescaleDB telemetry store (Tier 1). Empty = sessions stay
    # in JSON files (fully offline, current behavior). When set, session
    # summaries + per-frame timeline rows are mirrored into Postgres and reads
    # prefer the DB (fast indexed queries for analytics / predictive ML).
    # Example: postgresql://postgres:postgres@127.0.0.1:5432/ergovigilance
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    # When true and the DB is PostgreSQL with the timescaledb extension
    # installed, ergo_session_frames is created as a hypertable (time-series
    # partitioning + continuous aggregates). Safe to leave false — plain
    # PostgreSQL tables work identically for single-site scale.
    PG_TIMESCALEDB: bool = os.getenv("PG_TIMESCALEDB", "false").lower() == "true"
    POSE_MODEL_PATH: str = os.getenv(
        "POSE_MODEL_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "pose_landmarker_lite.task"),
    )
    # Configured IP/RTSP cameras: JSON array of {"id", "name", "url"}.
    # Physical USB cameras are auto-detected; these are added on top so
    # factory IP cameras (rtsp://...) appear in Settings + Multi-Camera.
    CAMERA_SOURCES: list[dict] = parse_camera_sources(os.getenv("CAMERA_SOURCES", ""))


settings = Settings()
