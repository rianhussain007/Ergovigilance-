"""Free-space low-watermark guard for alert clips (C4 disk guard).

HIGH-alert clips (``CloudCameraProcessor._save_clip``) are the one
cloud-core write path that can flood disk *between* backend retention
passes (age caps + ``RECORDINGS_MAX_GB`` run every ``RETENTION_INTERVAL_HOURS``).
This guard fires at write time: when free space on the clips filesystem
drops below ``CLIP_MIN_FREE_GB`` (default 2, 0 disables), the oldest clips
are deleted until the watermark is restored.

The guard never raises — an unusable filesystem logs and returns an
``error`` stats dict so clip evidence handling continues. Process-level
counters are surfaced on ``GET /cloud/health``.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CLIP_EXTS = (".mp4", ".avi")

# Surfaced on /cloud/health (the disk-guard "metric").
STATS: dict = {
    "clips_pruned_total": 0,
    "freed_bytes_total": 0,
    "last_prune_at": None,
    "last_prune_deleted": 0,
    "last_free_gb": None,
}


def min_free_gb() -> float:
    """Watermark in GB from CLIP_MIN_FREE_GB (0 disables the guard)."""
    try:
        return float(os.getenv("CLIP_MIN_FREE_GB", "2"))
    except (TypeError, ValueError):
        return 2.0


def _disk_usage(path: str | Path):
    """Indirection point so tests can fake a full filesystem."""
    return shutil.disk_usage(path)


def _existing_dir(path: str | Path) -> Path:
    """shutil.disk_usage needs an existing path — walk up to the nearest one."""
    p = Path(path)
    while not p.exists():
        if p == p.parent:
            break
        p = p.parent
    return p


def list_clips(clips_root: str | Path) -> list[Path]:
    """Clip files under ``clips_root`` (any camera subdir), oldest first."""
    root = Path(clips_root)
    if not root.exists():
        return []
    clips = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in CLIP_EXTS
    ]
    clips.sort(key=lambda p: p.stat().st_mtime)
    return clips


def ensure_free_space(clips_root: str | Path, min_gb: float | None = None) -> dict:
    """Prune oldest clips until free space >= the watermark.

    Returns a stats dict (``skipped`` when disabled or already above the
    watermark, ``error`` when the filesystem could not be queried).
    """
    threshold = min_free_gb() if min_gb is None else min_gb
    if threshold <= 0:
        return {"skipped": True, "disabled": True, "watermark_gb": threshold}

    try:
        usage = _disk_usage(_existing_dir(clips_root))
        free_gb = usage.free / 1024**3
        STATS["last_free_gb"] = round(free_gb, 3)
    except OSError as exc:
        logger.warning("Disk guard: cannot stat filesystem for %s (%s)", clips_root, exc)
        return {"skipped": False, "error": str(exc), "watermark_gb": threshold}

    if free_gb >= threshold:
        return {
            "skipped": False,
            "disabled": False,
            "deleted_clips": 0,
            "freed_bytes": 0,
            "free_before_gb": round(free_gb, 3),
            "free_after_gb": round(free_gb, 3),
            "watermark_gb": threshold,
        }

    deleted = 0
    freed = 0
    for clip in list_clips(clips_root):
        if free_gb + freed / 1024**3 >= threshold:
            break
        try:
            size = clip.stat().st_size
            clip.unlink()
        except OSError:
            continue
        freed += size
        deleted += 1

    STATS["clips_pruned_total"] += deleted
    STATS["freed_bytes_total"] += freed
    STATS["last_prune_at"] = time.time()
    STATS["last_prune_deleted"] = deleted

    free_after = free_gb + freed / 1024**3
    if deleted:
        logger.warning(
            "Disk guard: free %.2f GB < watermark %.1f GB — pruned %d oldest "
            "clip(s), freed %.1f MB (now %.2f GB)",
            free_gb, threshold, deleted, freed / 1e6, free_after,
        )
    else:
        logger.warning(
            "Disk guard: free %.2f GB < watermark %.1f GB but no clips left to prune",
            free_gb, threshold,
        )
    return {
        "skipped": False,
        "disabled": False,
        "deleted_clips": deleted,
        "freed_bytes": freed,
        "free_before_gb": round(free_gb, 3),
        "free_after_gb": round(free_after, 3),
        "watermark_gb": threshold,
    }


def stats_snapshot() -> dict:
    """Copy of the process counters for health/status endpoints."""
    snapshot = dict(STATS)
    snapshot["min_free_gb"] = min_free_gb()
    return snapshot
