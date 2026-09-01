"""Audit log API endpoints for SOC2 compliance.

Provides endpoints for querying, exporting, and verifying audit logs.
Only accessible to admin and safety_mgr roles.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from app.core.auth import require_roles
from app.core.audit_log import audit_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit-log", tags=["Audit Log"])


@router.get("")
async def list_audit_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    since_hours: Optional[int] = Query(24, description="Entries from last N hours"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(500, le=5000, description="Max entries to return"),
    current_user=Depends(require_roles("admin", "safety_mgr")),
):
    """Query audit log entries with optional filters."""
    entries = audit_logger.query(
        event_type=event_type,
        user_id=user_id,
        since_hours=since_hours,
        severity=severity,
        limit=limit,
    )
    return {
        "entries": entries,
        "total": len(entries),
        "filters": {
            "event_type": event_type,
            "user_id": user_id,
            "since_hours": since_hours,
            "severity": severity,
        },
    }


@router.get("/export/json")
async def export_audit_json(
    since_hours: int = Query(168, description="Export entries from last N hours (default: 7 days)"),
    current_user=Depends(require_roles("admin")),
):
    """Export audit logs as JSON for compliance."""
    entries = audit_logger.query(since_hours=since_hours, limit=10000)
    json_data = audit_logger.export_json(entries)
    return PlainTextResponse(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_log_export.json"},
    )


@router.get("/export/csv")
async def export_audit_csv(
    since_hours: int = Query(168, description="Export entries from last N hours (default: 7 days)"),
    current_user=Depends(require_roles("admin")),
):
    """Export audit logs as CSV for compliance."""
    entries = audit_logger.query(since_hours=since_hours, limit=10000)
    csv_data = audit_logger.export_csv(entries)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log_export.csv"},
    )


@router.get("/verify")
async def verify_integrity(
    current_user=Depends(require_roles("admin")),
):
    """Verify audit log chain integrity (tamper detection)."""
    result = audit_logger.verify_integrity()
    return result


@router.get("/stats")
async def audit_stats(
    current_user=Depends(require_roles("admin", "safety_mgr")),
):
    """Get audit log statistics."""
    entries_24h = audit_logger.query(since_hours=24, limit=10000)
    entries_7d = audit_logger.query(since_hours=168, limit=10000)

    event_counts = {}
    for entry in entries_24h:
        event_type = entry.get("event_type", "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    severity_counts = {}
    for entry in entries_24h:
        severity = entry.get("severity", "info")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    return {
        "entries_last_24h": len(entries_24h),
        "entries_last_7d": len(entries_7d),
        "event_counts_24h": event_counts,
        "severity_counts_24h": severity_counts,
    }
