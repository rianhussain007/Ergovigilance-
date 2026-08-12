"""Alerts / notifications endpoints."""

import logging
import uuid
import json
import math
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_repository
from app.core.auth import get_current_user, require_live_session_access, require_roles
from app.core.security import AuthenticatedUser
from app.core.database import insert_audit_log
from app.services.live_monitor import get_live_service_or_none
from app.repositories.base import DashboardRepository
from app.schemas.api import Alert, AlertResponse, AlertsResponse, AlertsHistoryResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_live_service():
    """Return the live monitoring service or a clean 503 instead of a raw 500.

    get_live_service() raises RuntimeError when the service was never
    initialized (e.g. the pose model was missing at startup), which FastAPI
    would otherwise surface as an unhandled 500.
    """
    service = get_live_service_or_none()
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Live monitoring service is not initialized (pose model unavailable at startup?)",
        )
    return service


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Active alerts, last 20 history entries, and summary from the Alert Engine.

    Full history is available at GET /api/alerts/history with pagination.
    """
    service = _require_live_service()
    require_live_session_access(user, service)
    return await repo.get_alerts_summary(recent_n=20)


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Acknowledge an active alert. Allowed for supervisor, safety_mgr, admin."""
    service = _require_live_service()
    require_live_session_access(user, service)

    engine = service.alert_engine
    alert = engine.get_alert_by_id(alert_id)
    if not engine.acknowledge(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found or not in ACTIVE state")

    # Log to audit trail
    details = json.dumps({"severity": alert.severity.value, "title": alert.title}) if alert else None
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="alert_acknowledged",
        target_type="alert",
        target_id=alert_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )

    updated = engine.get_alert_by_id(alert_id)
    return AlertResponse(**updated.to_dict())


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: str,
    user: AuthenticatedUser = Depends(require_roles("safety_mgr", "admin")),
):
    """Resolve an active or acknowledged alert. Allowed for safety_mgr and admin only."""
    service = _require_live_service()
    require_live_session_access(user, service)

    engine = service.alert_engine
    alert = engine.get_alert_by_id(alert_id)
    if not engine.resolve(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found or not in ACKNOWLEDGED/ACTIVE state")

    # Log to audit trail
    details = json.dumps({"severity": alert.severity.value, "title": alert.title}) if alert else None
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="alert_resolved",
        target_type="alert",
        target_id=alert_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )

    updated = engine.get_alert_by_id(alert_id)
    return AlertResponse(**updated.to_dict())


@router.get("/alerts/history", response_model=AlertsHistoryResponse)
async def get_alerts_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Paginated full alert history. Not polled — called on-demand by NotificationCenter."""
    service = _require_live_service()
    engine = service.alert_engine
    export = engine.export()
    all_history = export.get("history", [])
    total = len(all_history)
    pages = max(1, math.ceil(total / limit))
    start = (page - 1) * limit
    chunk = all_history[start:start + limit]
    alerts = [AlertResponse(**a) for a in chunk]
    return AlertsHistoryResponse(alerts=alerts, total=total, page=page, pages=pages)
