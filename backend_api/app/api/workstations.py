"""Workstation endpoints."""

import logging
from typing import List
from fastapi import APIRouter, Depends

from app.core.deps import get_repository
from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository
from app.schemas.api import WorkstationInfo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/workstations", response_model=List[WorkstationInfo])
async def get_workstations(
    repo: DashboardRepository = Depends(get_repository),
    _: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """All workstations with current posture and worker info."""
    return await repo.get_workstations()
