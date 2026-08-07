"""Trend analysis endpoints."""

import logging
from fastapi import APIRouter, Depends

from app.core.deps import get_repository
from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository
from app.schemas.api import TrendResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/trends", response_model=TrendResponse)
async def get_trends(
    repo: DashboardRepository = Depends(get_repository),
    _: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Weekly trends, feature trends, and risk distribution."""
    return await repo.get_trends()
