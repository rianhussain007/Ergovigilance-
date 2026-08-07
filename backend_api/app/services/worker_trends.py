from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.database import list_workers
from app.schemas.api import (
    DepartmentTrendEntry,
    StationAnalysisEntry,
    TemporalCurvePoint,
    TrendDirection,
    WorkerTemporalCurve,
    WorkerTrendPoint,
    WorkerTrendsResponse,
)

logger = logging.getLogger(__name__)

_RISK_SCORE_MAP: dict[str, float] = {
    "LOW": 0.0,
    "MEDIUM": 50.0,
    "HIGH": 100.0,
}

_CAMERA_ID_ALIASES: dict[str, str] = {
    "cam1": "cam-01",
    "cam2": "cam-02",
    "cam3": "cam-03",
    "camera1": "cam-01",
    "camera2": "cam-02",
    "camera3": "cam-03",
}

_STATION_DISPLAY_NAMES: dict[str, str] = {
    "cam-01": "Assembly Line A — Station 1",
    "cam-02": "Assembly Line B — Station 3",
    "cam-03": "Loading Dock — Bay 2",
}


def _load_all_sessions(sessions_dir: Path) -> list[dict[str, Any]]:
    """Load all session JSON files from disk (uses shared cache)."""
    from app.services.session_cache import get_all_sessions
    return list(get_all_sessions())


def _load_all_worker_ids(sessions_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Scan session files and group them by worker_id (uses shared cache)."""
    from app.services.session_cache import get_all_sessions
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for data in get_all_sessions():
        wid = data.get("worker_id")
        if not wid:
            continue
        groups[wid].append(data)
    for wid in groups:
        groups[wid].sort(key=lambda s: s.get("session_timestamp", ""))
    return dict(groups)


def _avg_risk_score(sessions: list[dict[str, Any]]) -> float:
    """Compute average risk score across sessions using risk_percentages."""
    total = 0.0
    count = 0
    for s in sessions:
        rp = s.get("risk_percentages")
        if not rp:
            continue
        low = rp.get("LOW", 0)
        med = rp.get("MEDIUM", 0)
        high = rp.get("HIGH", 0)
        total_frames = low + med + high
        if total_frames == 0:
            continue
        total += (med * 50.0 + high * 100.0) / total_frames
        count += 1
    return round(total / count, 1) if count else 0.0


def _session_risk_score(session: dict[str, Any]) -> float:
    """Compute risk score for a single session."""
    rp = session.get("risk_percentages")
    if not rp:
        return 0.0
    low = rp.get("LOW", 0)
    med = rp.get("MEDIUM", 0)
    high = rp.get("HIGH", 0)
    total_frames = low + med + high
    if total_frames == 0:
        return 0.0
    return (med * 50.0 + high * 100.0) / total_frames


def _compute_trend(sessions: list[dict[str, Any]]) -> TrendDirection:
    """Compare first half vs second half of a worker's sessions."""
    if len(sessions) < 2:
        return "stable"
    scores = []
    for s in sessions:
        level = s.get("highest_risk_level", "LOW")
        scores.append(_RISK_SCORE_MAP.get(level, 0.0))
    mid = len(scores) // 2
    early = sum(scores[:mid]) / mid
    late = sum(scores[mid:]) / (len(scores) - mid)
    diff = late - early
    if diff > 10.0:
        return "deteriorating"
    if diff < -10.0:
        return "improving"
    return "stable"


def _latest_risk_level(sessions: list[dict[str, Any]]) -> str:
    """Return the highest_risk_level of the most recent session."""
    if not sessions:
        return "LOW"
    return sessions[-1].get("highest_risk_level", "LOW")


def _parse_session_week(timestamp: str) -> str | None:
    """Parse session_timestamp (YYYYMMDD_HHMMSS or YYYYMMDD_HHMMSS_mmm) and return ISO week string YYYY-Www."""
    match = re.match(r"(\d{4})(\d{2})(\d{2})", timestamp)
    if not match:
        return None
    try:
        dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    except ValueError:
        return None


def _compute_temporal_curves(
    grouped: dict[str, list[dict[str, Any]]],
    worker_map: dict[str, dict[str, Any]],
) -> list[WorkerTemporalCurve]:
    """Compute weekly risk score time series per worker."""
    curves: list[WorkerTemporalCurve] = []
    for wid, sessions in grouped.items():
        if len(sessions) < 2:
            continue
        w = worker_map.get(wid, {})
        # Group sessions by ISO week
        week_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in sessions:
            ts = s.get("session_timestamp", "")
            week = _parse_session_week(ts)
            if week:
                week_groups[week].append(s)
        if not week_groups:
            continue
        points: list[TemporalCurvePoint] = []
        for week in sorted(week_groups.keys()):
            week_sessions = week_groups[week]
            avg = _avg_risk_score(week_sessions)
            points.append(TemporalCurvePoint(
                week=week,
                avg_risk_score=avg,
                sessions=len(week_sessions),
            ))
        if len(points) >= 2:
            curves.append(WorkerTemporalCurve(
                worker_id=wid,
                name=w.get("name", wid),
                department=w.get("department", "Unknown"),
                points=points,
            ))
    curves.sort(key=lambda c: c.worker_id)
    return curves


def _normalize_camera_id(raw: str | None) -> str | None:
    """Normalize inconsistent camera_id values to a canonical form."""
    if not raw:
        return None
    normalized = raw.strip().lower()
    return _CAMERA_ID_ALIASES.get(normalized, normalized)


def _compute_station_analysis(
    all_sessions: list[dict[str, Any]],
    worker_map: dict[str, dict[str, Any]],
) -> list[StationAnalysisEntry]:
    """Group sessions by normalized camera_id and compute per-station risk patterns."""
    station_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in all_sessions:
        cam = _normalize_camera_id(s.get("camera_id"))
        if not cam:
            continue
        station_groups[cam].append(s)

    entries: list[StationAnalysisEntry] = []
    for cam_id, sessions in sorted(station_groups.items()):
        risk_scores = [_session_risk_score(s) for s in sessions]
        avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0
        high_count = sum(1 for s in sessions if s.get("highest_risk_level") == "HIGH")
        worker_ids = set()
        for s in sessions:
            wid = s.get("worker_id")
            if wid:
                worker_ids.add(wid)
        worker_count = len(worker_ids) if worker_ids else len(set(
            w.get("worker_id") for w in (worker_map.values() if worker_map else [])
        ))
        display = _STATION_DISPLAY_NAMES.get(cam_id, cam_id.replace("cam-", "Station ").replace("cam", "Station "))
        entries.append(StationAnalysisEntry(
            station_id=cam_id,
            display_name=display,
            sessions=len(sessions),
            avg_risk_score=avg_risk,
            high_risk_count=high_count,
            worker_count=worker_count,
        ))
    return entries


def compute_worker_trends(project_root: Path) -> WorkerTrendsResponse:
    """Compute per-worker fatigue trends, department patterns, temporal curves, and station analysis."""
    sessions_dir = project_root / "outputs" / "sessions"
    all_sessions = _load_all_sessions(sessions_dir)
    grouped = _load_all_worker_ids(sessions_dir)
    total_workers = 0
    workers_with_data = 0

    try:
        all_workers = list_workers()
        total_workers = len(all_workers)
    except Exception as exc:
        logger.error("Failed to load workers table: %s", exc)
        all_workers = []

    worker_map: dict[str, dict[str, Any]] = {
        w["worker_id"]: dict(w) for w in all_workers
    }

    # Per-worker trend points
    worker_points: list[WorkerTrendPoint] = []
    for wid, sessions in grouped.items():
        if not sessions:
            continue
        workers_with_data += 1
        w = worker_map.get(wid, {})
        score = _avg_risk_score(sessions)
        trend = _compute_trend(sessions)
        latest = _latest_risk_level(sessions)
        worker_points.append(WorkerTrendPoint(
            worker_id=wid,
            name=w.get("name", wid),
            department=w.get("department", "Unknown"),
            shift=w.get("shift", "Unknown"),
            sessions=len(sessions),
            avg_risk_score=score,
            latest_risk_level=latest,
            trend=trend,
        ))
    worker_points.sort(key=lambda p: p.avg_risk_score, reverse=True)

    # Per-department aggregation
    dept_groups: dict[str, dict[str, Any]] = {}
    for p in worker_points:
        if p.department not in dept_groups:
            dept_groups[p.department] = {
                "count": 0, "risk_sum": 0.0, "high_count": 0,
                "improving": 0, "deteriorating": 0,
            }
        d = dept_groups[p.department]
        d["count"] += 1
        d["risk_sum"] += p.avg_risk_score
        if p.latest_risk_level == "HIGH":
            d["high_count"] += 1
        if p.trend == "improving":
            d["improving"] += 1
        elif p.trend == "deteriorating":
            d["deteriorating"] += 1

    departments: list[DepartmentTrendEntry] = []
    for dept, d in sorted(dept_groups.items()):
        avg = d["risk_sum"] / d["count"]
        trend: TrendDirection = (
            "deteriorating" if d["deteriorating"] > d["improving"]
            else "improving" if d["improving"] > d["deteriorating"]
            else "stable"
        )
        departments.append(DepartmentTrendEntry(
            department=dept,
            worker_count=d["count"],
            avg_risk_score=round(avg, 1),
            high_risk_count=d["high_count"],
            improving_count=d["improving"],
            deteriorating_count=d["deteriorating"],
            trend=trend,
        ))

    # Temporal curves (weekly risk per worker, only workers with >= 2 weeks of data)
    temporal_curves = _compute_temporal_curves(grouped, worker_map)

    # Station analysis (group by normalized camera_id)
    station_analysis = _compute_station_analysis(all_sessions, worker_map)

    return WorkerTrendsResponse(
        total_workers=total_workers,
        total_workers_with_data=workers_with_data,
        workers=worker_points,
        departments=departments,
        temporal_curves=temporal_curves,
        station_analysis=station_analysis,
    )
