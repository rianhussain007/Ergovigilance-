"""Shared module-level cache for parsed session file data.

LiveRepository is instantiated per-request (FastAPI Depends), so
instance/class attrs are lost between requests. These module-level
vars persist for the lifetime of the Python process.

Follows the same pattern as _camera_cache in app/repositories/live.py.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _resolve_sessions_dir() -> str:
    """Locate the sessions directory across the local and container layouts.

    Local:  backend_api/app/services/ -> project_root/outputs/sessions (3 levels)
    Docker: /app/app/services/        -> /app/outputs/sessions (2 levels, the
            Dockerfile copies backend_api/app to /app/app). SESSIONS_DIR env
            overrides both (compose sets it to /data/sessions for persistence).
    """
    env_dir = os.environ.get("SESSIONS_DIR")
    if env_dir:
        return env_dir
    root = Path(__file__).resolve().parents[3]
    if not (root / "outputs").is_dir() and (Path(__file__).resolve().parents[2] / "app").is_dir():
        root = Path(__file__).resolve().parents[2]  # container layout
    return os.path.join(str(root), "outputs", "sessions")


SESSIONS_DIR = _resolve_sessions_dir()

_session_cache: list[dict[str, Any]] | None = None
_session_cache_time: float = 0
_session_source: str = "file"  # "file" or "postgres"
# Sessions only change when a session ends (invalidate_session_cache() is
# called on stop), so the TTL is only a safety net — keep it long to avoid
# the ~400ms full rescan of every session file on disk (99 files as of
# 2026-08-12) every few minutes. Freshness is guaranteed by the invalidation
# on stop.
SESSION_CACHE_TTL: float = 1800.0  # seconds (30 min)


def _scan_session_files() -> list[dict[str, Any]]:
    """Scan and parse all session JSON files from disk."""
    sessions: list[dict[str, Any]] = []
    if not os.path.isdir(SESSIONS_DIR):
        return sessions
    for filename in os.listdir(SESSIONS_DIR):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(SESSIONS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append(data)
        except Exception as exc:
            logger.warning("Failed to read session file %s: %s", filename, exc)
    return sessions


def get_all_sessions() -> list[dict[str, Any]]:
    """Return cached parsed session list.

    Prefers the Postgres telemetry store when configured (fast indexed query);
    falls back to scanning JSON files. Re-reads only if the cache is stale
    (TTL exceeded) or the source changed.
    """
    global _session_cache, _session_cache_time, _session_source
    now = time.time()
    if _session_cache is not None and (now - _session_cache_time) < SESSION_CACHE_TTL:
        return _session_cache

    from app.core.postgres import pg_enabled, fetch_sessions
    if pg_enabled():
        rows = fetch_sessions()
        if rows:
            _session_cache = rows
            _session_source = "postgres"
            _session_cache_time = now
            logger.debug("Session cache refreshed — %d sessions from Postgres", len(rows))
            return _session_cache
        logger.debug("Postgres store empty — falling back to session files")

    _session_cache = _scan_session_files()
    _session_source = "file"
    _session_cache_time = now
    logger.debug("Session cache refreshed — %d sessions loaded", len(_session_cache))
    return _session_cache


def prewarm_session_cache() -> None:
    """Build the session cache once, eagerly (call from a background thread).

    The first ``get_all_sessions()`` call scans and parses every session JSON
    file on disk, which takes seconds with many files — prewarming moves that
    cost to startup so the first API request is served from cache.
    """
    global _session_cache, _session_cache_time
    try:
        _session_cache = _scan_session_files()
        _session_cache_time = time.time()
        logger.info("Session cache prewarmed — %d sessions loaded", len(_session_cache))
    except Exception as exc:
        logger.warning("Session cache prewarm failed (will build lazily): %s", exc)


def invalidate_session_cache() -> None:
    """Force re-read on next call to get_all_sessions().

    Call this after saving a new session so the new session appears
    immediately without waiting for the TTL to expire.
    """
    global _session_cache, _session_source
    _session_cache = None
    _session_source = "file"
    logger.debug("Session cache invalidated")


def cache_source() -> str:
    """Which store the cache last read from ('file' or 'postgres')."""
    global _session_source
    return _session_source


def get_cache_info() -> dict:
    """Return cache diagnostics (for debugging/monitoring)."""
    global _session_cache, _session_cache_time
    return {
        "cached": _session_cache is not None,
        "age_seconds": round(time.time() - _session_cache_time, 1) if _session_cache is not None else None,
        "ttl_seconds": SESSION_CACHE_TTL,
        "session_count": len(_session_cache) if _session_cache is not None else None,
    }
