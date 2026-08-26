"""Dependency injection for FastAPI."""

import logging

from fastapi import HTTPException, status

from app.repositories.live import LiveRepository
from app.repositories.base import DashboardRepository
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)


def get_repository() -> DashboardRepository:
    """Resolve the data repository for a request.

    There is exactly one repository: the live one. If the live monitoring
    service is unavailable we fail closed with HTTP 503 rather than ever
    serving fabricated numbers as if they were real.
    """
    try:
        get_live_service()
        return LiveRepository()
    except Exception as exc:  # noqa: BLE001 - fail closed, never mask with fake data
        logger.error("Live monitoring service unavailable — failing closed with 503: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live monitoring service is unavailable. "
            "Start the backend with the pose model present.",
        ) from exc
