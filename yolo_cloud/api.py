"""YOLO Cloud Core - FastAPI endpoints.

Provides REST API for managing cloud cameras, sessions, alerts, and reports.
Compatible with the existing ErgoVigilance dashboard - the frontend can
consume these endpoints the same way it consumes the on-premise backend.
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from yolo_cloud.auth import require_api_key, optional_api_key, get_tenant_id
from yolo_cloud import storage

from yolo_cloud.config import settings
from yolo_cloud.ingestion import get_cloud_service
from yolo_cloud.identity import get_identity_registry, embedding_from_image_bytes
from yolo_cloud.stations import get_station_store
from yolo_cloud import identity_audit
from yolo_cloud.reports import (
    generate_daily_csv,
    generate_daily_summary,
    generate_weekly_csv,
    generate_weekly_summary,
    generate_pdf_report,
)

# Shared feature extraction (works for COCO_17 too). Imported at module scope so
# /inference/detect can always resolve FEATURE_COLUMNS even when its per-person
# feature extraction falls through to the fallback path.
try:
    from backend.core.constants import COCO_17, FEATURE_COLUMNS
    from backend.services.features import (
        extract_features_from_keypoints,
        risk_from_features,
    )
except ImportError:  # pragma: no cover - backend package not on path
    COCO_17 = None
    FEATURE_COLUMNS = []
    extract_features_from_keypoints = None
    risk_from_features = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cloud", tags=["Cloud Core"])


# -- Health ------------------------------------------------------------------

@router.get("/health")
async def health():
    """Health check for the cloud service."""
    service = get_cloud_service()
    cameras = service.get_all_cameras()
    return {
        "status": "healthy",
        "engine": "yolov8-pose",
        "model": settings.YOLO_MODEL,
        "cameras_configured": len(cameras),
        "cameras_active": sum(1 for c in cameras if c.get("is_active")),
        "device": settings.YOLO_DEVICE,
    }


# -- Camera Management -------------------------------------------------------

@router.get("/cameras")
async def list_cameras(tenant: dict = Depends(optional_api_key)):
    """List all configured cloud cameras and their status."""
    service = get_cloud_service()
    cameras = service.get_all_cameras()
    # Also include cameras from database that may not be running
    if storage.pg_enabled():
        db_cameras = storage.get_cameras(tenant.get("tenant_id", "default"))
        db_ids = {c["camera_id"] for c in db_cameras}
        live_ids = {c["camera_id"] for c in cameras}
        # Add DB cameras that aren't currently running
        for dc in db_cameras:
            if dc["camera_id"] not in live_ids:
                cameras.append({
                    "camera_id": dc["camera_id"],
                    "camera_name": dc["camera_name"],
                    "camera_state": "disconnected",
                    "is_active": False,
                })
    return {"cameras": cameras}


@router.post("/cameras")
async def add_camera(body: dict, tenant: dict = Depends(require_api_key)):
    """Add a new RTSP camera and start monitoring.

    Body: {"id": "cam-1", "name": "Assembly Line", "url": "rtsp://..."}
    Requires: X-API-Key header
    """
    cam_id = body.get("id", "").strip()
    name = body.get("name", "IP Camera").strip()
    url = body.get("url", "").strip()
    tenant_id = tenant.get("tenant_id", "default")

    if not cam_id or not url:
        raise HTTPException(400, "Both 'id' and 'url' are required")

    if not url.startswith(("rtsp://", "rtmp://", "http://", "https://")):
        raise HTTPException(400, "URL must start with rtsp://, rtmp://, http://, or https://")

    # Persist camera to database
    if storage.pg_enabled():
        storage.upsert_camera(cam_id, name, url, tenant_id)

    service = get_cloud_service()
    try:
        result = service.add_and_start_camera(cam_id, name, url, tenant_id=tenant_id)
        return result
    except Exception as exc:
        raise HTTPException(500, f"Failed to start camera: {exc}")


@router.delete("/cameras/{camera_id}")
async def remove_camera(camera_id: str, tenant: dict = Depends(require_api_key)):
    """Remove a camera and stop all processing."""
    if storage.pg_enabled():
        storage.set_camera_active(camera_id, False)
    service = get_cloud_service()
    removed = service.remove_camera(camera_id)
    if not removed:
        raise HTTPException(404, f"Camera {camera_id} not found")
    return {"removed": camera_id}


@router.get("/cameras/{camera_id}")
async def get_camera(camera_id: str):
    """Get detailed state of a specific camera."""
    service = get_cloud_service()
    state = service.get_camera_state(camera_id)
    if state is None:
        raise HTTPException(404, f"Camera {camera_id} not found")
    return state


@router.get("/cameras/{camera_id}/snapshot")
async def camera_snapshot(camera_id: str):
    """Get the latest frame from a camera as a JPEG image.

    Returns the raw JPEG bytes with Content-Type: image/jpeg.
    Used by the frontend to show a live thumbnail preview.
    """
    import cv2
    import numpy as np
    from yolo_cloud.rtsp_manager import get_rtsp_manager

    rtsp = get_rtsp_manager()
    frame = rtsp.get_frame(camera_id)
    if frame is None:
        raise HTTPException(404, "No frame available — camera may not be streaming")

    # Encode as JPEG
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    from fastapi.responses import Response
    return Response(content=buf.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.post("/cameras/{camera_id}/start")
async def start_camera(camera_id: str, tenant: dict = Depends(require_api_key)):
    """Start monitoring a camera."""
    service = get_cloud_service()
    cameras = service.get_all_cameras()
    cam = next((c for c in cameras if c["camera_id"] == camera_id), None)
    if cam is None:
        raise HTTPException(404, f"Camera {camera_id} not found")
    if cam.get("is_active"):
        return {"status": "already_running", "camera_id": camera_id}
    result = service.add_and_start_camera(
        camera_id, cam.get("camera_name", ""), cam.get("url", ""),
        tenant_id=tenant.get("tenant_id", "default"),
    )
    return result


@router.post("/cameras/{camera_id}/stop")
async def stop_camera(camera_id: str):
    """Stop monitoring a camera."""
    service = get_cloud_service()
    result = service.stop_camera(camera_id)
    if result is None:
        raise HTTPException(404, f"Camera {camera_id} not found or not active")
    return result


# -- Multi-worker persons & identity -----------------------------------------

@router.get("/cameras/{camera_id}/persons")
async def camera_persons(camera_id: str):
    """Live per-track person snapshots for one camera (multi-worker tile grid)."""
    service = get_cloud_service()
    state = service.get_camera_persons(camera_id)
    if state is None:
        raise HTTPException(404, f"Camera {camera_id} not found or not active")
    return state


@router.get("/persons/{track_id}/timeline")
async def person_timeline(
    track_id: int,
    limit: int = Query(100, ge=1, le=2000),
    camera_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """Sampled per-track risk series for a track_id (merged across sessions)."""
    service = get_cloud_service()
    return service.get_person_timeline(
        track_id, limit=limit, camera_id=camera_id, session_id=session_id,
    )


# -- Station ROIs (workstation polygons) --------------------------------------

@router.get("/cameras/{camera_id}/stations")
async def list_stations(camera_id: str):
    """Workstation polygons drawn for this camera."""
    stations = get_station_store().list_stations(camera_id)
    return {
        "camera_id": camera_id,
        "station_count": len(stations),
        "stations": stations,
    }


@router.put("/cameras/{camera_id}/stations/{station_id}")
async def upsert_station(
    camera_id: str, station_id: str, body: dict,
    tenant: dict = Depends(require_api_key),
):
    """Create or replace one workstation polygon.

    Body: ``{"station_name": "Assembly 1", "polygon": [{"x": 0.1, "y": 0.2}, ...]}``
    with at least 3 points in NORMALIZED frame coordinates (0..1). Points are
    normalized so a boundary drawn at one stream resolution keeps working if the
    stream size changes. A track's bbox centroid inside this polygon is reported
    as this station in ``persons[]``. Overlaps resolve to the smallest polygon.
    """
    try:
        return get_station_store().set_station(
            camera_id,
            station_id,
            station_name=str(body.get("station_name", "") or "").strip(),
            polygon=body.get("polygon"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/cameras/{camera_id}/stations/{station_id}")
async def delete_station(
    camera_id: str, station_id: str, tenant: dict = Depends(require_api_key),
):
    """Remove one workstation polygon (tracks at it become unmapped)."""
    if not get_station_store().delete_station(camera_id, station_id):
        raise HTTPException(404, f"Station {station_id} not found on camera {camera_id}")
    return {"camera_id": camera_id, "station_id": station_id, "deleted": True}


# -- Alert clips (pre-alert evidence) ----------------------------------------

@router.get("/cameras/{camera_id}/clips/{alert_id}")
async def get_alert_clip(camera_id: str, alert_id: str):
    """Download the short clip saved when this alert fired.

    The clip is PRE-ALERT only: it covers the seconds before the alert, from the
    camera's rolling buffer, and ends at the alert. Only HIGH alerts save a clip,
    so a MEDIUM alert has none and returns 404.
    """
    entry = get_cloud_service().get_clip(camera_id, alert_id)
    if entry is None:
        raise HTTPException(
            404,
            f"No clip for alert {alert_id} on camera {camera_id} "
            "(clips are saved for HIGH alerts only)",
        )
    suffix = os.path.splitext(entry["path"])[1].lower()
    media_type = "video/mp4" if suffix == ".mp4" else "video/x-msvideo"
    return FileResponse(
        entry["path"], media_type=media_type, filename=os.path.basename(entry["path"])
    )


@router.post("/cameras/{camera_id}/tracks/{track_id}/identity")
async def bind_track_identity(
    camera_id: str, track_id: int, body: dict,
    tenant: dict = Depends(require_api_key),
):
    """Bind a track to a worker via an explicit badge/QR scan.

    Body: ``{"worker_id": "EMP-4", "method": "badge"|"qr"}``. Rebinding the
    same track to a different worker is allowed and audited as an ID switch.
    """
    worker_id = str(body.get("worker_id", "")).strip()
    method = str(body.get("method", "badge")).strip().lower()
    actor = str(body.get("actor", "")).strip() or None
    if not worker_id:
        raise HTTPException(400, "'worker_id' is required")
    if method not in ("badge", "qr"):
        raise HTTPException(400, "'method' must be 'badge' or 'qr'")
    return get_identity_registry().bind_badge(camera_id, track_id, worker_id, actor=actor)


@router.delete("/cameras/{camera_id}/tracks/{track_id}/identity")
async def unbind_track_identity(
    camera_id: str, track_id: int, tenant: dict = Depends(require_api_key),
):
    """Remove a track's worker binding (identity only — no biometric wipe)."""
    removed = get_identity_registry().unbind(camera_id, track_id)
    if not removed:
        raise HTTPException(404, f"No binding for track {track_id} on {camera_id}")
    return {"camera_id": camera_id, "track_id": track_id, "unbound": True}


@router.post("/cameras/{camera_id}/tracks/{track_id}/face")
async def bind_track_face(
    camera_id: str, track_id: int, file: bytes = File(...),
    tenant: dict = Depends(require_api_key),
):
    """Bind a track by face match — ONLY for workers who granted consent.

    Reuses the on-premise recognizer; matches below the verified band are never
    bound, and the response reports the band instead (never guess a name).
    """
    if file is None:
        raise HTTPException(400, "No image file provided")
    embedding = embedding_from_image_bytes(file)
    if embedding is None:
        raise HTTPException(
            503, "Face recognizer unavailable, or no usable face in the image"
        )
    result = get_identity_registry().bind_face(camera_id, track_id, embedding)
    if result.get("reason") == "consent_withdrawn":
        raise HTTPException(403, "Worker has withdrawn consent for face identity")
    return result


@router.post("/cameras/{camera_id}/tracks/{track_id}/identity/override")
async def override_track_identity(
    camera_id: str, track_id: int, body: dict,
    tenant: dict = Depends(require_api_key),
):
    """Supervisor override: force a track's identity, bypassing badge/face state.

    Body: ``{"worker_id": "EMP-4", "supervisor": "shift-lead@plant", "reason": "..."}``.
    Always audited with the actor and reason.
    """
    worker_id = str(body.get("worker_id", "")).strip()
    supervisor = str(body.get("supervisor", "")).strip()
    reason = str(body.get("reason", "")).strip()
    result = get_identity_registry().override(
        camera_id, track_id, worker_id, supervisor, reason,
    )
    if not result.get("bound"):
        raise HTTPException(400, f"Override not applied: {result.get('reason')}")
    return result


@router.get("/identity/audit")
async def identity_audit_log(
    limit: int = Query(200, ge=1, le=2000),
    camera_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
):
    """Append-only identity audit trail (bind/rebind/override/reentry/unbind/consent)."""
    return {
        "events": identity_audit.read(
            limit=limit, camera_id=camera_id, worker_id=worker_id, event=event,
        ),
        "path": identity_audit.audit_path(),
    }


@router.post("/workers/{worker_id}/withdraw-consent")
async def withdraw_worker_consent(
    worker_id: str, tenant: dict = Depends(require_api_key),
):
    """Withdraw face-identity consent: unbind every live track + wipe biometrics."""
    return get_identity_registry().withdraw(worker_id)


@router.post("/workers/{worker_id}/restore-consent")
async def restore_worker_consent(
    worker_id: str, tenant: dict = Depends(require_api_key),
):
    """Clear the local withdrawal latch after a re-consent is recorded."""
    return get_identity_registry().restore(worker_id)


# -- Dashboard ---------------------------------------------------------------

@router.get("/dashboard")
async def dashboard():
    """Aggregated dashboard across all cloud cameras.

    Returns data compatible with the on-premise /api/dashboard endpoint
    so the same dashboard component can display cloud data.
    """
    service = get_cloud_service()
    return service.get_dashboard()


# -- Sessions ----------------------------------------------------------------

@router.get("/sessions")
async def list_sessions(limit: int = Query(50, ge=1, le=500), tenant: dict = Depends(optional_api_key)):
    """List cloud sessions across all cameras."""
    service = get_cloud_service()
    sessions = service.get_sessions(limit)
    # Also include sessions from database
    if storage.pg_enabled():
        db_sessions = storage.get_sessions(limit, tenant.get("tenant_id", "default"))
        # Merge: DB sessions + live sessions, deduplicate by session_id
        seen = {s.get("session_id") for s in sessions}
        for ds in db_sessions:
            if ds.get("session_id") not in seen:
                sessions.append(ds)
        sessions.sort(key=lambda s: s.get("start_time", ""), reverse=True)
    return {"sessions": sessions[:limit]}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get details of a specific cloud session."""
    service = get_cloud_service()
    sessions = service.get_sessions(limit=1000)
    session = next((s for s in sessions if s.get("session_id") == session_id), None)
    if session is None:
        raise HTTPException(404, f"Session {session_id} not found")
    return session


# -- Alerts ------------------------------------------------------------------

@router.get("/alerts")
async def list_alerts(limit: int = Query(100, ge=1, le=1000), tenant: dict = Depends(optional_api_key)):
    """List recent alerts across all cloud cameras."""
    service = get_cloud_service()
    alerts = service.get_alerts(limit)
    # Also include alerts from database
    if storage.pg_enabled():
        db_alerts = storage.get_alerts(limit, tenant.get("tenant_id", "default"))
        seen = {a.get("alert_id") for a in alerts}
        for da in db_alerts:
            if da.get("alert_id") not in seen:
                alerts.append(da)
        alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    return {"alerts": alerts[:limit]}


# -- Reports -----------------------------------------------------------------

@router.get("/reports/daily")
async def daily_report(
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    camera_id: Optional[str] = Query(None),
):
    """Generate a daily risk report."""
    if date:
        try:
            report_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        report_date = datetime.now()

    service = get_cloud_service()
    sessions = service.get_sessions(limit=1000)

    # Filter by date
    day_start = report_date.replace(hour=0, minute=0, second=0)
    day_end = day_start + timedelta(days=1)
    day_start_ts = day_start.timestamp()
    day_end_ts = day_end.timestamp()

    day_sessions = []
    for s in sessions:
        try:
            st = datetime.fromisoformat(s.get("start_time", ""))
            if day_start_ts <= st.timestamp() < day_end_ts:
                if camera_id is None or s.get("camera_id") == camera_id:
                    day_sessions.append(s)
        except (ValueError, TypeError):
            pass

    total_frames = sum(s.get("frame_count", 0) for s in day_sessions)
    total_alerts = sum(s.get("alert_count", 0) for s in day_sessions)
    risk_totals = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for s in day_sessions:
        for level, count in s.get("risk_summary", {}).items():
            risk_totals[level] = risk_totals.get(level, 0) + count

    return {
        "report_type": "daily",
        "date": report_date.strftime("%Y-%m-%d"),
        "camera_id": camera_id or "all",
        "sessions": len(day_sessions),
        "total_frames": total_frames,
        "total_alerts": total_alerts,
        "risk_distribution": risk_totals,
        "session_details": day_sessions,
    }


@router.get("/reports/weekly")
async def weekly_report(
    week_start: Optional[str] = Query(None, description="YYYY-MM-DD (Monday), defaults to current week"),
    camera_id: Optional[str] = Query(None),
):
    """Generate a weekly risk report."""
    if week_start:
        try:
            ws = datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        today = datetime.now()
        ws = today - timedelta(days=today.weekday())

    service = get_cloud_service()
    sessions = service.get_sessions(limit=1000)
    return generate_weekly_summary(sessions, ws, camera_id)


@router.get("/reports/pdf")
async def pdf_report(
    report_type: str = Query("daily", pattern="^(daily|weekly)$"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    camera_id: Optional[str] = Query(None),
):
    """Generate and download a PDF report."""
    service = get_cloud_service()
    sessions = service.get_sessions(limit=1000)

    if report_type == "daily":
        report_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
        report_data = generate_daily_summary(sessions, report_date, camera_id)
    else:
        ws = datetime.strptime(date, "%Y-%m-%d") if date else (
            datetime.now() - timedelta(days=datetime.now().weekday())
        )
        report_data = generate_weekly_summary(sessions, ws, camera_id)

    pdf_bytes = generate_pdf_report(report_data, report_type)
    if pdf_bytes is None:
        raise HTTPException(503, "PDF generation unavailable. Install reportlab: pip install reportlab")

    filename = "ergovigilance_{}_{}.pdf".format(report_type, datetime.now().strftime('%Y%m%d'))
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/reports/csv")
async def csv_report(
    report_type: str = Query("daily", pattern="^(daily|weekly)$"),
    date: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
):
    """Generate and download a CSV report."""
    service = get_cloud_service()
    sessions = service.get_sessions(limit=1000)

    if report_type == "daily":
        report_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
        csv_content = generate_daily_csv(sessions, report_date, camera_id)
        filename = "ergovigilance_daily_{}.csv".format(report_date.strftime('%Y%m%d'))
    else:
        ws = datetime.strptime(date, "%Y-%m-%d") if date else (
            datetime.now() - timedelta(days=datetime.now().weekday())
        )
        csv_content = generate_weekly_csv(sessions, ws, camera_id)
        filename = "ergovigilance_weekly_{}.csv".format(ws.strftime('%Y%m%d'))

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/reports/export")
async def export_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
):
    """Export session data as CSV for external analysis."""
    service = get_cloud_service()
    sessions = service.get_sessions(limit=1000)

    # Filter
    if start_date:
        sessions = [s for s in sessions if s.get("start_time", "") >= start_date]
    if end_date:
        sessions = [s for s in sessions if s.get("start_time", "") <= end_date]
    if camera_id:
        sessions = [s for s in sessions if s.get("camera_id") == camera_id]

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id", "camera_id", "camera_name", "start_time", "duration_seconds",
        "frame_count", "person_count", "avg_risk_score", "highest_risk",
        "alert_count",
    ])
    for s in sessions:
        writer.writerow([
            s.get("session_id", ""),
            s.get("camera_id", ""),
            s.get("camera_name", ""),
            s.get("start_time", ""),
            s.get("duration_seconds", 0),
            s.get("frame_count", 0),
            s.get("person_count", 0),
            s.get("avg_risk_score", 0),
            s.get("highest_risk", "LOW"),
            s.get("alert_count", 0),
        ])

    output.seek(0)
    filename = "ergovigilance_cloud_{}.csv".format(datetime.now().strftime('%Y%m%d'))
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# -- Model Metrics -------------------------------------------------------


@router.get("/models/metrics")
async def model_metrics():
    """Return YOLO model training metrics, confusion matrices, and per-class stats."""
    models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    metrics = {}

    for model_name in ["yolo_risk", "yolo_task"]:
        metrics_path = os.path.join(models_dir, f"{model_name}_metrics.json")
        try:
            with open(metrics_path) as f:
                metrics[model_name] = json.load(f)
        except FileNotFoundError:
            metrics[model_name] = None

    # Training history (from previous runs)
    history_path = os.path.join(models_dir, "training_history.json")
    try:
        with open(history_path) as f:
            metrics["history"] = json.load(f)
    except FileNotFoundError:
        metrics["history"] = []

    # Feature importance (if available in the model bundle)
    for model_name in ["yolo_risk", "yolo_task"]:
        model_path = os.path.join(models_dir, f"{model_name}_model.pkl")
        try:
            import joblib
            bundle = joblib.load(model_path)
            if isinstance(bundle, dict):
                if "features" in bundle:
                    metrics[f"{model_name}_features"] = bundle["features"]
                if "classes" in bundle:
                    metrics[f"{model_name}_classes"] = bundle["classes"]
                if "confusion_matrix" in bundle:
                    metrics[f"{model_name}_confusion_matrix"] = bundle["confusion_matrix"]
        except Exception:
            pass

    return metrics


@router.get("/models/compare")
async def model_comparison():
    """Compare YOLO cloud core vs MediaPipe on-premise core metrics."""
    # YOLO metrics
    yolo_risk_path = os.path.join(os.path.dirname(__file__), "..", "models", "yolo_risk_metrics.json")
    yolo_task_path = os.path.join(os.path.dirname(__file__), "..", "models", "yolo_task_metrics.json")
    yolo_risk = {}
    yolo_task = {}
    try:
        with open(yolo_risk_path) as f:
            yolo_risk = json.load(f)
    except FileNotFoundError:
        pass
    try:
        with open(yolo_task_path) as f:
            yolo_task = json.load(f)
    except FileNotFoundError:
        pass

    # MediaPipe metrics (from ground truth evaluation)
    gt_path = os.path.join(os.path.dirname(__file__), "..", "results", "ground_truth_evaluation.json")
    mediapipe = {}
    try:
        with open(gt_path) as f:
            mediapipe = json.load(f)
    except FileNotFoundError:
        pass

    return {
        "yolo_cloud": {
            "risk": yolo_risk,
            "task": yolo_task,
            "keypoints": 17,
            "model": "YOLOv8-pose",
            "runtime": "Cloud (RTSP)",
        },
        "mediapipe_on_premise": {
            "accuracy": mediapipe.get("accuracy", None),
            "n_samples": mediapipe.get("n_samples", None),
            "keypoints": 33,
            "model": "MediaPipe Pose",
            "runtime": "On-premise (USB webcam)",
        },
    }


# -- Model Registry (export/import/versioning) ---------------------------

from yolo_cloud.model_registry import ModelRegistry

_model_registry = ModelRegistry()


@router.get("/models/versions")
async def list_model_versions():
    """List all saved model versions."""
    versions = _model_registry.list_versions()
    return {
        "versions": [
            {
                "version_id": v.version_id,
                "timestamp": v.timestamp,
                "description": v.description,
                "files": v.files,
                "has_risk_model": "yolo_risk_model.pkl" in v.files,
                "has_task_model": "yolo_task_model.pkl" in v.files,
            }
            for v in versions
        ],
        "current_metrics": _model_registry.get_current_metrics(),
    }


@router.post("/models/versions/save")
async def save_model_version(description: str = ""):
    """Snapshot current models as a new version."""
    version = _model_registry.save_version(description)
    return {
        "version_id": version.version_id,
        "timestamp": version.timestamp,
        "files": version.files,
    }


@router.post("/models/versions/{version_id}/rollback")
async def rollback_model_version(version_id: str):
    """Restore models from a specific version."""
    success = _model_registry.rollback(version_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    return {"status": "rolled_back", "version_id": version_id}


@router.get("/models/export")
async def export_models():
    """Export current models as a downloadable zip."""
    zip_path = _model_registry.export_models()
    import io
    with open(zip_path, "rb") as f:
        content = f.read()
    os.remove(zip_path)  # clean up temp file
    return StreamingResponse(
        iter([content]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_path.name}"},
    )


@router.post("/models/import")
async def import_models(file: bytes = File(...)):
    """Import models from an uploaded zip file."""
    if file is None:
        raise HTTPException(status_code=400, detail="No file provided")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(file)
        tmp_path = Path(tmp.name)
    try:
        result = _model_registry.import_models(tmp_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        os.unlink(tmp_path)


# -- Live Inference Demo -------------------------------------------------


@router.post("/inference/detect")
async def detect_posture(file: bytes = File(...)):
    """Run YOLO pose detection on an uploaded image frame.
    
    Accepts a JPEG/PNG image, runs YOLOv8-pose + risk classification,
    and returns the annotated image as base64 along with per-person risk data.
    """
    import base64
    import cv2
    import numpy as np

    if file is None:
        raise HTTPException(status_code=400, detail="No image file provided")

    # Decode image
    nparr = np.frombuffer(file, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image format")

    h, w = frame.shape[:2]

    # Load YOLO model
    try:
        from ultralytics import YOLO
        model_path = settings.YOLO_MODEL
        model = YOLO(model_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model load failed: {e}")

    # Run inference
    results = model(frame, conf=settings.YOLO_CONFIDENCE, device=settings.YOLO_DEVICE, verbose=False)

    persons = []
    annotated = frame.copy()

    if results and len(results) > 0 and results[0].keypoints is not None:
        kps_data = results[0].keypoints.data.cpu().numpy()
        boxes = results[0].boxes

        # Load ML models for risk/task classification
        import joblib
        risk_model = None
        task_model = None
        model_features = None
        try:
            risk_bundle = joblib.load(Path(__file__).resolve().parents[1] / "models" / "yolo_risk_model.pkl")
            risk_model = risk_bundle["model"] if isinstance(risk_bundle, dict) else risk_bundle
            task_bundle = joblib.load(Path(__file__).resolve().parents[1] / "models" / "yolo_task_model.pkl")
            task_model = task_bundle["model"] if isinstance(task_bundle, dict) else task_bundle
            # Models were trained on their own feature column list — use it for the
            # feature vector (falling back to FEATURE_COLUMNS if absent).
            if isinstance(risk_bundle, dict) and risk_bundle.get("features"):
                model_features = list(risk_bundle["features"])
            elif isinstance(task_bundle, dict) and task_bundle.get("features"):
                model_features = list(task_bundle["features"])
            else:
                model_features = list(FEATURE_COLUMNS)
        except Exception:
            model_features = list(FEATURE_COLUMNS)

        for pi in range(len(kps_data)):
            person_kps = kps_data[pi]
            conf = float(boxes[pi].conf) if boxes is not None else 0.5
            box = boxes[pi].xyxy.cpu().numpy().astype(int) if boxes is not None else None

            # Extract features
            try:
                kps_arr = np.zeros((17, 4), dtype=float)
                for ki, kp in enumerate(person_kps):
                    if len(kp) >= 3 and kp[2] > 0:
                        kps_arr[ki, 0] = float(kp[0])
                        kps_arr[ki, 1] = float(kp[1])
                        kps_arr[ki, 3] = float(kp[2])
                    else:
                        kps_arr[ki] = float("nan")

                features, unavailable, _ = extract_features_from_keypoints(kps_arr, COCO_17)

                # Classify risk and task
                feat_vec = np.array([features.get(c, float("nan")) for c in model_features], dtype=float).reshape(1, -1)

                risk_level = "MEDIUM"
                risk_score = 50.0
                task = "Unknown"

                if risk_model is not None:
                    risk_level = str(risk_model.predict(feat_vec)[0])
                    try:
                        probs = risk_model.predict_proba(feat_vec)[0]
                        classes = risk_model.classes_ if hasattr(risk_model, "classes_") else ["LOW", "MEDIUM", "HIGH"]
                        weights = {"LOW": 20.0, "MEDIUM": 55.0, "HIGH": 85.0}
                        risk_score = sum(p * weights.get(str(c), 50.0) for p, c in zip(probs, classes))
                    except Exception:
                        risk_score = {"LOW": 20.0, "MEDIUM": 55.0, "HIGH": 85.0}.get(risk_level, 50.0)
                else:
                    risk_level = risk_from_features(features, unavailable)

                if task_model is not None:
                    task = str(task_model.predict(feat_vec)[0])

            except Exception:
                risk_level = "MEDIUM"
                risk_score = 50.0
                task = "Unknown"

            # Draw on annotated image
            color_map = {"LOW": (40, 170, 70), "MEDIUM": (0, 165, 255), "HIGH": (40, 40, 220)}
            color = color_map.get(risk_level, (200, 200, 200))

            if box is not None:
                x1, y1, x2, y2 = box[0]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                label = f"{risk_level} {risk_score:.0f} | {task}"
                cv2.putText(annotated, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Draw keypoints
            for kp in person_kps:
                if len(kp) >= 3 and kp[2] > 0.3:
                    cx, cy = int(kp[0]), int(kp[1])
                    cv2.circle(annotated, (cx, cy), 4, color, -1)

            # Draw skeleton
            skeleton = [(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)]
            for k1, k2 in skeleton:
                if k1 < len(person_kps) and k2 < len(person_kps):
                    p1, p2 = person_kps[k1], person_kps[k2]
                    if len(p1) >= 3 and len(p2) >= 3 and p1[2] > 0.3 and p2[2] > 0.3:
                        cv2.line(annotated, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), color, 2)

            persons.append({
                "person_id": pi,
                "confidence": round(conf, 3),
                "risk_level": risk_level,
                "risk_score": round(risk_score, 1),
                "task": task,
                "keypoints_detected": int(sum(1 for kp in person_kps if len(kp) >= 3 and kp[2] > 0.3)),
                "features": {k: round(float(v), 2) for k, v in features.items() if not (isinstance(v, float) and v != v)} if 'features' in dir() else {},
            })

    # Encode annotated image
    _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
    img_b64 = base64.b64encode(buf).decode('utf-8')

    return {
        "image_width": w,
        "image_height": h,
        "persons": persons,
        "person_count": len(persons),
        "annotated_image": f"data:image/jpeg;base64,{img_b64}",
        "model_used": settings.YOLO_MODEL,
    }


# -- Webhooks -------------------------------------------------------------


@router.get("/webhooks")
async def list_webhooks(tenant: dict = Depends(require_api_key)):
    """List all configured webhooks for the tenant."""
    from yolo_cloud.webhooks import get_webhooks
    return {"webhooks": get_webhooks(tenant.get("tenant_id", "default"))}


@router.post("/webhooks")
async def create_webhook(body: dict, tenant: dict = Depends(require_api_key)):
    """Create a new webhook.

    Body: {"url": "https://...", "name": "Slack Alert", "events": ["alert.fired"]}
    """
    from yolo_cloud.webhooks import store_webhook
    url = body.get("url", "").strip()
    name = body.get("name", "webhook").strip()
    events = body.get("events", ["alert.fired"])
    secret = body.get("secret", "")
    if not url:
        raise HTTPException(400, "Webhook URL is required")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")
    success = store_webhook(tenant.get("tenant_id", "default"), url, events, secret, name)
    if not success:
        raise HTTPException(500, "Failed to store webhook")
    return {"status": "created", "url": url, "name": name}


@router.post("/webhooks/test")
async def test_webhook_endpoint(body: dict):
    """Test a webhook URL by sending a test event.

    Body: {"url": "https://..."}
    """
    from yolo_cloud.webhooks import test_webhook
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(400, "Webhook URL is required")
    return test_webhook(url)


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook_endpoint(webhook_id: str, tenant: dict = Depends(require_api_key)):
    """Delete a webhook."""
    from yolo_cloud.webhooks import delete_webhook
    success = delete_webhook(webhook_id, tenant.get("tenant_id", "default"))
    if not success:
        raise HTTPException(404, "Webhook not found")
    return {"removed": webhook_id}


# -- Data Retention & Stats -----------------------------------------------


@router.get("/storage/stats")
async def storage_stats(tenant: dict = Depends(require_api_key)):
    """Get storage statistics (session count, alert count, camera count)."""
    return storage.get_storage_stats(tenant.get("tenant_id", "default"))


@router.post("/retention/cleanup")
async def retention_cleanup(
    session_days: int = Query(30, ge=1, le=365),
    alert_days: int = Query(90, ge=1, le=365),
    tenant: dict = Depends(require_api_key),
):
    """Clean up old sessions and alerts beyond retention period."""
    if not storage.pg_enabled():
        return {"message": "PostgreSQL not configured — retention cleanup skipped", "sessions_deleted": 0, "alerts_deleted": 0}
    sessions_deleted = storage.cleanup_old_sessions(session_days, tenant.get("tenant_id", "default"))
    alerts_deleted = storage.cleanup_old_alerts(alert_days, tenant.get("tenant_id", "default"))
    return {
        "sessions_deleted": sessions_deleted,
        "alerts_deleted": alerts_deleted,
        "session_retention_days": session_days,
        "alert_retention_days": alert_days,
    }


# -- API Key Management ---------------------------------------------------


@router.post("/api-keys")
async def create_api_key_endpoint(body: dict, tenant: dict = Depends(require_api_key)):
    """Create a new API key for a tenant.

    Body: {"name": "My Factory", "tenant_id": "factory-1"}
    Returns the generated key (shown once, store securely).
    """
    import secrets
    name = body.get("name", "unnamed")
    tenant_id = body.get("tenant_id", tenant.get("tenant_id", "default"))
    api_key = f"ev_{secrets.token_urlsafe(32)}"

    if storage.pg_enabled():
        success = storage.create_api_key(api_key, tenant_id, name)
        if not success:
            raise HTTPException(500, "Failed to create API key")
    else:
        logger.warning("API key creation requires PostgreSQL (DATABASE_URL not set)")

    return {
        "api_key": api_key,
        "tenant_id": tenant_id,
        "name": name,
        "message": "Store this key securely — it will not be shown again",
    }


@router.get("/api-keys")
async def list_api_keys(tenant: dict = Depends(require_api_key)):
    """List API keys for the current tenant."""
    conn = storage.get_connection()
    if conn is None:
        return {"keys": [], "message": "PostgreSQL not configured"}
    try:
        rows = conn.execute(
            "SELECT key_id, name, tenant_id, is_active, created_at, last_used FROM cloud_api_keys WHERE tenant_id = %s ORDER BY created_at DESC",
            (tenant.get("tenant_id", "default"),),
        ).fetchall()
        return {
            "keys": [
                {
                    "key_id": r[0],
                    "name": r[1],
                    "tenant_id": r[2],
                    "is_active": r[3],
                    "created_at": r[4].isoformat() if r[4] else None,
                    "last_used": r[5].isoformat() if r[5] else None,
                }
                for r in rows
            ]
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to list keys: {exc}")


@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, tenant: dict = Depends(require_api_key)):
    """Rotate an API key — generates a new key and deactivates the old one."""
    import secrets
    conn = storage.get_connection()
    if conn is None:
        raise HTTPException(503, "PostgreSQL not configured")
    try:
        # Verify the key belongs to this tenant
        row = conn.execute(
            "SELECT key_id, tenant_id FROM cloud_api_keys WHERE key_id = %s AND tenant_id = %s",
            (key_id, tenant.get("tenant_id", "default")),
        ).fetchone()
        if not row:
            raise HTTPException(404, "API key not found")

        # Generate new key
        new_key = f"ev_{secrets.token_urlsafe(32)}"
        new_key_hash = hashlib.sha256(new_key.encode()).hexdigest()

        # Deactivate old key
        conn.execute(
            "UPDATE cloud_api_keys SET is_active = FALSE WHERE key_id = %s",
            (key_id,),
        )

        # Create new key
        conn.execute(
            "INSERT INTO cloud_api_keys (key_id, key_hash, name, tenant_id, is_active, created_at) VALUES (%s, %s, %s, %s, TRUE, NOW())",
            (key_id + "-rotated", new_key_hash, f"Rotated {datetime.now().strftime('%Y-%m-%d')}", tenant.get("tenant_id", "default")),
        )
        conn.commit()

        logger.info("API key rotated for tenant %s", tenant.get("tenant_id"))
        return {
            "new_key": new_key,
            "message": "Store this key securely — it will not be shown again",
            "old_key_deactivated": True,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to rotate key: {exc}")


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, tenant: dict = Depends(require_api_key)):
    """Revoke (deactivate) an API key."""
    conn = storage.get_connection()
    if conn is None:
        raise HTTPException(503, "PostgreSQL not configured")
    try:
        result = conn.execute(
            "UPDATE cloud_api_keys SET is_active = FALSE WHERE key_id = %s AND tenant_id = %s",
            (key_id, tenant.get("tenant_id", "default")),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(404, "API key not found")
        return {"status": "revoked", "key_id": key_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to revoke key: {exc}")


# -- WebSocket for live camera data streaming -----------------------------

_ws_clients: set = set()
# Event loop serving the WebSocket, captured when a client connects so the ingest
# thread can schedule alert pushes onto it via run_coroutine_threadsafe.
_ws_loop: Optional[asyncio.AbstractEventLoop] = None


def _remember_ws_loop() -> None:
    """Capture the loop serving ``/ws`` (no-op when there is no running loop)."""
    global _ws_loop
    try:
        _ws_loop = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover
        _ws_loop = None


def push_alert_event(alert: dict) -> int:
    """Push a newly created alert to connected clients immediately.

    Called from the ingest thread, so the send is scheduled onto the WebSocket
    loop rather than awaited here. Returns how many clients were queued.

    This is an ACCELERATOR, not the delivery guarantee: ``/ws`` still sends its
    5 Hz snapshot carrying ``recent_alerts``, so an alert reaches a client within
    200 ms even if this push is missed. Clients should de-duplicate on
    ``alert_id`` because one alert can arrive by both paths.
    """
    loop = _ws_loop
    if loop is None or not _ws_clients:
        return 0
    payload = {"type": "alert", "alert": alert}
    queued = 0
    for client in list(_ws_clients):
        try:
            asyncio.run_coroutine_threadsafe(client.send_json(payload), loop)
            queued += 1
        except Exception as exc:  # noqa: BLE001 - a dead client must not stall ingest
            logger.debug("Alert event push failed: %s", exc)
    return queued


@router.websocket("/ws")
async def cloud_ws(websocket: WebSocket):
    """WebSocket endpoint for live camera data. Two delivery paths:

    * ``{"type": "update"}`` at 5 Hz (every 200 ms): per-camera status including
      ``persons[]`` (one entry per ``track_id``, so one camera_id can drive 5-10
      worker tiles), recent alerts carrying ``track_id``/``worker_id``, and
      overall dashboard stats. This is the GUARANTEED path — an alert always
      appears here within 200 ms of being created.
    * ``{"type": "alert"}`` immediately on creation, as an accelerator for
      toasts. Best-effort, and the SAME alert may also arrive in the next
      ``update`` snapshot, so clients must de-duplicate on ``alert_id``.
    """
    await websocket.accept()
    _remember_ws_loop()
    _ws_clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(_ws_clients))

    try:
        service = get_cloud_service()

        # Send initial state
        cameras = service.get_all_cameras()
        await websocket.send_json({
            "type": "init",
            "cameras": cameras,
            "health": {
                "engine": "yolov8-pose",
                "model": settings.YOLO_MODEL,
                "device": settings.YOLO_DEVICE,
            },
        })

        # Push updates at 5 Hz (200 ms) — enough for per-tile progress bars
        while True:
            # Check for incoming messages (ping/pong keep-alive)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
                data = json.loads(msg)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            except Exception:
                break

            # Push camera status update
            try:
                cameras = service.get_all_cameras()
                alerts = service.get_alerts(limit=10)
                dashboard = service.get_dashboard()
                await websocket.send_json({
                    "type": "update",
                    "cameras": cameras,
                    "persons": dashboard.get("persons", []),
                    "recent_alerts": alerts[:5],
                    "dashboard": {
                        "active_cameras": dashboard.get("active_cameras", 0),
                        "total_workers": dashboard.get("total_workers", 0),
                        "risk_distribution": dashboard.get("risk_distribution", {}),
                        "id_switch_count": dashboard.get("id_switch_count", 0),
                        "total_sessions": dashboard.get("total_sessions", 0),
                        "active_alerts": dashboard.get("active_alerts", 0),
                        "avg_risk_score": dashboard.get("avg_risk_score", 0),
                    },
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception as e:
                logger.debug("WS push error: %s", e)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        _ws_clients.discard(websocket)


# -- Application factory ------------------------------------------------

def create_app() -> "FastAPI":
    """Create and configure the FastAPI application.

    Used by uvicorn with --factory flag:
        uvicorn yolo_cloud.api:create_app --factory
    """
    from fastapi import FastAPI

    _app = FastAPI(
        title="ErgoVigilance Cloud Core",
        description="""YOLO-powered ergonomic risk monitoring for RTSP camera streams.

## Authentication

All endpoints require an API key via one of:
- Header: `X-API-Key: ev_your_key_here`
- Bearer: `Authorization: Bearer ev_your_key_here`

## Rate Limits
- 100 requests per minute per API key
- 1000 requests per minute per tenant

## Webhooks

Configure webhook URLs to receive real-time alert notifications.
All payloads are signed with HMAC-SHA256 for verification.""",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Customize OpenAPI schema with security schemes
    def custom_openapi():
        if _app.openapi_schema:
            return _app.openapi_schema
        from fastapi.openapi.utils import get_openapi
        schema = get_openapi(
            title=_app.title,
            version=_app.version,
            description=_app.description,
            routes=_app.routes,
        )
        schema["components"] = schema.get("components", {})
        schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for tenant authentication",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Bearer token (API key)",
            },
        }
        schema["security"] = [{"ApiKeyAuth": []}, {"BearerAuth": []}]
        _app.openapi_schema = schema
        return schema

    _app.openapi = custom_openapi

    # ── Single-worker guard ─────────────────────────────────────────────
    # Camera ingestion is in-process singleton state (one FFmpeg per camera, one
    # set of processors, one identity registry). A second uvicorn worker would
    # open a second stream per camera and double-process every frame, so it is
    # refused unless an operator explicitly opts out.
    web_concurrency = int(os.getenv("WEB_CONCURRENCY", "1") or "1")
    if web_concurrency > 1:
        _msg = (
            f"WEB_CONCURRENCY={web_concurrency} is not supported: cloud ingestion is "
            "in-process singleton state, so multiple workers duplicate every stream. "
            "Run a single worker and scale vertically "
            f"(EXPECTED_CAMERAS={settings.EXPECTED_CAMERAS}). "
            "Set STRICT_SINGLE_WORKER=false to override (unsupported)."
        )
        if settings.STRICT_SINGLE_WORKER:
            raise RuntimeError(_msg)
        logger.error(_msg)

    # ── TLS / reverse-proxy policy ──────────────────────────────────────
    @_app.middleware("http")
    async def _tls_and_proxy_guard(request: Request, call_next):
        if settings.REQUIRE_TLS:
            forwarded_proto = request.headers.get("x-forwarded-proto", "")
            is_https = request.url.scheme == "https" or (
                settings.TRUST_PROXY
                and forwarded_proto.split(",")[0].strip().lower() == "https"
            )
            if not is_https:
                return JSONResponse(
                    status_code=403,
                    content={"error": "TLS required (REQUIRE_TLS=true)"},
                )
        return await call_next(request)

    # Rate limiting (must be added before routers)
    try:
        from yolo_cloud.rate_limit import CloudRateLimitMiddleware
        _app.add_middleware(CloudRateLimitMiddleware)
    except ImportError:
        logger.warning("Rate limiter not available, skipping")

    # Tenant isolation (must be added before routers)
    try:
        from yolo_cloud.tenant_middleware import TenantIsolationMiddleware, TenantContextMiddleware
        _app.add_middleware(TenantContextMiddleware)
        _app.add_middleware(TenantIsolationMiddleware)
    except ImportError:
        logger.warning("Tenant middleware not available, skipping")

    _app.include_router(router, prefix="/api")

    # Initialize PostgreSQL storage if configured
    if storage.pg_enabled():
        try:
            storage.init_schema()
            logger.info("Cloud PostgreSQL storage initialized")
        except Exception as exc:
            logger.warning("Cloud DB init failed (file mode): %s", exc)

    @_app.get("/healthz")
    async def root_health():
        db_status = "connected" if storage.pg_enabled() and storage.get_connection() else "file-mode"
        from yolo_cloud.rate_limit import limits_snapshot
        return {
            "status": "ok",
            "service": "cloud-core",
            "storage": db_status,
            "expected_cameras": settings.EXPECTED_CAMERAS,
            "web_concurrency": web_concurrency,
            "limits": limits_snapshot(),
        }

    logger.info(
        "Cloud Core started: model=%s device=%s port=%d",
        settings.YOLO_MODEL, settings.YOLO_DEVICE, settings.PORT,
    )
    return _app