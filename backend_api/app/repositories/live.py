"""Live repository — reads from LiveState instead of mock data.

Replaces MockRepository when the CV pipeline is active.
Maintains the same DashboardResponse schema so React interfaces stay unchanged.
"""

import logging
import os
import sys
import time
from typing import List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.repositories.base import DashboardRepository
from app.schemas.api import (
    DashboardResponse,
    SessionRecord,
    TrendResponse,
    CameraInfo,
    WorkstationInfo,
    DeploymentMetrics,
    ManagerSummary,
    WorkerSummary,
    Alert,
    ReportRecord,
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
            },
            liveStatus={
                "riskLevel": {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high"}.get(state.risk_level, "low"),
                "riskScore": state.risk_score,
                "confidence": state.confidence,
                "currentTask": state.task_name,
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
                task="Monitoring Session",
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

        sessions_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "outputs", "sessions")

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
            return None

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
            video_path=data.get("video_path"),
            video_recording_status=data.get("video_recording_status"),
            video_recording_error=data.get("video_recording_error"),
            video_frame_count=data.get("video_frame_count"),
            video_codec=data.get("video_codec"),
        )

    async def get_trends(self) -> TrendResponse:
        import app.utils.mock_data as mock_data
        return TrendResponse(**mock_data.TRENDS)

    async def get_reports(self) -> List[ReportRecord]:
        """Return real reports from session data."""
        import os
        import json
        from datetime import datetime

        sessions_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "outputs", "sessions")
        reports = []

        if os.path.exists(sessions_dir):
            for filename in os.listdir(sessions_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(sessions_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                            session_id = data.get("session_id", filename.replace(".json", ""))
                            ended_at = data.get("ended_at", "")
                            stats = data.get("statistics", {})
                            alerts_count = len(data.get("alerts", []))

                            # Calculate report date
                            try:
                                if ended_at:
                                    dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                                    report_date = dt.strftime("%Y-%m-%d")
                                else:
                                    report_date = datetime.now().strftime("%Y-%m-%d")
                            except (ValueError, TypeError) as exc:
                                logger.warning("Failed to parse ended_at %s: %s", ended_at, exc)
                                report_date = datetime.now().strftime("%Y-%m-%d")

                            # Determine report type
                            if alerts_count > 0:
                                report_type = "safety"
                                title = f"Safety Report — {session_id}"
                            else:
                                report_type = "session"
                                title = f"Session Report — {session_id}"

                            reports.append(ReportRecord(
                                id=f"RPT-{session_id}",
                                title=title,
                                type=report_type,
                                date=report_date,
                                status="completed",
                                size=f"{len(data.get('snapshots', []))} snapshots",
                            ))
                    except Exception as exc:
                        logger.warning("Skipping corrupt report file %s: %s", filename, exc)

        # Sort by date (newest first)
        reports.sort(key=lambda x: x.date if x.date else "", reverse=True)
        return reports

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

        from backend.services.camera_manager import detect_cameras

        # Module-level cache (survives per-request instances)
        global _camera_cache, _camera_cache_time  # noqa: PLW0603

        active_index: Optional[int] = getattr(service, "current_camera_index", None) if is_running else None

        # Re-probe only when cache is expired or empty.
        # This preserves the LED-flicker fix while still allowing the idle UI
        # to show detected cameras as "Available" once they are discovered.
        now = time.time()
        if not _camera_cache or (now - _camera_cache_time) > _camera_cache_ttl:
            age = now - _camera_cache_time if _camera_cache_time else float("inf")
            if is_running:
                logger.info("[get_cameras] cache expired (age=%.1fs) — probing physical devices", age)
            else:
                logger.info("[get_cameras] idle cache miss (age=%.1fs) — probing physical devices once", age)
            detected = detect_cameras(fast=True, max_index=5)
            fresh: list[CameraInfo] = []
            for cam in detected:
                fresh.append(CameraInfo(
                    id=f"cam-{cam.index}",
                    name=cam.name or f"Camera {cam.index}",
                    worker="",
                    fps=0,
                    risk="low",
                    recording=False,
                    uptime="",
                    status="available",
                ))
            _camera_cache = fresh
            _camera_cache_time = now
            logger.info("[get_cameras] probed %d camera(s), next probe in %ds", len(fresh), _camera_cache_ttl)
        else:
            age = now - _camera_cache_time
            logger.info("[get_cameras] cache hit (age=%.1fs); reusing cached %d camera(s)", age, len(_camera_cache))

        if not _camera_cache:
            return []

        risk_map = {"LOW": "low", "MEDIUM": "moderate", "HIGH": "high"}
        result: list[CameraInfo] = []
        for base in _camera_cache:
            idx = int(base.id.replace("cam-", "")) if base.id.startswith("cam-") else -1
            if is_running and active_index is not None and idx == active_index:
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
        global _camera_cache, _camera_cache_time  # noqa: PLW0603
        now = time.time()
        if not _camera_cache or (now - _camera_cache_time) > _camera_cache_ttl:
            _camera_cache_time = now
            try:
                detected = detect_cameras(fast=True, max_index=5)
                _camera_cache = [
                    CameraInfo(
                        id=f"cam-{cam.index}",
                        name=cam.name or f"Camera {cam.index}",
                        worker="", fps=0, risk="low",
                        recording=False, uptime="", status="available",
                    )
                    for cam in detected
                ]
            except Exception as exc:
                logger.warning("get_deployment camera probe failed: %s", exc)
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

        return DeploymentMetrics(
            backendStatus="ok",
            backendVersion=settings.APP_VERSION,
            backendUptimeSeconds=backend_uptime,
            databaseEngine="SQLite",
            databaseSizeBytes=db_size,
            databaseStatus=db_status,
            cameraCount=camera_count,
            registeredWorkerCount=len(workers),
            activeSessionCount=1 if session_active else 0,
            sessionActive=session_active,
            sessionFps=session_fps,
            sessionInferenceLatencyMs=session_inference_latency,
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
            return ManagerSummary(**mock_data.MANAGER)

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

        result = ManagerSummary(
            registeredWorkers=len(all_workers),
            highRiskWorkers=high_risk_count,
            todayAlerts=today_alerts_count,
            sessionsCompleted=session_count,
            mostCommonIssue=most_common_issue,
            workers=workers_summary,
            departmentHeatmap=dept_heatmap,
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
            unavailable_features=list(snapshot.unavailable_features),
            approximate_features=list(snapshot.approximate_features),
            lower_body_confidence=snapshot.lower_body_confidence,
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

        snapshots = export_data.get("snapshots", [])
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
