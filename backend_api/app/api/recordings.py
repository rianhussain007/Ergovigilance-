"""Recorded session replay endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser, decode_access_token

router = APIRouter()

RECORDINGS_DIR = os.environ.get(
    "RECORDINGS_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")),
)


def _find_recording_dir(session_id: str) -> Optional[str]:
    """Find a recording directory by scanning for a matching summary.json."""
    base = Path(RECORDINGS_DIR)
    if not base.exists():
        return None
    for worker_dir in base.iterdir():
        if not worker_dir.is_dir():
            continue
        for session_dir in worker_dir.iterdir():
            summary_path = session_dir / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path) as f:
                        summary = json.load(f)
                    if summary.get("session_id") == session_id:
                        return str(session_dir)
                except (json.JSONDecodeError, OSError):
                    continue
    return None


@router.get("/recordings")
async def list_recordings(_: AuthenticatedUser = Depends(get_current_user)):
    """List all recorded sessions."""
    base = Path(RECORDINGS_DIR)
    if not base.exists():
        return {"recordings": []}

    recordings = []
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
                    recordings.append({
                        "session_id": summary.get("session_id", session_dir.name),
                        "session_timestamp": summary.get("session_timestamp", session_dir.name),
                        "worker_id": summary.get("worker_id", worker_dir.name),
                        "duration_seconds": summary.get("session_duration_seconds", 0),
                        "total_frames": summary.get("total_frames", 0),
                        "highest_risk_level": summary.get("highest_risk_level", "LOW"),
                        "risk_percentages": summary.get("risk_percentages", {}),
                        "has_video": video_path.exists(),
                        "has_timeline": timeline_path.exists(),
                    })
                except (json.JSONDecodeError, OSError):
                    continue
    return {"recordings": recordings}


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
):
    """Stream the MP4 video for a recorded session.
    
    Accepts optional `token` query param for <video> elements that
    cannot set the Authorization header directly.
    """
    if token:
        try:
            decode_access_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    rec_dir = _find_recording_dir(session_id)
    if not rec_dir:
        raise HTTPException(status_code=404, detail=f"Recording {session_id} not found")
    video_path = Path(rec_dir) / "original.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found for this recording")
    return FileResponse(str(video_path), media_type="video/mp4")
