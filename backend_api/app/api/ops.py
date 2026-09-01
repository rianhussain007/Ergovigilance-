"""Operational endpoints — liveness, readiness, and Prometheus metrics.

- ``/healthz``  — liveness. Always 200 once the process is serving.
- ``/readyz``   — readiness. 200 only when the app can serve real requests
  (database reachable, and in live mode the monitoring service is initialized).
- ``/metrics``  — Prometheus text exposition (via prometheus-client).

These live at the root (not under ``/api``) so load balancers, orchestrators,
and Docker healthchecks can probe them without auth.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    REGISTRY,
    generate_latest,
)

from app.core.config import settings
from app.core.database import database_is_healthy
from app.core.health import get_uptime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Operations"])

# Single source of truth for the model path (see config.POSE_MODEL_PATH).

# --- Metrics -----------------------------------------------------------------
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests served",
    ["method", "route", "status"],
)
ACTIVE_SESSIONS = Gauge("ergo_active_sessions", "Active monitoring sessions (0 or 1 for the local service)")
UPTIME = Gauge("ergo_uptime_seconds", "Seconds since the API process started")


def _live_service_initialized() -> bool:
    try:
        from app.services.live_monitor import is_live_service_initialized

        return is_live_service_initialized()
    except Exception:  # noqa: BLE001 - never let a probe fail readiness
        return False


def _active_session_count() -> float:
    try:
        from app.services.live_monitor import get_live_service

        service = get_live_service()
        return 1.0 if service.is_running() else 0.0
    except Exception:  # noqa: BLE001 - service not initialized / stopped
        return 0.0


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe — always 200 while the process is up."""
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz() -> JSONResponse:
    """Readiness probe — 503 until the app can serve real requests."""
    checks: dict[str, Any] = {"database": database_is_healthy()}
    checks["live_service"] = _live_service_initialized()
    checks["model_available"] = os.path.exists(settings.POSE_MODEL_PATH)

    # Live mode only: the service must be initialized or requests fail closed
    # with 503 — there is no demo-data fallback anymore.
    ready = checks["database"] and checks["live_service"]
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
        },
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics in text exposition format."""
    ACTIVE_SESSIONS.set(_active_session_count())
    UPTIME.set(get_uptime())
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@router.get("/sla", include_in_schema=False)
async def sla_status() -> dict:
    """SLA compliance status — availability, response times, incidents."""
    from app.core.sla_monitor import sla_monitor
    return sla_monitor.get_status()


@router.get("/storage", include_in_schema=False)
async def storage_stats() -> dict:
    """Storage usage — recordings, alerts, reports, disk space."""
    from app.core.storage_manager import storage_manager
    stats = storage_manager.get_stats()
    disk = storage_manager.get_disk_info()
    return {
        "usage": {
            "total_mb": stats.total_size_mb,
            "max_mb": stats.max_size_mb,
            "usage_percent": stats.usage_percent,
            "recordings": {
                "size_mb": stats.recordings_size_mb,
                "count": stats.recordings_count,
            },
            "alerts": {
                "size_mb": stats.alerts_size_mb,
                "count": stats.alerts_count,
            },
            "reports": {
                "size_mb": stats.reports_size_mb,
                "count": stats.reports_count,
            },
            "oldest_recording": stats.oldest_recording,
            "newest_recording": stats.newest_recording,
        },
        "disk": disk,
    }


@router.get("/cache", include_in_schema=False)
async def cache_stats() -> dict:
    """Response cache statistics — hit rate, entries, memory usage."""
    from app.core.response_cache import response_cache
    return response_cache.get_stats()


@router.get("/queries", include_in_schema=False)
async def query_stats() -> dict:
    """Database query performance — slow queries, top queries, latency."""
    from app.core.query_monitor import query_monitor
    return query_monitor.get_stats()


@router.get("/logs", include_in_schema=False)
async def log_stats() -> dict:
    """Logging configuration and file sizes."""
    from app.core.log_config import get_log_stats
    return get_log_stats()


@router.get("/recovery", include_in_schema=False)
async def recovery_stats() -> dict:
    """Auto-recovery monitor status."""
    from app.core.auto_recovery import recovery_monitor
    return recovery_monitor.get_status()


async def http_metrics_middleware(request: Request, call_next):
    """Count every HTTP request by method, path, and response status."""
    response = await call_next(request)
    try:
        HTTP_REQUESTS.labels(
            method=request.method,
            route=request.url.path,
            status=response.status_code,
        ).inc()
    except Exception:  # noqa: BLE001 - metrics must never break requests
        logger.debug("Failed to record metrics for %s", request.url.path)
    return response
