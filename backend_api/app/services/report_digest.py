"""Nightly / on-demand risk digest.

Aggregates the most recent sessions into a compact JSON summary — session
count, risk distribution, alert volume, top issue, per-session rows — and
writes it to ``<project>/outputs/reports/digest_*.json``. Safety managers get
zero-touch evidence: a file per period they can open, forward, or feed into
the AI assistant without logging in and clicking through Reports.

The digest deliberately stays JSON-only (no Playwright/PDF dependency), so the
scheduled loop is cheap, headless-safe, and cannot fail the service.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.session_cache import get_all_sessions

logger = logging.getLogger(__name__)

# Digests are written under the project's outputs dir (same place the dev
# flows write reports). Override with REPORTS_DIR.
_REPORTS_DIR = os.environ.get(
    "REPORTS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "outputs", "reports"),
)
# Keep only this many digest files on disk (rotation guard).
_MAX_DIGESTS = 30


def _parse_ts(value: Any) -> datetime | None:
    """Parse a session_timestamp (``%Y%m%d_%H%M%S%f`` or ISO) to datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    for fmt in ("%Y%m%d_%H%M%S%f", "%Y%m%d_%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _since_dt(since_hours: float) -> datetime:
    return datetime.now() - timedelta(hours=since_hours)


def generate_digest(since_hours: float = 24.0, save: bool = True) -> dict[str, Any]:
    """Aggregate the last *since_hours* of sessions into a digest.

    Returns ``{digest, saved: bool, path}`` — ``saved`` is False when the
    digest was computed but not written (or there was nothing to write).
    """
    cutoff = _since_dt(since_hours)
    recent: list[dict[str, Any]] = []
    for s in get_all_sessions():
        ts = _parse_ts(s.get("session_timestamp"))
        if ts is None or ts < cutoff:
            continue
        recent.append(s)

    total_frames = sum(int(s.get("total_frames") or 0) for s in recent)
    risk_sums = {"LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0}
    weighted = sum(max(1, int(s.get("total_frames") or 0)) for s in recent)
    alert_count = 0
    issue_counts: dict[str, int] = {}
    highest = "LOW"
    for s in recent:
        rp = s.get("risk_percentages") or {}
        for level in risk_sums:
            risk_sums[level] += float(rp.get(level) or 0.0) * max(1, int(s.get("total_frames") or 0))
        alerts = s.get("alerts") or []
        if isinstance(alerts, list):
            alert_count += sum(1 for a in alerts if isinstance(a, dict))
        issue = s.get("most_frequent_issue")
        if issue:
            issue_counts[str(issue)] = issue_counts.get(str(issue), 0) + 1
        if s.get("highest_risk_level") in ("HIGH", "CRITICAL"):
            highest = "HIGH"
        elif s.get("highest_risk_level") == "MEDIUM" and highest == "LOW":
            highest = "MEDIUM"

    top_issue = max(issue_counts.items(), key=lambda kv: kv[1])[0] if issue_counts else None

    digest = {
        "digest_type": "risk_digest",
        "generated_at": datetime.now().isoformat(),
        "window_hours": since_hours,
        "period_start": cutoff.isoformat(),
        "summary": {
            "session_count": len(recent),
            "total_frames": total_frames,
            "alert_count": alert_count,
            "highest_risk_level": highest,
            "top_issue": top_issue,
            "risk_percentages": (
                {
                    k: round(v / weighted, 1) if weighted else 0.0
                    for k, v in risk_sums.items()
                }
                if recent
                else {"LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0}
            ),
        },
        "sessions": [
            {
                "session_id": s.get("session_id"),
                "session_timestamp": s.get("session_timestamp"),
                "worker_id": s.get("worker_id"),
                "task_name": s.get("task_name"),
                "total_frames": s.get("total_frames"),
                "highest_risk_level": s.get("highest_risk_level"),
                "alert_count": (
                    sum(1 for a in (s.get("alerts") or []) if isinstance(a, dict))
                    if isinstance(s.get("alerts"), list)
                    else 0
                ),
            }
            for s in sorted(recent, key=lambda x: str(x.get("session_timestamp", "")), reverse=True)
        ][:50],
    }

    path: str | None = None
    saved = False
    if save and recent:
        try:
            reports_dir = Path(_REPORTS_DIR)
            reports_dir.mkdir(parents=True, exist_ok=True)
            filename = f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            path = str(reports_dir / filename)
            tmp = reports_dir / (filename + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(digest, f, indent=2)
            os.replace(tmp, path)
            saved = True
            _prune_old_digests(reports_dir)
        except Exception as exc:  # noqa: BLE001 - a failed digest write must never break the caller
            logger.warning("Digest write failed: %s", exc)

    return {"digest": digest, "saved": saved, "path": path}


def list_digests() -> list[dict[str, Any]]:
    """Return saved digests (newest first), with a summary preview each."""
    reports_dir = Path(_REPORTS_DIR)
    if not reports_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for filepath in sorted(reports_dir.glob("digest_*.json"), reverse=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            out.append(
                {
                    "path": str(filepath),
                    "filename": filepath.name,
                    "generated_at": data.get("generated_at"),
                    "summary": data.get("summary"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read digest %s: %s", filepath.name, exc)
    return out


def _prune_old_digests(reports_dir: Path) -> None:
    """Keep at most ``_MAX_DIGESTS`` digest files (oldest removed)."""
    files = sorted(reports_dir.glob("digest_*.json"))
    for stale in files[: max(0, len(files) - _MAX_DIGESTS)]:
        try:
            stale.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
