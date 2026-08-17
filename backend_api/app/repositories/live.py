"""Live repository — reads from LiveState instead of mock data.

Replaces MockRepository when the CV pipeline is active.
Maintains the same DashboardResponse schema so React interfaces stay unchanged.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.repositories.base import DashboardRepository
from app.schemas.api import (
    DashboardResponse,
    SessionRecord,
    CameraInfo,
    WorkstationInfo,
    DeploymentMetrics,
    ManagerSummary,
    WorkerSummary,
    Alert,
    ContextSnapshotResponse,
    GuidanceSnapshot,
    GuidanceFeedbackItem,
    AlertsResponse,
    AlertResponse,
    AlertSummary,
    RecommendationsBundleResponse,
    RecommendationBundleData,
    RecommendationResponse,
    HistoryResponse,
    HistoryPoint,
    HistoryStatistics,
    SessionDetailResponse,
    SessionAlertEntry,
    DepartmentHeatmapEntry,
    RiskLevel,
)
from app.services.live_monitor import get_live_service

# ── Module-level camera detection cache ─────────────────────────────
# LiveRepository is instantiated per request (FastAPI Depends()), so
# instance/class attrs are lost between requests.  These module-level
# vars persist for the lifetime of the Python process.
_camera_cache: list["CameraInfo"] = []
_camera_cache_time: float = 0
_camera_cache_ttl = 300  # seconds (5 min — cameras rarely change)


def _ensure_camera_cache(force: bool = False) -> None:
    """Probe physical cameras and populate the module-level cache if stale.

    Probing opens camera devices, which takes several seconds on Windows, so
    it is cached (5 min TTL) and can be prewarmed at startup via
    ``warm_camera_cache()``.
    """
    global _camera_cache, _camera_cache_time  # noqa: PLW0603
    from backend.services.camera_manager import detect_cameras

    now = time.time()
    if not force and _camera_cache and (now - _camera_cache_time) <= _camera_cache_ttl:
        return

    try:
        detected = detect_cameras(fast=True, max_index=5)
    except Exception as exc:
        # Back off retries for the full TTL on failure so a broken probe can't
        # be hammered per request; a camera plugged in afterwards is picked up
        # at the next TTL expiry. (The previous code surfaced probe errors as
        # 500s, so this is strictly friendlier.)
        logger.warning("Camera probe failed (retrying in %ds): %s", _camera_cache_ttl, exc)
        _camera_cache_time = now
        return

    _camera_cache = [
        CameraInfo(
            id=f"cam-{cam.index}",
            name=cam.name or f"Camera {cam.index}",
            worker="",
            fps=0,
            risk="low",
            recording=False,
            uptime="",
            status="available",
        )
        for cam in detected
    ]
    _camera_cache_time = now
    logger.info("Camera probe complete — %d camera(s) detected", len(_camera_cache))


def warm_camera_cache() -> None:
    """Pre-probe cameras so the first /api/cameras and /api/deployment calls
    don't block on a multi-second device probe (call from a background thread)."""
    try:
        _ensure_camera_cache(force=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Camera cache prewarm failed (will probe lazily): %s", exc)

# ── Module-level manager summary cache ──────────────────────────────
_manager_cache: dict | None = None
_manager_cache_time: float = 0
_MANAGER_CACHE_TTL = 30  # seconds
from app.core.auth import can_view_all_sessions

logger = logging.getLogger(__name__)

_VALID_SESSION_STATUSES = frozenset({"active", "completed", "interrupted"})


def _session_status_from_data(data: dict) -> str:
    raw = data.get("status", "completed")
    return raw if raw in _VALID_SESSION_STATUSES else "completed"


class LiveRepository(DashboardRepository):
    """Repository that reads directly from the live pipeline state."""

    def _build_dashboard(self) -> DashboardResponse:
        service = get_live_service()
        state = service.get_state_snapshot()

        session_id = state.session_id or "SESH-LIVE-001"
        start_time = ""
        duration = 0
        if state.session_start:
            start_time = __import__("datetime").datetime.fromtimestamp(
                state.session_start
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            duration = int(time.time() - state.session_start)

        features_list = []
        feature_configs = [
            ("neck_flexion", "Neck Flexion", "°", 0, 50),
            ("trunk_flexion", "Trunk Flexion", "°", 0, 60),
            ("left_shoulder_elev", "Left Shoulder Elevation", "°", 0, 90),
            ("right_shoulder_elev", "Right Shoulder Elevation", "°", 0, 90),
            ("shoulder_symmetry", "Shoulder Symmetry", "%", 0, 30),
            ("alignment_deviation", "Alignment Deviation", "%", 0, 20),
            ("knee_angle", "Knee Angle", "°", 80, 180),
            # Phase-A additions (2026-08): head / wrist / stance ergonomics
            ("forward_head_posture", "Forward Head Posture", "%", 0, 30),
            ("head_tilt_angle", "Head Tilt", "°", 0, 30),
            ("wrist_deviation_angle", "Wrist Deviation", "°", 0, 25),
            ("stance_stability", "Stance Stability", "", 0, 1),
            ("weight_shift_offset", "Weight Shift", "%", 0, 20),
        ]

        from backend.services.features import risk_breakdown
        breakdown = risk_breakdown(state.features)

        status_map = {"LOW": "good", "MEDIUM": "moderate", "HIGH": "high"}

        import math
        for key, name, unit, mn, mx in feature_configs:
            raw_val = state.features.get(key, 0.0)
            val = 0.0 if (isinstance(raw_val, float) and math.isnan(raw_val)) else raw_val
            br = breakdown.get(key)
            frisk = br.level if br else "LOW"
            features_list.append({
                "id": key,
                "name": name,
                "value": round(val, 1),
                "unit": unit,
                "min": mn,
                "max": mx,
                "status": status_map.get(frisk, "unavailable"),
            })

        issues_list = []
        for i, issue in enumerate(state.issues):
            sev = issue.get("severity", "LOW").lower()
            if sev == "low":
                mapped_sev = "low"
            elif sev == "medium":
                mapped_sev = "moderate"
            else:
                mapped_sev = "high"
            issues_list.append({
                "id": f"ISSUE-{i:03d}",
                "severity": mapped_sev,
                "name": issue.get("issue", "Unknown"),
                "timestamp": state.timestamp,
                "detail": f"{issue.get('issue', '')} — Value: {issue.get('value', 0):.1f}, Threshold: {issue.get('threshold', 0)}",
            })

        analytics = service.analytics.get_summary() if hasattr(service.analytics, 'get_summary') else {}

        return DashboardResponse(
            session={
                "id": session_id,
                "workerName": "Live Session",
                "workerId": "CAM-001",
                "startTime": start_time,
                "currentTime": state.timestamp,
                "duration": duration,
                "framesAnalyzed": analytics.get("total_frames", 0),
                "cameraStatus": state.camera_status,
                "cameraReconnecting": bool(getattr(state, "camera_reconnecting", False)),
            },
            liveStatus={
                "riskLevel": {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high"}.get(state.risk_level, "low"),
                "riskScore": state.risk_score,
                "confidence": state.confidence,
                "currentTask": state.task_name,
                "taskConfidence": getattr(state, "task_confidence", 0.0),
                "taskDurationSeconds": state.task_duration_seconds,
                "workerStatus": "active" if state.person_detected else "idle",
            },
            ergonomicFeatures=features_list,
            issues=issues_list,
            recommendations={
                "worker": state.worker_recommendation,
                "supervisor": state.supervisor_recommendation,
            },
            sessionAnalytics={
                "sessionDuration": f"{duration // 60}m {duration % 60}s",
                "framesAnalyzed": analytics.get("total_frames", 0),
                "highestRisk": "LOW",
                "mostFrequentIssue": analytics.get("most_frequent_issue", "None") or "None",
                "averageNeck": round(analytics.get("avg_neck_flexion", 0), 1),
                "averageTrunk": round(analytics.get("avg_trunk_flexion", 0), 1),
                "averageKnee": round(analytics.get("avg_knee_angle", 0), 1),
            },
            unavailableFeatures=list(state.unavailable_features),
            riskHistory=[],
            trendAnalysis={
                "trend": "stable",
                "averageRisk": 0,
                "sessionsAnalyzed": 0,
                "improving": 0,
                "stable": 1,
                "deteriorating": 0,
            },
        )

    async def get_dashboard(self) -> DashboardResponse:
        return self._build_dashboard()

    async def get_latest_session(self) -> DashboardResponse:
        return self._build_dashboard()

    async def get_sessions(self, current_user=None) -> List[SessionRecord]:
        import os
        from datetime import datetime
        from app.services.session_cache import get_all_sessions

        records = []

        service = get_live_service()
        state = service.get_state_snapshot()
        if state.session_active and state.session_id:
            active_owner_id = getattr(service, "current_created_by_user_id", None)
            if current_user is None or can_view_all_sessions(current_user) or active_owner_id == current_user.id:
                worker_id = getattr(service, "current_worker_id", None)
                camera_id = getattr(service, "current_camera_id", None)
            else:
                worker_id = None
                camera_id = None
        else:
            worker_id = None
            camera_id = None

        if state.session_active and state.session_id and (
            current_user is None
            or can_view_all_sessions(current_user)
            or getattr(service, "current_created_by_user_id", None) == current_user.id
        ):
            duration_secs = int(time.time() - state.session_start) if state.session_start else 0
            mins = duration_secs // 60
            secs = duration_secs % 60
            duration_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            date_str = (
                datetime.fromtimestamp(state.session_start).strftime("%Y-%m-%dT%H:%M:%SZ")
                if state.session_start
                else state.timestamp
            )
            records.append(SessionRecord(
                id=state.session_id,
                date=date_str,
                duration=duration_str,
                highestRisk=state.risk_level or "LOW",
                highest_risk_level=state.risk_level or "LOW",
                task=state.task_name or "Monitoring Session",
                status="active",
                worker_id=worker_id,
                created_by_user_id=getattr(service, "current_created_by_user_id", None),
                camera_id=camera_id,
            ))

        cached = get_all_sessions()
        if not cached:
            return records

        for data in cached:
            created_by_user_id = data.get("created_by_user_id")
            if current_user is not None and not can_view_all_sessions(current_user):
                if created_by_user_id != current_user.id:
                    continue

            ts = data.get("session_timestamp", "") or ""
            duration_secs = data.get("session_duration_seconds", 0)
            mins = int(duration_secs // 60)
            secs = int(duration_secs % 60)
            duration_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

            highest = data.get("highest_risk_level", "LOW")
            risk_map = {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high"}
            highest_risk = risk_map.get(highest, "low")
            # Dominant level for list/calendar display (falls back to peak).
            dominant = data.get("risk_level") or highest
            if dominant not in ("LOW", "MEDIUM", "HIGH"):
                dominant = highest

            date_str = ""
            if ts:
                try:
                    # Strip millisecond suffix (_NNN) if present
                    clean_ts = ts.rsplit("_", 1)[0] if ts.count("_") > 1 and ts.rsplit("_", 1)[1].isdigit() else ts
                    dt = datetime.strptime(clean_ts, "%Y%m%d_%H%M%S")
                    date_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except (ValueError, TypeError) as exc:
                    logger.warning("Failed to parse session timestamp %s: %s", ts, exc)
                    date_str = ts

            records.append(SessionRecord(
                id=data.get("session_id") or (f"SESH-{ts}" if ts else f"SESH-{int(time.time())}"),
                date=date_str,
                duration=duration_str,
                highestRisk=data.get("most_frequent_issue") or highest_risk,
                highest_risk_level=highest,
                risk_level=dominant,
                risk_percentages=data.get("risk_percentages") or {},
                # Real per-session task classification (persisted at save time
                # since task recognition is live-only). Older sessions predate
                # the field — show them honestly instead of a fake value.
                task=data.get("task_name") or "Not classified",
                status="completed",
                worker_id=data.get("worker_id"),
                created_by_user_id=created_by_user_id,
                camera_id=data.get("camera_id"),
            ))

        records.sort(key=lambda r: r.date, reverse=True)
        return records

    async def get_session_detail(self, session_id: str, current_user=None) -> Optional[SessionDetailResponse]:
        import os
        import json
        from datetime import datetime
        from fastapi import HTTPException, status

        # Same layout-robust resolution as app/services/session_cache.py: env
        # override, then local (3 levels up) vs container (/app/app, 2 levels).
        env_sessions = os.environ.get("SESSIONS_DIR")
        if env_sessions:
            sessions_dir = env_sessions
        else:
            root = Path(__file__).resolve().parents[3]
            if not (root / "outputs").is_dir() and (Path(__file__).resolve().parents[2] / "app").is_dir():
                root = Path(__file__).resolve().parents[2]
            sessions_dir = os.path.join(str(root), "outputs", "sessions")

        ts_part = session_id.replace("SESH-", "", 1)
        candidate_paths = [os.path.join(sessions_dir, f"session_{ts_part}.json")]
        filepath = None
        for candidate in candidate_paths:
            if os.path.exists(candidate):
                filepath = candidate
                break
        if filepath is None:
            # Fallback — search by session_id from cache instead of full filesystem scan
            import glob as glob_module
            from app.services.session_cache import get_all_sessions
            for cached in get_all_sessions():
                if cached.get("session_id") == session_id:
                    ts_part_cached = cached.get("session_timestamp", session_id).replace("session_", "")
                    pattern = os.path.join(sessions_dir, f"session_{ts_part_cached}*.json")
                    matches = glob_module.glob(pattern)
                    if matches:
                        filepath = matches[0]
                    break

        if filepath is None:
            # Tier 1: fall back to the Postgres telemetry store when the JSON
            # file is missing (e.g. a session mirrored from another deployment).
            from app.core.postgres import pg_enabled, fetch_sessions
            if pg_enabled():
                for cached in fetch_sessions():
                    if cached.get("session_id") == session_id:
                        data = cached
                        break
                else:
                    return None
            else:
                return None
        else:
            with open(filepath, "r") as f:
                data = json.load(f)

        created_by_user_id = data.get("created_by_user_id")
        if current_user is not None and not can_view_all_sessions(current_user):
            if created_by_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this session")

        alerts_raw = data.get("alerts", [])
        alerts = []
        for a in alerts_raw:
            if not isinstance(a, dict):
                logger.warning("Skipping non-dict alert entry: %r", a)
                continue
            alerts.append(
                SessionAlertEntry(
                    id=a.get("id", ""),
                    session_id=a.get("session_id", ""),
                    frame_number=a.get("frame_number", 0),
                    created_at=a.get("created_at", ""),
                    severity=a.get("severity", "LOW"),
                    state=a.get("state", "ACTIVE"),
                    title=a.get("title", ""),
                    message=a.get("message", ""),
                    trigger_rule=a.get("trigger_rule", ""),
                    confidence=a.get("confidence", 0.0),
                    requires_ack=a.get("requires_ack", False),
                    expires_at=a.get("expires_at", ""),
                )
            )

        risk_pct = data.get("risk_percentages") or {}

        return SessionDetailResponse(
            id=session_id,
            status=_session_status_from_data(data),
            session_timestamp=data.get("session_timestamp", ts_part),
            session_duration_seconds=data.get("session_duration_seconds", 0.0),
            total_frames=data.get("total_frames", 0),
            risk_percentages=risk_pct,
            most_frequent_issue=data.get("most_frequent_issue"),
            most_frequent_issue_count=data.get("most_frequent_issue_count", 0),
            highest_risk_level=data.get("highest_risk_level", "LOW"),
            highest_risk_timestamp=data.get("highest_risk_timestamp"),
            avg_neck_flexion=data.get("avg_neck_flexion", 0.0),
            avg_trunk_flexion=data.get("avg_trunk_flexion", 0.0),
            avg_shoulder_symmetry=data.get("avg_shoulder_symmetry", 0.0),
            avg_knee_angle=data.get("avg_knee_angle", 0.0),
            alerts=alerts,
            worker_id=data.get("worker_id"),
            created_by_user_id=created_by_user_id,
            camera_id=data.get("camera_id"),
            video_path=data.get("video_path"),            video_recording_status=data.get("video_recording_status"),
            video_recording_error=data.get("video_recording_error"),
            video_frame_count=data.get("video_frame_count"),
            video_codec=data.get("video_codec"),
        )

    async def get_cameras(self) -> List[CameraInfo]:
        """Enumerate all physically available cameras via camera_manager.

        Caches the detection result at module level for 60 seconds to avoid
        repeatedly opening/closing physical camera devices on every request.
        Note: LiveRepository is instantiated per request by FastAPI Depends(),
        so instance-level cache would be lost — this uses module-level vars.

        - "streaming" if this camera is the one driving the active live session
        - "available" for all other detected cameras (idle, not monitoring)
        Returns an empty list when no cameras are detected at all.
        """
        logger.info("[get_cameras] repo_instance=%s", id(self))

        service = get_live_service()
        is_running = service.is_running()

        # Module-level cache (survives per-request instances). Re-probe only
        # when the cache is expired or empty; prewarmed at startup by
        # warm_camera_cache() so the first page load is fast.
        _ensure_camera_cache()

        if not _camera_cache:
            return []

        risk_map = {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high"}
        active_index = getattr(service, "current_camera_index", None)
        active_source = getattr(service, "current_camera_source", None)

        result: list[CameraInfo] = []
        for base in _camera_cache:
            idx = int(base.id.replace("cam-", "")) if base.id.startswith("cam-") else -1
            is_active = (
                is_running
                and active_source is not None
                and idx == int(active_source)
            )
            if is_active:
                state = service.get_state_snapshot()
                worker_id = getattr(service, "current_worker_id", "unknown")
                camera_id = getattr(service, "current_camera_id", None) or base.id
                result.append(CameraInfo(
                    id=camera_id,
                    name=base.name,
                    worker=worker_id,
                    fps=int(state.fps or 0),
                    risk=risk_map.get(state.risk_level, "low"),
                    recording=True,
                    uptime=state.timestamp or "",
                    status="streaming",
                ))
            else:
                result.append(base)

        # Append configured IP/RTSP cameras (from CAMERA_SOURCES) so they appear
        # in Settings + Multi-Camera alongside physical USB cameras.
        from app.core.config import settings
        for cam in settings.CAMERA_SOURCES:
            is_active = is_running and active_source == cam["url"]
            if is_active:
                state = service.get_state_snapshot()
                result.append(CameraInfo(
                    id=cam["id"],
                    name=cam["name"],
                    worker=getattr(service, "current_worker_id", "unknown"),
                    fps=int(state.fps or 0),
                    risk=risk_map.get(state.risk_level, "low"),
                    recording=True,
                    uptime=state.timestamp or "",
                    status="streaming",
                ))
            else:
                result.append(CameraInfo(
                    id=cam["id"],
                    name=cam["name"],
                    worker="",
                    fps=0,
                    risk="low",
                    recording=False,
                    uptime="",
                    status="available",
                ))
        return result

    async def get_workstations(self) -> List[WorkstationInfo]:
        return []

    async def get_deployment(self) -> DeploymentMetrics:
        import os
        import time
        from app.core.config import settings
        from app.core.database import list_workers, DB_PATH
        from backend.services.camera_manager import detect_cameras

        # Backend info
        from app.main import BACKEND_START_TIME
        backend_uptime = time.time() - BACKEND_START_TIME

        # Database info — init_local_database() already runs at app startup
        db_size = 0
        db_status = "ok"
        try:
            if os.path.exists(DB_PATH):
                db_size = os.path.getsize(DB_PATH)
        except Exception as exc:
            logger.error("Failed to check database health: %s", exc)
            db_status = "error"

        # Worker count — cached alongside camera cache to avoid SQLite query per poll
        workers: list = []
        try:
            workers = list_workers()
        except Exception as exc:
            logger.error("Failed to list workers: %s", exc)

        # Camera count — reuse the same cache as get_cameras() to avoid
        # probing physical devices on every deployment poll (frontend polls every 30s).
        _ensure_camera_cache()
        camera_count = len(_camera_cache) if _camera_cache else 0

        # Session info
        try:
            service = get_live_service()
            session_active = service.is_running()
            state = service.get_state_snapshot()
            session_fps = state.fps if session_active else None
            session_inference_latency = state.inference_latency_ms if session_active else None
        except Exception as exc:
            logger.error("Failed to get live service state: %s", exc)
            session_active = False
            session_fps = None
            session_inference_latency = None

        # Task-classifier drift canary (model vs Gaussian fallback usage).
        from backend.services.drift_monitor import get_drift_monitor
        drift_summary = get_drift_monitor().summary()
        from app.schemas.api import ModelDriftMetrics
        drift = ModelDriftMetrics(**drift_summary)

        from app.core.postgres import pg_enabled
        database_engine = "PostgreSQL" if pg_enabled() else "SQLite"
        return DeploymentMetrics(
            backendStatus="ok",
            backendVersion=settings.APP_VERSION,
            backendUptimeSeconds=backend_uptime,
            databaseEngine=database_engine,
            databaseSizeBytes=db_size,
            databaseStatus=db_status,
            cameraCount=camera_count,
            registeredWorkerCount=len(workers),
            activeSessionCount=1 if session_active else 0,
            sessionActive=session_active,
            sessionFps=session_fps,
            sessionInferenceLatencyMs=session_inference_latency,
            drift=drift,
        )

    async def get_manager(self) -> ManagerSummary:
        """Return ManagerSummary from real SQLite + session files.

        * registeredWorkers  — count of rows in SQLite workers table
        * highRiskWorkers    — workers whose most recent completed session
                              had highest_risk_level == "HIGH"
        * todayAlerts        — alerts with created_at >= today UTC midnight
        * sessionsCompleted  — count of session JSON files on disk
        * mostCommonIssue    — most frequent trigger_rule across all alerts
        * workers            — per-worker summaries with risk from their
                              most recent session
        Falls back to mock data if the database is unavailable.
        Cached for 30s at module level to avoid re-scanning on every poll.
        """
        import time as _time
        global _manager_cache, _manager_cache_time  # noqa: PLW0603
        now = _time.time()
        if _manager_cache and (now - _manager_cache_time) < _MANAGER_CACHE_TTL:
            return _manager_cache

        from collections import defaultdict
        from datetime import datetime, timezone

        from app.core.database import list_workers, get_connection

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        try:
            all_workers = list_workers()
        except Exception:
            logger.warning("get_manager: database unavailable, using mock data")
            import app.utils.mock_data as mock_data
            # Mark the summary as degraded so the UI can flag mock numbers
            # instead of presenting them as real floor data.
            return ManagerSummary(**mock_data.MANAGER, degraded=True)

        # ── Load all persisted alerts ────────────────────────────────
        today_alerts_count = 0
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM alerts WHERE created_at >= ?",
                    (today_start,),
                ).fetchone()
                if row:
                    today_alerts_count = row["cnt"]
        except Exception as exc:
            logger.error("Failed to load persisted alerts: %s", exc)

        # ── Scan session files for counts + per-worker risk + issue ──
        from app.services.session_cache import get_all_sessions
        cached = get_all_sessions()
        session_count = len(cached)
        # worker_id -> (timestamp, highest_risk_level)
        latest_session: dict[str, tuple[str, str]] = {}
        issue_counts: dict[str, int] = {}
        for data in cached:
            wid = data.get("worker_id")
            if not wid:
                continue
            ts = data.get("session_timestamp", "")
            risk = data.get("highest_risk_level", "LOW")
            # Keep the most recent session per worker
            if wid not in latest_session or ts > latest_session[wid][0]:
                latest_session[wid] = (ts, risk)
            # Aggregate most_frequent_issue across sessions
            mfi = data.get("most_frequent_issue")
            mfi_count = data.get("most_frequent_issue_count", 0)
            if mfi and mfi_count:
                issue_counts[mfi] = issue_counts.get(mfi, 0) + mfi_count
        most_common_issue = max(issue_counts, key=issue_counts.get) if issue_counts else ""

        high_risk_count = sum(
            1 for _, (_, risk) in latest_session.items() if risk == "HIGH"
        )

        # ── Build per-worker summaries ───────────────────────────────
        workers_summary: List[WorkerSummary] = []
        dept_groups: dict[str, dict[str, float | int]] = {}
        for w in all_workers:
            wid = w["worker_id"]
            dept = w["department"]
            _, last_risk = latest_session.get(wid, ("", "LOW"))
            severity_map = {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high"}
            status = severity_map.get(last_risk, "low")
            risk_val = {"high": 70.0, "moderate": 35.0, "low": 0.0}.get(status, 0.0)
            workers_summary.append(WorkerSummary(
                id=wid,
                name=w["name"],
                status=status,
                task=dept,
                risk=risk_val,
            ))

            # Aggregate per department
            if dept not in dept_groups:
                dept_groups[dept] = {"risk_sum": 0.0, "count": 0, "high_count": 0}
            dept_groups[dept]["risk_sum"] += risk_val  # type: ignore[union-attr]
            dept_groups[dept]["count"] += 1  # type: ignore[union-attr]
            if last_risk == "HIGH":
                dept_groups[dept]["high_count"] += 1  # type: ignore[union-attr]

        dept_heatmap: list[DepartmentHeatmapEntry] = []
        for dept, data in sorted(dept_groups.items()):
            avg = data["risk_sum"] / data["count"]  # type: ignore[operator]
            level: RiskLevel = "high" if avg >= 50 else "moderate" if avg >= 20 else "low"
            dept_heatmap.append(DepartmentHeatmapEntry(
                department=dept,
                averageRisk=round(avg, 1),
                workerCount=data["count"],  # type: ignore[arg-type]
                highRiskCount=data["high_count"],  # type: ignore[arg-type]
                level=level,
            ))

        from app.services.manager_metrics import compute_manager_metrics
        metrics = compute_manager_metrics(cached)

        result = ManagerSummary(
            registeredWorkers=len(all_workers),
            highRiskWorkers=high_risk_count,
            todayAlerts=today_alerts_count,
            sessionsCompleted=session_count,
            mostCommonIssue=most_common_issue,
            workers=workers_summary,
            departmentHeatmap=dept_heatmap,
            weeklyImprovement=metrics["weeklyImprovement"],
            averageCompliance=metrics["averageCompliance"],
            healthScore=metrics["healthScore"],
        )
        _manager_cache = result
        _manager_cache_time = now
        return result

    async def get_alerts(self) -> List[Alert]:
        return []

    async def get_alerts_full(self) -> AlertsResponse:
        service = get_live_service()
        alert_data = service.alert_engine.export()

        active = [
            AlertResponse(**a) for a in alert_data.get("active_alerts", [])
        ]
        history = [
            AlertResponse(**a) for a in alert_data.get("history", [])
        ]

        critical_count = sum(1 for a in active if a.severity == "CRITICAL")
        ack_count = sum(1 for a in history if a.state == "ACKNOWLEDGED")

        return AlertsResponse(
            active=active,
            history=history,
            summary=AlertSummary(
                total_fired=alert_data.get("total_fired", 0),
                active_count=len(active),
                critical_count=critical_count,
                acknowledged_count=ack_count,
                consecutive_high=alert_data.get("consecutive_high", 0),
            ),
        )

    async def get_alerts_summary(self, recent_n: int = 6) -> AlertsResponse:
        """Lightweight alert fetch — summary + last N history + active.

        Avoids serializing the entire history list.
        """
        service = get_live_service()
        engine = service.alert_engine

        active = [AlertResponse(**a) for a in [v.to_dict() for v in engine.get_active_alerts()]]
        history_tail = [
            AlertResponse(**a) for a in [a.to_dict() for a in engine._history[-recent_n:]]
        ]

        critical_count = sum(1 for a in active if a.severity == "CRITICAL")
        total_fired = len(engine._history)
        ack_count = sum(1 for a in engine._history[-recent_n:] if a.state.value == "ACKNOWLEDGED")

        return AlertsResponse(
            active=active,
            history=history_tail,
            summary=AlertSummary(
                total_fired=total_fired,
                active_count=len(active),
                critical_count=critical_count,
                acknowledged_count=ack_count,
                consecutive_high=engine._consecutive_high,
            ),
        )

    async def get_context_snapshot(self) -> Optional[ContextSnapshotResponse]:
        service = get_live_service()
        state = service.get_state_snapshot()
        snapshot = state.context_snapshot
        if snapshot is None:
            return None

        guidance = None
        rula_score = None
        # Must be initialized BEFORE the ``if features:`` block — it is referenced
        # unconditionally below, so an empty feature dict (no person detected on
        # the latest frame) previously raised ``UnboundLocalError``, 500-ing the
        # dashboard + context-snapshot endpoints mid-session.
        rula_is_partial = False
        features = state.features
        if features:
            from backend.services.guidance import build_guidance
            raw = build_guidance(features)
            guidance = GuidanceSnapshot(
                feedback=[GuidanceFeedbackItem(**f) for f in raw["feedback"]],
                flagged_areas=raw["flagged_areas"],
                recommendations=raw["recommendations"],
            )
            from backend.services.features import compute_rula_informed_score
            rula_result = compute_rula_informed_score(features)
            rula_score = rula_result["rula_informed_score"]
            rula_is_partial = rula_result.get("is_partial_score", False)

        import math

        # Calibrated-risk advisory overlay: the REBA-trained model cross-checks
        # the rule-based band. Both are computed from the same features — the
        # model adds an independent, data-calibrated view that can catch rule
        # blind spots (advisory only; rules stay authoritative for alerting).
        calibrated_band: str | None = None
        calibrated_confidence: float | None = None
        calibrated_agrees: bool | None = None
        if features:
            from backend.services.risk_calibration import band_agrees, predict_risk_band
            calib = predict_risk_band(features)
            if calib is not None:
                calibrated_band = calib["band"]
                calibrated_confidence = calib["confidence"]
                calibrated_agrees = band_agrees(calib["band"], snapshot.risk_level)

        def _clean_score(v) -> float | None:
            """Coerce a score to a JSON-safe float (numpy scalars and NaN -> None)."""
            if v is None:
                return None
            try:
                if v != v:  # NaN check works for both python and numpy floats
                    return None
            except Exception:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        clean_scores = {k: _clean_score(v) for k, v in snapshot.feature_scores.items()}

        # Authoritative standard-method assessment (RULA vs REBA) — what drove
        # the risk level. Falls back to the computed RULA info when the frame
        # predates the standard assessment (e.g. empty features / no person).
        std = snapshot.standard_assessment or {}
        assessment_method = std.get("method") or None
        assessment_score = std.get("score")
        assessment_band = std.get("risk_level") or None

        return ContextSnapshotResponse(
            session_id=snapshot.session_id,
            frame_number=snapshot.frame_number,
            captured_at=snapshot.captured_at,
            worker_id=snapshot.worker_id,
            base_risk=snapshot.base_risk,
            context_modifier=snapshot.context_modifier,
            fatigue_score=snapshot.fatigue_score,
            exposure_score=snapshot.exposure_score,
            confidence_modifier=snapshot.confidence_modifier,
            final_risk=snapshot.final_risk,
            risk_score_normalized=snapshot.final_risk / 100.0,
            risk_level=snapshot.risk_level,
            safety_state=snapshot.safety_state,
            reason=snapshot.reason,
            active_rules=list(snapshot.active_rules),
            feature_scores=clean_scores,
            guidance=guidance,
            rula_informed_score=rula_score,
            rula_is_partial=rula_is_partial,
            assessment_method=assessment_method,
            assessment_score=assessment_score,
            assessment_band=assessment_band,
            calibrated_band=calibrated_band,
            calibrated_confidence=calibrated_confidence,
            calibrated_agrees=calibrated_agrees,
            unavailable_features=list(snapshot.unavailable_features),
            approximate_features=list(snapshot.approximate_features),
            lower_body_confidence=snapshot.lower_body_confidence,
            framing=dict(getattr(state, "framing", {}) or {}),
            person_count=int(getattr(state, "person_count", 1) or 1),
            person_boxes=list(getattr(state, "person_boxes", []) or []),
            person_identities=[
                dict(r) for r in (getattr(state, "person_identities", []) or [])
            ],
            identified_worker=dict(getattr(state, "identified_worker", {}) or {}),
        )

    async def get_recommendations(self) -> RecommendationsBundleResponse:
        service = get_live_service()
        export_data = service.recommendation_engine.export()

        bundle_data = export_data.get("bundle")
        if bundle_data is None:
            return RecommendationsBundleResponse(bundle=None, total_generated=0)

        recs = [
            RecommendationResponse(**r) for r in bundle_data.get("recommendations", [])
        ]
        bundle = RecommendationBundleData(
            recommendations=recs,
            summary=bundle_data.get("summary", ""),
            highest_priority=bundle_data.get("highest_priority", "Low"),
            generated_at=bundle_data.get("generated_at", ""),
        )
        return RecommendationsBundleResponse(
            bundle=bundle,
            total_generated=export_data.get("total_generated", 0),
        )

    async def get_history(self) -> HistoryResponse:
        service = get_live_service()
        export_data = service.history_engine.export()

        # The 2s poll re-serializes the full snapshot list; cap what the chart
        # needs (last 2000 points keeps multi-hour sessions responsive while
        # still showing the full trend shape). Statistics stay full-session.
        snapshots = export_data.get("snapshots", [])[-2000:]
        stats_raw = export_data.get("statistics", {})

        points = []
        for snap in snapshots:
            captured = snap.get("captured_at", "")
            time_str = ""
            if captured:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(captured.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S")
                except (ValueError, TypeError) as exc:
                    logger.warning("Failed to parse history timestamp %s: %s", captured, exc)
                    time_str = captured

            points.append(HistoryPoint(
                time=time_str,
                value=round(snap.get("final_risk", 0.0), 1),
                fatigue=round(snap.get("fatigue_score", 0.0), 1),
                exposure=round(snap.get("exposure_score", 0.0), 1),
                risk_level=snap.get("risk_level", "LOW"),
            ))

        statistics = HistoryStatistics(
            frames_stored=stats_raw.get("frames_stored", 0),
            session_duration_seconds=stats_raw.get("session_duration_seconds", 0.0),
            average_risk=stats_raw.get("average_risk", 0.0),
            maximum_risk=stats_raw.get("maximum_risk", 0.0),
            minimum_risk=stats_raw.get("minimum_risk", 0.0),
            average_fatigue=stats_raw.get("average_fatigue", 0.0),
            average_exposure=stats_raw.get("average_exposure", 0.0),
        )

        return HistoryResponse(points=points, statistics=statistics)
