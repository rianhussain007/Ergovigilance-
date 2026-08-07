"""Dashboard endpoints."""

import logging
import os
import time
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, require_live_session_access, require_roles
from app.core.database import (
    count_users,
    count_users_by_role,
    count_workers,
    database_is_healthy,
)
from app.core.health import health_status
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service, get_live_service_or_none

from app.core.deps import get_repository
from app.repositories.base import DashboardRepository
from app.schemas.api import (
    AdminDashboardSummary,
    DashboardResponse,
    RecentAlertSummary,
    RecentSessionSummary,
    SupervisorDashboardSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_session_date(value: str) -> date | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        pass
    for fmt in ("%Y%m%d_%H%M%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _risk_score_from_level(value: str) -> float | None:
    normalized = (value or "").upper()
    if normalized == "LOW" or normalized == "LOW_RISK" or normalized == "LOW RISK":
        return 0.0
    if normalized in {"MEDIUM", "MODERATE", "MEDIUM_RISK", "MEDIUM RISK"}:
        return 50.0
    if normalized == "HIGH" or normalized == "HIGH_RISK" or normalized == "HIGH RISK":
        return 100.0
    return None


def _average_risk_from_session_detail(detail) -> float | None:
    risk_pct = detail.risk_percentages or {}
    weighted = 0.0
    total = 0.0
    for key, score in (("LOW", 0.0), ("MEDIUM", 50.0), ("HIGH", 100.0)):
        pct = risk_pct.get(key)
        if pct is None:
            continue
        weighted += float(pct) * score
        total += float(pct)
    if total > 0:
        return weighted / total
    return _risk_score_from_level(detail.highest_risk_level)


def _count_saved_session_files() -> int:
    """Count session files on disk. Cached for 30s to avoid repeated dir scans."""
    global _session_file_count, _session_file_count_time
    now = time.time()
    if _session_file_count is not None and (now - _session_file_count_time) < 30:
        return _session_file_count
    sessions_dir = Path(os.environ.get(
        "SESSIONS_DIR",
        Path(__file__).resolve().parents[3] / "outputs" / "sessions",
    ))
    if not sessions_dir.exists():
        _session_file_count = 0
    else:
        _session_file_count = sum(1 for path in sessions_dir.iterdir() if path.name.startswith("session_") and path.suffix == ".json")
    _session_file_count_time = now
    return _session_file_count


_session_file_count: int | None = None
_session_file_count_time: float = 0


async def _build_supervisor_summary(repo: DashboardRepository, user: AuthenticatedUser) -> SupervisorDashboardSummary:
    sessions = await repo.get_sessions(current_user=user)
    alerts = await repo.get_alerts_summary(recent_n=6)
    today = date.today()

    sessions_today = sum(1 for session in sessions if _parse_session_date(session.date) == today)
    recent_sessions = [
        RecentSessionSummary(
            id=session.id,
            date=session.date,
            duration=session.duration,
            highestRisk=session.highestRisk,
            task=session.task,
            status=session.status,
            worker_id=session.worker_id,
        )
        for session in sessions[:6]
    ]
    recent_alerts = [
        RecentAlertSummary(
            id=alert.id,
            title=alert.title,
            severity=alert.severity,
            state=alert.state,
            created_at=alert.created_at,
            session_id=alert.session_id,
        )
        for alert in alerts.history
    ]

    risk_values: list[float] = []
    for session in sessions:
        if session.status == "active":
            dashboard = await repo.get_dashboard()
            risk_values.append(float(dashboard.liveStatus.riskScore))
            continue
        score = _risk_score_from_level(session.highestRisk)
        if score is not None:
            risk_values.append(score)

    average_risk = round(sum(risk_values) / len(risk_values), 1) if risk_values else None

    return SupervisorDashboardSummary(
        worker_count=count_workers(),
        sessions_today=sessions_today,
        open_alerts=alerts.summary.active_count,
        average_risk=average_risk,
        recent_sessions=recent_sessions,
        recent_alerts=recent_alerts,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Current session dashboard — live status, features, issues, recommendations."""
    service = get_live_service_or_none()
    if service is not None:
        require_live_session_access(user, service)
    return await repo.get_dashboard()


@router.get("/session/latest", response_model=DashboardResponse)
async def get_latest_session(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Latest completed or active session data."""
    service = get_live_service_or_none()
    if service is not None:
        require_live_session_access(user, service)
    return await repo.get_latest_session()


@router.get("/dashboard/supervisor-summary", response_model=SupervisorDashboardSummary)
async def get_supervisor_dashboard_summary(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Role-gated aggregate summary for visible workers and sessions."""
    return await _build_supervisor_summary(repo, user)


@router.get("/dashboard/admin-summary", response_model=AdminDashboardSummary)
async def get_admin_dashboard_summary(
    repo: DashboardRepository = Depends(get_repository),
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Admin-only system and aggregate dashboard summary."""
    base = await _build_supervisor_summary(repo, user)
    service = get_live_service_or_none()
    backend = health_status()
    active_session_count = 0
    connected_camera_status = "disconnected"
    if service is not None:
        state = service.get_state_snapshot()
        active_session_count = 1 if state.session_active else 0
        connected_camera_status = state.camera_status

    return AdminDashboardSummary(
        **base.model_dump(),
        total_users=count_users(),
        total_sessions=_count_saved_session_files() + active_session_count,
        backend_status=backend.get("status", "unknown"),
        database_status="healthy" if database_is_healthy() else "unhealthy",
        connected_camera_status=connected_camera_status,
        role_distribution=count_users_by_role(),
    )
