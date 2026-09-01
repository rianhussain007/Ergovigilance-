"""Session recording storage manager with auto-cleanup.

Manages disk space for session recordings, alerts, and reports.
Auto-deletes old files based on configurable retention policies.

Configurable via environment:
- STORAGE_MAX_MB: max total storage in MB (default 1000)
- STORAGE_RETENTION_DAYS: days to keep recordings (default 30)
- STORAGE_RECORDINGS_DIR: directory for recordings (default ./recordings)
- STORAGE_ALERTS_DIR: directory for alert images (default ./alerts)
- STORAGE_REPORTS_DIR: directory for exported reports (default ./reports)

Usage:
    from app.core.storage_manager import storage_manager
    storage_manager.cleanup_old_files()
    stats = storage_manager.get_stats()
"""

import os
import time
import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

STORAGE_MAX_MB = int(os.getenv("STORAGE_MAX_MB", "1000"))
STORAGE_RETENTION_DAYS = int(os.getenv("STORAGE_RETENTION_DAYS", "30"))
RECORDINGS_DIR = Path(os.getenv("STORAGE_RECORDINGS_DIR", "./recordings"))
ALERTS_DIR = Path(os.getenv("STORAGE_ALERTS_DIR", "./alerts"))
REPORTS_DIR = Path(os.getenv("STORAGE_REPORTS_DIR", "./reports"))


@dataclass
class StorageStats:
    """Storage usage statistics."""
    total_size_mb: float
    max_size_mb: int
    recordings_size_mb: float
    recordings_count: int
    alerts_size_mb: float
    alerts_count: int
    reports_size_mb: float
    reports_count: int
    usage_percent: float
    oldest_recording: Optional[str]
    newest_recording: Optional[str]


class StorageManager:
    """Manages disk storage for recordings, alerts, and reports."""

    def __init__(
        self,
        recordings_dir: Path = RECORDINGS_DIR,
        alerts_dir: Path = ALERTS_DIR,
        reports_dir: Path = REPORTS_DIR,
        max_size_mb: int = STORAGE_MAX_MB,
        retention_days: int = STORAGE_RETENTION_DAYS,
    ):
        self.recordings_dir = recordings_dir
        self.alerts_dir = alerts_dir
        self.reports_dir = reports_dir
        self.max_size_mb = max_size_mb
        self.retention_days = retention_days

        # Ensure directories exist
        for d in [recordings_dir, alerts_dir, reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _get_dir_size_mb(self, path: Path) -> float:
        """Get total size of a directory in MB."""
        if not path.exists():
            return 0.0
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024 * 1024)

    def _get_dir_count(self, path: Path) -> int:
        """Get file count in a directory."""
        if not path.exists():
            return 0
        return sum(1 for f in path.rglob("*") if f.is_file())

    def _get_oldest_newest(self, path: Path) -> tuple[Optional[str], Optional[str]]:
        """Get oldest and newest file timestamps."""
        files = sorted(path.rglob("*"), key=lambda f: f.stat().st_mtime if f.is_file() else float('inf'))
        files = [f for f in files if f.is_file()]
        if not files:
            return None, None
        oldest = datetime.fromtimestamp(files[0].stat().st_mtime).isoformat()
        newest = datetime.fromtimestamp(files[-1].stat().st_mtime).isoformat()
        return oldest, newest

    def get_stats(self) -> StorageStats:
        """Get current storage usage statistics."""
        rec_size = self._get_dir_size_mb(self.recordings_dir)
        alert_size = self._get_dir_size_mb(self.alerts_dir)
        report_size = self._get_dir_size_mb(self.reports_dir)
        total_size = rec_size + alert_size + report_size

        oldest, newest = self._get_oldest_newest(self.recordings_dir)

        return StorageStats(
            total_size_mb=round(total_size, 2),
            max_size_mb=self.max_size_mb,
            recordings_size_mb=round(rec_size, 2),
            recordings_count=self._get_dir_count(self.recordings_dir),
            alerts_size_mb=round(alert_size, 2),
            alerts_count=self._get_dir_count(self.alerts_dir),
            reports_size_mb=round(report_size, 2),
            reports_count=self._get_dir_count(self.reports_dir),
            usage_percent=round((total_size / self.max_size_mb) * 100, 1) if self.max_size_mb > 0 else 0,
            oldest_recording=oldest,
            newest_recording=newest,
        )

    def cleanup_old_files(self) -> dict:
        """Delete files older than retention_days. Returns cleanup summary."""
        cutoff = time.time() - (self.retention_days * 86400)
        deleted = {"recordings": 0, "alerts": 0, "reports": 0, "freed_mb": 0.0}

        for dirpath, category in [
            (self.recordings_dir, "recordings"),
            (self.alerts_dir, "alerts"),
            (self.reports_dir, "reports"),
        ]:
            if not dirpath.exists():
                continue
            for f in dirpath.rglob("*"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    try:
                        f.unlink()
                        deleted[category] += 1
                        deleted["freed_mb"] += size_mb
                        logger.info("Deleted old %s file: %s (%.2f MB)", category, f.name, size_mb)
                    except OSError as e:
                        logger.error("Failed to delete %s: %s", f, e)

        deleted["freed_mb"] = round(deleted["freed_mb"], 2)
        return deleted

    def enforce_storage_limit(self) -> dict:
        """If over storage limit, delete oldest recordings until under limit."""
        stats = self.get_stats()
        if stats.total_size_mb <= self.max_size_mb:
            return {"action": "none", "reason": "within_limit", "usage_percent": stats.usage_percent}

        freed = 0.0
        deleted = 0
        # Delete oldest recordings first
        recordings = sorted(
            self.recordings_dir.rglob("*"),
            key=lambda f: f.stat().st_mtime if f.is_file() else float('inf')
        )
        recordings = [f for f in recordings if f.is_file()]

        for f in recordings:
            if stats.total_size_mb - freed <= self.max_size_mb * 0.9:  # Stop at 90%
                break
            size_mb = f.stat().st_size / (1024 * 1024)
            try:
                f.unlink()
                freed += size_mb
                deleted += 1
                logger.info("Evicted recording to enforce limit: %s (%.2f MB)", f.name, size_mb)
            except OSError as e:
                logger.error("Failed to evict %s: %s", f, e)

        return {
            "action": "evicted",
            "files_deleted": deleted,
            "freed_mb": round(freed, 2),
            "usage_before_percent": stats.usage_percent,
        }

    def get_disk_info(self) -> dict:
        """Get system disk info for the storage partition."""
        try:
            usage = shutil.disk_usage(str(self.recordings_dir))
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "usage_percent": round((usage.used / usage.total) * 100, 1),
            }
        except Exception as e:
            logger.error("Failed to get disk info: %s", e)
            return {"error": str(e)}


# Singleton instance
storage_manager = StorageManager()
