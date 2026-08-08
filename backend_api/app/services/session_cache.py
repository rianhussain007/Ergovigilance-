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

SESSIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "outputs", "sessions"
)

_session_cache: list[dict[str, Any]] | None = None
_session_cache_time: float = 0
# Sessions only change when a session ends (invalidate_session_cache() is
# called on stop), so 5 minutes is plenty — a 30s TTL made every sessions
# poll re-scan + re-parse all session JSON files on disk (~3s for 66 files).
SESSION_CACHE_TTL: float = 300.0  # seconds


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

    Re-scans disk only if cache is stale (TTL exceeded).
    """
    global _session_cache, _session_cache_time
    now = time.time()
    if _session_cache is not None and (now - _session_cache_time) < SESSION_CACHE_TTL:
        return _session_cache
    _session_cache = _scan_session_files()
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
    """Force re-scan on next call to get_all_sessions().

    Call this after saving a new session file so the new session appears
    immediately without waiting for the TTL to expire.
    """
    global _session_cache
    _session_cache = None
    logger.debug("Session cache invalidated")


def get_cache_info() -> dict:
    """Return cache diagnostics (for debugging/monitoring)."""
    global _session_cache, _session_cache_time
    return {
        "cached": _session_cache is not None,
        "age_seconds": round(time.time() - _session_cache_time, 1) if _session_cache is not None else None,
        "ttl_seconds": SESSION_CACHE_TTL,
        "session_count": len(_session_cache) if _session_cache is not None else None,
    }
