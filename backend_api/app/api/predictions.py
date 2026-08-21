"""Predictive analytics endpoints (Tier 2 of the excluded-scope build).

Advisory forecasts from the trained risk forecaster — never replaces the
rule-based Context Engine. Both endpoints degrade honestly: with insufficient
data or a weak model agreement they return ``insufficient_data`` /
fallback-based forecasts rather than fabricated numbers.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user, can_view_all_sessions
from app.core.security import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predictions"])


@router.get("/predictions/next-window")
async def predict_next_window(
    user: AuthenticatedUser = Depends(get_current_user),
    horizon_seconds: float = 600.0,
):
    """Forecast mean risk over the next ``horizon_seconds`` from the live session.

    Uses the recent live timeline (last ~150 processed frames). Requires an
    active session; otherwise returns a clear idle state.
    """
    from app.services.live_monitor import get_live_service_or_none
    from backend.services.predictive import get_risk_forecaster

    service = get_live_service_or_none()
    if service is None:
        raise HTTPException(status_code=503, detail="Live monitoring service is unavailable.")
    if not service.is_running():
        return {
            "forecast": None,
            "insufficient_data": True,
            "reason": "No active session — start monitoring to get a forecast",
        }

    frames = service.get_recent_timeline(200)
    forecast = get_risk_forecaster().predict_next_window(frames, horizon_seconds)
    return {"forecast": forecast, "session_id": service.state.session_id}


@router.get("/predictions/session-forecast")
async def predict_session_forecast(
    user: AuthenticatedUser = Depends(get_current_user),
    session_id: str | None = None,
):
    """Forecast a session's full risk profile from its early portion.

    When ``session_id`` is given, the early frames are read from the persisted
    timeline (Postgres or files). Otherwise the live session's recent frames
    are used.
    """
    from app.services.live_monitor import get_live_service_or_none
    from backend.services.predictive import get_risk_forecaster

    if session_id:
        frames = _load_session_early_frames(session_id, user)
        if frames is None:
            return {
                "forecast": None,
                "insufficient_data": True,
                "reason": f"Session {session_id} not found or no timeline data",
            }
        forecast = get_risk_forecaster().predict_early_session(frames)
        return {"forecast": forecast, "session_id": session_id}

    service = get_live_service_or_none()
    if service is None:
        raise HTTPException(status_code=503, detail="Live monitoring service is unavailable.")
    if not service.is_running():
        return {
            "forecast": None,
            "insufficient_data": True,
            "reason": "No active session — start monitoring to get a forecast",
        }
    frames = service.get_recent_timeline(200)
    forecast = get_risk_forecaster().predict_early_session(frames)
    return {"forecast": forecast, "session_id": service.state.session_id}


def _load_session_early_frames(session_id: str, user: AuthenticatedUser) -> list | None:
    """Load the first portion of a persisted session's timeline (role-gated)."""
    from app.services.session_cache import get_all_sessions

    match = None
    for s in get_all_sessions():
        if s.get("session_id") == session_id:
            match = s
            break
    if match is None:
        return None
    if user is not None and not can_view_all_sessions(user):
        if match.get("created_by_user_id") != user.id:
            return None

    from app.core.postgres import pg_enabled, fetch_frames
    if pg_enabled():
        frames = fetch_frames(session_id)
        if frames:
            # Keep the early portion (first ~20% of frames).
            n = max(30, int(len(frames) * 0.2))
            return frames[:n]
    # File fallback: read the recording timeline.json via the session store.
    try:
        from app.core.postgres import iter_timeline_files
        from pathlib import Path
        for payload, frames in iter_timeline_files(str(Path(__file__).resolve().parents[3])):
            if payload.get("session_id") == session_id and frames:
                n = max(30, int(len(frames) * 0.2))
                return frames[:n]
    except Exception as exc:
        logger.warning("File fallback for session forecast failed: %s", exc)
    return None
