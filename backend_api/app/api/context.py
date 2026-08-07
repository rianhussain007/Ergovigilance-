"""Context Intelligence snapshot endpoint."""

from fastapi import APIRouter, Depends

from app.core.deps import get_repository
from app.core.auth import get_current_user, require_live_session_access
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service, get_live_service_or_none
from app.repositories.base import DashboardRepository
from app.schemas.api import ContextSnapshotResponse

router = APIRouter()


@router.get("/context/snapshot", response_model=ContextSnapshotResponse | None)
async def get_context_snapshot(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Current Context Intelligence snapshot from the live pipeline.

    Returns the latest ContextSnapshot produced by the ContextIntelligenceEngine.
    Returns null when no session is active.
    """
    service = get_live_service_or_none()
    if service is not None:
        require_live_session_access(user, service)
    return await repo.get_context_snapshot()
