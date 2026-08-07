"""Live session timeline endpoint — returns recent TimelineEntry objects."""

import logging
from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user, require_live_session_access
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/session/timeline/recent")
async def get_live_timeline(
    n: int = Query(200, ge=1, le=1000, description="Number of recent entries"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return the last *n* timeline entries from the current live session.

    Each entry matches the TimelineEntry TypeScript interface:
      { timestamp, frame_number, risk_score, risk_level, confidence,
        features, fatigue, exposure, context_score, current_task,
        task_duration_seconds, recommendations, alerts,
        unavailable_features, lower_body_confidence }
    """
    service = get_live_service()
    require_live_session_access(user, service)
    entries = service.get_recent_timeline(n)
    return {"timeline": entries}
