"""Deployment / infrastructure endpoints."""

import logging
from fastapi import APIRouter, Depends

from app.core.deps import get_repository
from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository
from app.schemas.api import DeploymentMetrics

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/deployment", response_model=DeploymentMetrics)
async def get_deployment(
    repo: DashboardRepository = Depends(get_repository),
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Infrastructure metrics — edge devices, cameras, storage, models."""
    return await repo.get_deployment()
