"""Dependency injection for FastAPI."""

import logging

from fastapi import HTTPException, status

from app.core.config import settings
from app.repositories.mock import MockRepository
from app.repositories.live import LiveRepository
from app.repositories.base import DashboardRepository
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)


def get_repository() -> DashboardRepository:
    """Resolve the data repository for a request.

    Mock mode is only ever entered explicitly via USE_MOCK_REPOSITORY=true.
    In live mode we fail closed: if the live monitoring service is unavailable
    we return HTTP 503 rather than silently serving mock data, which would
    present fabricated numbers as if they were real.
    """
    if settings.USE_MOCK_REPOSITORY:
        return MockRepository()

    try:
        get_live_service()
        return LiveRepository()
    except Exception as exc:  # noqa: BLE001 - fail closed, never mask with mock data
        logger.error("Live monitoring service unavailable — failing closed with 503: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live monitoring service is unavailable. "
            "Start the backend with the pose model present, or set USE_MOCK_REPOSITORY=true for demo mode.",
        ) from exc
