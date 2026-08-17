"""Recorded session replay endpoints."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser, decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

RECORDINGS_DIR = os.environ.get(
    "RECORDINGS_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")),
)

# ── Module-level cache ────────────────────────────────────────────────
# Walking the recordings tree and parsing every summary.json took 0.4-0.6s
# per request (the slowest endpoint when idle) and was repeated 3x per
# ReplayPage view (list + summary + timeline lookups). Recordings only
# change when a session stops, so a 60s TTL cache is safe and makes every
# navigation instant.
_RECORDINGS_CACHE_TTL = 300.0

_recordings_cache: list[dict] | None = None
_recordings_cache_time: float = 0.0
_dir_index: dict[str, str] | None = None  # session_id -> recording dir
_dir_index_time: float = 0.0


def _scan_recordings() -> list[dict]:
    """Walk the recordings tree once and build the listing + dir index."""
    global _dir_index, _dir_index_time  # noqa: PLW0603
    base = Path(RECORDINGS_DIR)
    recordings: list[dict] = []
    index: dict[str, str] = {}
    if base.exists():
        for worker_dir in sorted(base.iterdir()):
            if not worker_dir.is_dir():
                continue
            for session_dir in sorted(worker_dir.iterdir()):
                summary_path = session_dir / "summary.json"
                timeline_path = session_dir / "timeline.json"
                video_path = session_dir / "original.mp4"
                if summary_path.exists():
                    try:
                        with open(summary_path) as f:
                            summary = json.load(f)
                        session_id = summary.get("session_id", session_dir.name)
                        index[session_id] = str(session_dir)
                        recordings.append({
                            "session_id": session_id,
                            "session_timestamp": summary.get("session_timestamp", session_dir.name),
                            "worker_id": summary.get("worker_id", worker_dir.name),
                            "duration_seconds": summary.get("session_duration_seconds", 0),
                            "total_frames": summary.get("total_frames", 0),
                            "highest_risk_level": summary.get("highest_risk_level", "LOW"),
                            "risk_level": summary.get("risk_level") or summary.get("highest_risk_level", "LOW"),
                            "risk_percentages": summary.get("risk_percentages", {}),
                            "has_video": video_path.exists(),
                            "has_timeline": timeline_path.exists(),
                        })
                    except (json.JSONDecodeError, OSError):
                        continue
    _dir_index = index
    _dir_index_time = time.time()
    return recordings


def _get_recordings() -> list[dict]:
    global _recordings_cache, _recordings_cache_time  # noqa: PLW0603
    now = time.time()
    if _recordings_cache is not None and (now - _recordings_cache_time) < _RECORDINGS_CACHE_TTL:
        return _recordings_cache
    _recordings_cache = _scan_recordings()
    _recordings_cache_time = now
    return _recordings_cache


def _find_recording_dir(session_id: str) -> Optional[str]:
    """Find a recording directory by session_id (cached index, O(1) lookup)."""
    global _dir_index, _dir_index_time  # noqa: PLW0603
    now = time.time()
    if _dir_index is None or (now - _dir_index_time) >= _RECORDINGS_CACHE_TTL:
        # Rebuild the index (also refreshes the listing cache).
        _scan_recordings()
    return (_dir_index or {}).get(session_id)


def invalidate_recordings_cache() -> None:
    """Force a rescan on the next request (called when a session stops)."""
    global _recordings_cache, _recordings_cache_time, _dir_index, _dir_index_time  # noqa: PLW0603
    _recordings_cache = None
    _dir_index = None


def prewarm_recordings_cache() -> None:
    """Build the recordings cache once at startup (background thread).

    The first listing after a restart walks the whole tree (~0.25s here);
    prewarming moves that cost to startup so the first page that lists
    recordings is already served from cache.
    """
    try:
        _get_recordings()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Recordings cache prewarm failed (will build lazily): %s", exc)


@router.get("/recordings")
async def list_recordings(_: AuthenticatedUser = Depends(get_current_user)):
    """List all recorded sessions (cached, 60s TTL)."""
    return {"recordings": _get_recordings()}


@router.get("/recordings/{session_id}/summary")
async def get_recording_summary(
    session_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Get the summary for a recorded session."""
    rec_dir = _find_recording_dir(session_id)
    if not rec_dir:
        raise HTTPException(status_code=404, detail=f"Recording {session_id} not found")
    summary_path = Path(rec_dir) / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this recording")
    try:
        with open(summary_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read summary: {exc}")


@router.get("/recordings/{session_id}/timeline")
async def get_recording_timeline(
    session_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Get the full timeline for a recorded session."""
    rec_dir = _find_recording_dir(session_id)
    if not rec_dir:
        raise HTTPException(status_code=404, detail=f"Recording {session_id} not found")
    timeline_path = Path(rec_dir) / "timeline.json"
    if not timeline_path.exists():
        raise HTTPException(status_code=404, detail="Timeline not found for this recording")
    try:
        with open(timeline_path) as f:
            return {"timeline": json.load(f)}
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read timeline: {exc}")


@router.get("/recordings/{session_id}/video")
async def get_recording_video(
    session_id: str,
    token: str = Query(None),
    raw: bool = Query(False),
):
    """Stream the MP4 video for a recorded session.
    
    Accepts optional `token` query param for <video> elements that
    cannot set the Authorization header directly.

    By default prefers the overlaid video (skeleton burned in) for the
    Replay screen. Pass ``raw=true`` to force the clean original — the
    Video Review screen needs this because it draws its own analysis
    skeleton on a canvas; playing the pre-burned overlay would stack two
    skeletons from different runs on top of each other.
    """
    if token:
        try:
            decode_access_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    rec_dir = _find_recording_dir(session_id)
    if not rec_dir:
        raise HTTPException(status_code=404, detail=f"Recording {session_id} not found")
    if raw:
        video_path = Path(rec_dir) / "original.mp4"
    else:
        # Prefer the overlaid video (skeleton burned in) when available
        overlay_path = Path(rec_dir) / "overlay.mp4"
        video_path = overlay_path if overlay_path.exists() else Path(rec_dir) / "original.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found for this recording")
    return FileResponse(str(video_path), media_type="video/mp4")
