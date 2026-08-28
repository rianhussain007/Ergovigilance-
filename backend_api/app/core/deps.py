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

    If the live monitoring service is unavailable (e.g. no camera in Docker),
    fall back to session-cache mode for read-only endpoints (sessions,
    deployment, manager). Live-only endpoints (dashboard, alerts, context)
    will still fail closed with 503 if the service is truly unavailable.
    """
    try:
        get_live_service()
        return LiveRepository()
    except Exception as exc:  # noqa: BLE001
        # In Docker or headless deployments, the live service may not be
        # initialized.  Instead of 503-ing every endpoint, allow read-only
        # endpoints (sessions, deployment, manager) to work from the session
        # cache and SQLite database.  Live-only endpoints will still get 503
        # when they try to access live state.
        logger.warning("Live monitoring service unavailable — using session-cache fallback: %s", exc)
        return LiveRepository()
