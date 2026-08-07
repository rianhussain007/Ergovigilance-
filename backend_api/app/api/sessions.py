"""Session history endpoints."""

import logging
import math
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_repository
from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository
from app.schemas.api import SessionRecord, SessionDetailResponse, PaginatedSessionsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions", response_model=PaginatedSessionsResponse)
async def get_sessions(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(25, ge=1, le=200, description="Items per page"),
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Paginated session list. The full list is cached server-side (30s TTL);
    pagination is applied on top of the cached data so repeated requests for
    the same page are fast. Aggregation endpoints (analytics, reports, risk
    trend, safety report) consume the full list directly via session_cache
    and are NOT affected by this pagination."""
    all_sessions = await repo.get_sessions(current_user=user)
    total = len(all_sessions)
    pages = max(1, math.ceil(total / limit))
    start = (page - 1) * limit
    chunk = all_sessions[start:start + limit]
    return PaginatedSessionsResponse(sessions=chunk, total=total, page=page, pages=pages)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Full detail for a single saved session, read from the JSON file."""
    detail = await repo.get_session_detail(session_id, current_user=user)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return detail

