"""Unified search endpoint — searches across sessions, workers, reports, and alerts."""

from fastapi import APIRouter, Query, Depends
from typing import Any
import os
import json
from pathlib import Path

from app.core.auth import get_current_user
from app.core.database import get_connection

router = APIRouter()

SESSIONS_DIR = Path("sessions")
WORKERS_DIR = Path("workers")


def _search_sessions(q: str, limit: int) -> list[dict]:
    """Search session files by ID, worker name, or risk level."""
    results = []
    if not SESSIONS_DIR.is_dir():
        return results
    ql = q.lower()
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        if len(results) >= limit:
            break
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sid = data.get("session_id", f.stem)
            worker = data.get("worker_name", data.get("worker_id", ""))
            risk = data.get("highest_risk", data.get("risk_level", ""))
            date = data.get("date", data.get("started_at", ""))
            duration = data.get("duration", "")
            task = data.get("current_task", data.get("task", ""))
            searchable = f"{sid} {worker} {risk} {task} {date}".lower()
            if ql in searchable:
                results.append({
                    "id": sid,
                    "label": f"Session {sid[:12]}",
                    "description": f"{worker} — {risk} risk — {duration}",
                    "route": "/sessions",
                    "category": "Sessions",
                    "type": "session",
                })
        except Exception:
            continue
    return results


def _search_workers(q: str, limit: int) -> list[dict]:
    """Search workers by name, employee ID, or department."""
    results = []
    if not WORKERS_DIR.is_dir():
        return results
    ql = q.lower()
    for f in sorted(WORKERS_DIR.glob("*.json")):
        if len(results) >= limit:
            break
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            name = data.get("name", "")
            emp_id = data.get("employee_id", data.get("worker_id", ""))
            dept = data.get("department", "")
            searchable = f"{name} {emp_id} {dept}".lower()
            if ql in searchable:
                results.append({
                    "id": emp_id,
                    "label": name,
                    "description": f"{emp_id} — {dept}",
                    "route": "/workers",
                    "category": "Workers",
                    "type": "worker",
                })
        except Exception:
            continue
    return results


def _search_audit(q: str, limit: int) -> list[dict]:
    """Search audit trail entries."""
    results = []
    ql = q.lower()
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, actor_email, action_type, target_type, target_id, timestamp, details "
            "FROM audit_log ORDER BY timestamp DESC LIMIT 200"
        ).fetchall()
        for row in rows:
            if len(results) >= limit:
                break
            searchable = f"{row['actor_email']} {row['action_type']} {row['target_type']} {row['target_id']} {row['details'] or ''}".lower()
            if ql in searchable:
                results.append({
                    "id": row["id"],
                    "label": f"{row['action_type'].replace('_', ' ').title()}",
                    "description": f"{row['actor_email']} — {row['target_type'] or ''} {row['target_id'] or ''} — {row['timestamp'][:16]}",
                    "route": "/audit",
                    "category": "Audit Trail",
                    "type": "audit",
                })
    except Exception:
        pass
    return results


def _search_navigation(q: str) -> list[dict]:
    """Match navigation items by name or description."""
    nav_items = [
        {"label": "Dashboard", "description": "Live monitoring overview", "route": "/dashboard", "category": "Navigation", "type": "nav"},
        {"label": "Live Monitoring", "description": "Real-time camera feed and pose analysis", "route": "/monitoring", "category": "Navigation", "type": "nav"},
        {"label": "Session History", "description": "Browse past monitoring sessions", "route": "/sessions", "category": "Navigation", "type": "nav"},
        {"label": "Reports", "description": "Safety, risk trend, and session reports", "route": "/reports", "category": "Navigation", "type": "nav"},
        {"label": "Analytics", "description": "Cross-session analytics and trends", "route": "/analytics", "category": "Navigation", "type": "nav"},
        {"label": "Workers", "description": "Worker profiles and enrollment", "route": "/workers", "category": "Navigation", "type": "nav"},
        {"label": "Settings", "description": "Theme, camera, notifications", "route": "/settings", "category": "Navigation", "type": "nav"},
        {"label": "Cloud Cameras", "description": "YOLO-based CCTV RTSP monitoring", "route": "/cloud-cameras", "category": "Navigation", "type": "nav"},
        {"label": "Cloud Settings", "description": "YOLO model and RTSP configuration", "route": "/cloud-settings", "category": "Navigation", "type": "nav"},
        {"label": "Model Dashboard", "description": "YOLO vs MediaPipe comparison", "route": "/model-dashboard", "category": "Navigation", "type": "nav"},
        {"label": "YOLO Demo", "description": "Upload image for pose detection", "route": "/yolo-demo", "category": "Navigation", "type": "nav"},
        {"label": "ROI Analytics", "description": "Cost savings and business case", "route": "/roi-analytics", "category": "Navigation", "type": "nav"},
        {"label": "System Health", "description": "Service status and metrics", "route": "/system-health", "category": "Navigation", "type": "nav"},
        {"label": "Video Review", "description": "Review recorded sessions", "route": "/video-review", "category": "Navigation", "type": "nav"},
        {"label": "Multi-Camera View", "description": "Grid view of all camera feeds", "route": "/cameras", "category": "Navigation", "type": "nav"},
        {"label": "Audit Trail", "description": "System activity log", "route": "/audit", "category": "Navigation", "type": "nav"},
        {"label": "Onboarding", "description": "Factory IT setup checklist", "route": "/onboarding", "category": "Navigation", "type": "nav"},
        {"label": "Manager Dashboard", "description": "Admin factory-wide ergonomic overview", "route": "/manager", "category": "Navigation", "type": "nav"},
        {"label": "User Management", "description": "Admin user roles and permissions", "route": "/users", "category": "Navigation", "type": "nav"},
        {"label": "Operator Dashboard", "description": "Operator view with personal posture tracking and alerts", "route": "/dashboard", "category": "Navigation", "type": "nav"},
        {"label": "API Documentation", "description": "OpenAPI explorer for all endpoints", "route": "/api-docs", "category": "Navigation", "type": "nav"},
        {"label": "Pilot Requests", "description": "Manage factory pilot applications", "route": "/pilot-requests", "category": "Navigation", "type": "nav"},
        {"label": "Cloud Onboarding", "description": "Guided RTSP camera setup wizard", "route": "/cloud-onboarding", "category": "Navigation", "type": "nav"},
        {"label": "Architecture", "description": "System architecture and tech stack overview", "route": "/architecture", "category": "Navigation", "type": "nav"},
    ]
    ql = q.lower()
    return [
        {**item, "id": item["route"]}
        for item in nav_items
        if ql in item["label"].lower() or ql in item["description"].lower()
    ]


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Max results per category"),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """Unified search across sessions, workers, audit trail, and navigation."""
    results = []
    results.extend(_search_navigation(q))
    results.extend(_search_sessions(q, limit))
    results.extend(_search_workers(q, limit))
    results.extend(_search_audit(q, limit))

    # Group by category
    grouped: dict[str, list] = {}
    for r in results:
        grouped.setdefault(r["category"], []).append(r)

    return {
        "query": q,
        "total": len(results),
        "results": results,
        "grouped": grouped,
    }
