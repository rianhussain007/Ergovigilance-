"""Risk History endpoint."""

from fastapi import APIRouter, Depends

from app.core.deps import get_repository
from app.core.auth import get_current_user, require_live_session_access
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service
from app.repositories.base import DashboardRepository
from app.schemas.api import HistoryResponse

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Risk history from the History Engine.

    Returns all recorded data points and aggregated statistics.
    Returns empty points when no session is active.
    """
    require_live_session_access(user, get_live_service())
    return await repo.get_history()
