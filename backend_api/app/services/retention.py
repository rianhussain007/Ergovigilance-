"""Data retention & disk-usage guardrails.

Enforces the platform's data-retention policy on disk artifacts:

- Session JSON files under ``outputs/sessions`` (per ``SESSION_RETENTION_DAYS``)
- Recorded session directories under ``recordings/<worker>/<session>``
  (per ``RECORDING_RETENTION_DAYS``)
- A hard disk cap on the recordings tree (``RECORDINGS_MAX_GB``) — when
  exceeded, the oldest sessions are evicted first.

All policy knobs come from environment variables (0 disables the check).
The functions accept explicit paths so they are unit-testable against
temporary directories; production paths honour the same env vars the API
modules use (``SESSIONS_DIR`` / ``RECORDINGS_DIR``).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SESSIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "outputs", "sessions")
)
_DEFAULT_RECORDINGS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")
)

_SECONDS_PER_DAY = 24 * 60 * 60

# Admin-tunable overrides are persisted here so the Settings UI can change the
# policy at runtime (env vars alone can't be edited from a running process).
_OVERRIDE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "retention.json",
)


def _load_overrides() -> dict:
    """Read persisted admin overrides ({} when missing/corrupt)."""
    try:
        if os.path.exists(_OVERRIDE_PATH):
            with open(_OVERRIDE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def set_retention_config(config: dict) -> tuple[dict, bool]:
    """Persist admin-tunable retention policy to the override file.

    Accepts a partial dict (``{session_retention_days: 60}``); unspecified
    keys keep their current effective value. Returns ``(merged_policy,
    persisted)`` — persisted is False when the override file could not be
    written (e.g. read-only filesystem), so callers can surface the failure
    instead of silently reporting success.
    """
    current = retention_config()
    merged = {
        "session_retention_days": int(config.get("session_retention_days", current["session_retention_days"])),
        "recording_retention_days": int(config.get("recording_retention_days", current["recording_retention_days"])),
        "recordings_max_gb": float(config.get("recordings_max_gb", current["recordings_max_gb"])),
    }
    persisted = False
    try:
        os.makedirs(os.path.dirname(_OVERRIDE_PATH), exist_ok=True)
        with open(_OVERRIDE_PATH, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        persisted = True
    except OSError as exc:
        logger.warning("Failed to persist retention overrides: %s", exc)
    return merged, persisted


def _resolve_dir(explicit: str | Path | None, env_name: str, default: str) -> Path:
    """Resolve a directory: explicit argument wins, then env, then default.

    Env is read at call time so policy changes (and tests) can override paths
    without re-importing the module. An empty env value is treated as unset to
    avoid accidentally resolving to the process cwd.
    """
    if explicit is not None:
        return Path(explicit)
    value = os.environ.get(env_name) or default
    return Path(value)


def _env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to the default on missing/bad values."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def retention_config() -> dict:
    """Read the retention policy — env defaults, overridden by the persisted
    admin config file (0 = disabled)."""
    overrides = _load_overrides()
    policy = {
        "session_retention_days": _env_int("SESSION_RETENTION_DAYS", 30),
        "recording_retention_days": _env_int("RECORDING_RETENTION_DAYS", 30),
        "recordings_max_gb": _env_int("RECORDINGS_MAX_GB", 20),
    }
    for key in policy:
        if key in overrides:
            policy[key] = overrides[key]
    return policy


def dir_size(path: Path) -> int:
    """Total byte size of a directory tree (best effort)."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def list_session_files(sessions_dir: str | Path | None = None) -> list[Path]:
    """Session summary JSON files (``session_*.json``) in the sessions dir."""
    base = _resolve_dir(sessions_dir, "SESSIONS_DIR", _DEFAULT_SESSIONS_DIR)
    if not base.exists():
        return []
    return [
        p
        for p in base.iterdir()
        if p.is_file() and p.name.startswith("session_") and p.suffix == ".json"
    ]


def list_recording_sessions(recordings_dir: str | Path | None = None) -> list[Path]:
    """Recorded session dirs: ``<recordings>/<worker>/<session>``.

    A dir counts as a session if it contains any of the recorded artifacts
    (summary.json, timeline.json, original.mp4) — this includes orphan dirs
    left by a crash mid-save, so they remain evictable by age and the disk cap.
    """
    base = _resolve_dir(recordings_dir, "RECORDINGS_DIR", _DEFAULT_RECORDINGS_DIR)
    if not base.exists():
        return []
    sessions: list[Path] = []
    for worker_dir in base.iterdir():
        if not worker_dir.is_dir():
            continue
        for session_dir in worker_dir.iterdir():
            if not session_dir.is_dir():
                continue
            if any((session_dir / name).exists() for name in ("summary.json", "timeline.json", "original.mp4")):
                sessions.append(session_dir)
    return sessions


def _parse_session_timestamp(summary: dict) -> float | None:
    """Epoch seconds from a summary's ``session_timestamp`` ("%Y%m%d_%H%M%S_%f")."""
    ts = summary.get("session_timestamp") if isinstance(summary, dict) else None
    if not ts:
        return None
    try:
        return datetime.strptime(str(ts), "%Y%m%d_%H%M%S_%f").timestamp()
    except ValueError:
        return None


def _session_epoch(session_dir: Path) -> float:
    """Best available epoch for a session dir.

    Directory mtimes are rewritten by git checkout / rsync / file copies, which
    makes them unreliable for age decisions — so prefer the authoritative
    ``summary.json`` ``session_timestamp``, falling back to the dir mtime.
    """
    summary_path = session_dir / "summary.json"
    try:
        if summary_path.exists():
            with open(summary_path, encoding="utf-8") as f:
                ts = _parse_session_timestamp(json.load(f))
            if ts is not None:
                return ts
    except (OSError, json.JSONDecodeError):
        pass
    try:
        return session_dir.stat().st_mtime
    except OSError:
        return 0.0


def cleanup_sessions(
    max_age_days: int,
    sessions_dir: str | Path | None = None,
) -> dict:
    """Delete session JSON files older than ``max_age_days`` (0 disables)."""
    if max_age_days <= 0:
        return {"skipped": True, "deleted_files": 0, "freed_bytes": 0}
    cutoff = time.time() - max_age_days * _SECONDS_PER_DAY
    deleted = 0
    freed = 0
    for path in list_session_files(sessions_dir):
        try:
            stat = path.stat()
            if stat.st_mtime < cutoff:
                freed += stat.st_size
                path.unlink()
                deleted += 1
                logger.info("Retention: removed session file %s", path)
        except OSError:
            continue
    return {"skipped": False, "deleted_files": deleted, "freed_bytes": freed}


def cleanup_recordings(
    max_age_days: int,
    recordings_dir: str | Path | None = None,
) -> dict:
    """Delete recorded session dirs older than ``max_age_days`` (0 disables)."""
    if max_age_days <= 0:
        return {"skipped": True, "deleted_dirs": 0, "freed_bytes": 0}
    cutoff = time.time() - max_age_days * _SECONDS_PER_DAY
    deleted = 0
    freed = 0
    for session_dir in list_recording_sessions(recordings_dir):
        if _session_epoch(session_dir) >= cutoff:
            continue
        try:
            freed += dir_size(session_dir)
            shutil.rmtree(session_dir, ignore_errors=True)
            deleted += 1
            logger.warning("Retention: removed recording %s", session_dir)
        except OSError:
            continue
    return {"skipped": False, "deleted_dirs": deleted, "freed_bytes": freed}


def enforce_recordings_cap(
    max_gb: float,
    recordings_dir: str | Path | None = None,
) -> dict:
    """Evict oldest recordings until the tree fits under ``max_gb`` (0 disables)."""
    if max_gb <= 0:
        return {"skipped": True, "evicted_dirs": 0, "freed_bytes": 0}
    base = _resolve_dir(recordings_dir, "RECORDINGS_DIR", _DEFAULT_RECORDINGS_DIR)
    cap_bytes = int(max_gb * 1024**3)
    total = dir_size(base)
    if total <= cap_bytes:
        return {
            "skipped": False,
            "evicted_dirs": 0,
            "freed_bytes": 0,
            "total_bytes": total,
            "cap_bytes": cap_bytes,
        }
    sessions = sorted(
        list_recording_sessions(base),
        key=_session_epoch,
    )
    freed = 0
    evicted = 0
    for session_dir in sessions:
        if total - freed <= cap_bytes:
            break
        try:
            size = dir_size(session_dir)
            shutil.rmtree(session_dir, ignore_errors=True)
            freed += size
            evicted += 1
            logger.warning(
                "Retention: evicted %s to stay under %.1f GB cap (freed %.1f MB)",
                session_dir,
                max_gb,
                size / 1e6,
            )
        except OSError:
            continue
    return {
        "skipped": False,
        "evicted_dirs": evicted,
        "freed_bytes": freed,
        "total_bytes": total,
        "cap_bytes": cap_bytes,
    }


def run_retention() -> dict:
    """Run the full retention policy. Safe to call on every interval."""
    cfg = retention_config()
    stats = {
        "session_retention_days": cfg["session_retention_days"],
        "recording_retention_days": cfg["recording_retention_days"],
        "recordings_max_gb": cfg["recordings_max_gb"],
        "sessions": cleanup_sessions(cfg["session_retention_days"]),
        "recordings": cleanup_recordings(cfg["recording_retention_days"]),
        "disk_cap": enforce_recordings_cap(cfg["recordings_max_gb"]),
    }
    logger.info("Retention run: sessions=%s recordings=%s disk_cap=%s",
                stats["sessions"], stats["recordings"], stats["disk_cap"])
    return stats


def storage_stats() -> dict:
    """Current on-disk usage and policy (for the admin retention endpoints)."""
    sessions_dir = _resolve_dir(None, "SESSIONS_DIR", _DEFAULT_SESSIONS_DIR)
    recordings_dir = _resolve_dir(None, "RECORDINGS_DIR", _DEFAULT_RECORDINGS_DIR)
    return {
        "policy": retention_config(),
        "sessions": {
            "dir": str(sessions_dir),
            "file_count": len(list_session_files()),
            "bytes": dir_size(sessions_dir),
        },
        "recordings": {
            "dir": str(recordings_dir),
            "session_count": len(list_recording_sessions()),
            "bytes": dir_size(recordings_dir),
        },
    }
