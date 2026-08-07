"""Dependency injection for FastAPI."""

from app.core.config import settings
from app.repositories.mock import MockRepository
from app.repositories.live import LiveRepository
from app.repositories.base import DashboardRepository
from app.services.live_monitor import get_live_service


def get_repository() -> DashboardRepository:
    if settings.USE_MOCK_REPOSITORY:
        return MockRepository()
    try:
        get_live_service()
        return LiveRepository()
    except (RuntimeError, Exception):
        return MockRepository()
