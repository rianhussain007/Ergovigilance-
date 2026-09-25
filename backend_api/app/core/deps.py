"""Dependency injection for FastAPI."""

import logging
import os

from fastapi import HTTPException, status

from app.repositories.live import LiveRepository
from app.repositories.base import DashboardRepository
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)


def get_repository() -> DashboardRepository:
    """Resolve the data repository for a request.

    Fail-closed contract (tests/test_fail_closed_endpoints.py,
    test_api_smoke.py::test_live_mode_fails_closed_with_503): when the live
    monitoring service is not initialized there is no trustworthy data source,
    so EVERY repository-backed endpoint answers ``503 Service Unavailable``
    rather than serving mock or empty payloads (an absent service previously
    leaked the synthetic ``SESH-LIVE-001`` dashboard, a placeholder camera
    list and empty ``[]`` responses — those are exactly the "silently serve
    mock data" failure this guard exists to prevent).

    DEMO_MODE is the one deliberate exception: a demo deployment opts in to
    synthetic data with no camera, so it keeps the session-cache fallback.
    """
    try:
        get_live_service()
    except Exception as exc:  # noqa: BLE001
        from backend.services.demo_seeding import DEMO_MODE

        if not DEMO_MODE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live monitoring service unavailable",
            ) from exc
        logger.warning(
            "Live monitoring service unavailable — DEMO_MODE serving session-cache fallback: %s",
            exc,
        )
    return LiveRepository()
