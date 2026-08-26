"""Manager dashboard endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_repository
from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository, RepositoryUnavailableError
from app.schemas.api import ManagerSummary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/manager", response_model=ManagerSummary)
async def get_manager(
    repo: DashboardRepository = Depends(get_repository),
    _: AuthenticatedUser = Depends(require_roles("safety_mgr", "admin")),
):
    """Factory-wide manager summary — workers online, risk counts, compliance.

    Fails closed with 503 when the underlying data cannot be read — the
    manager dashboard must never render placeholder numbers as real ones.
    """
    try:
        return await repo.get_manager()
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
