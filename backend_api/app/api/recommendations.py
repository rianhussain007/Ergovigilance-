"""Recommendation Engine endpoint."""

from fastapi import APIRouter, Depends

from app.core.deps import get_repository
from app.core.auth import get_current_user, require_live_session_access
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service, get_live_service_or_none
from app.repositories.base import DashboardRepository
from app.schemas.api import RecommendationsBundleResponse

router = APIRouter()


@router.get("/recommendations", response_model=RecommendationsBundleResponse)
async def get_recommendations(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Current recommendation bundle from the Recommendation Engine.

    Returns the latest RecommendationBundle produced by the RecommendationEngine.
    Returns empty bundle when no session is active.
    """
    service = get_live_service_or_none()
    if service is not None:
        require_live_session_access(user, service)
    return await repo.get_recommendations()
