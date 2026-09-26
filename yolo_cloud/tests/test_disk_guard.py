"""Tests for the free-space low-watermark clip guard (C4 disk guard).

The filesystem is faked via ``disk_guard._disk_usage`` so no test ever
depends on (or pressures) the real disk.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from yolo_cloud import disk_guard


class _FakeUsage:
    def __init__(self, free: int, total: int = 100 * 1024**3):
        self.free = free
        self.total = total
        self.used = total - free


def _make_clip(root: Path, name: str, size: int, age_days: float) -> Path:
    cam = root / "cam-1"
    cam.mkdir(parents=True, exist_ok=True)
    clip = cam / name
    clip.write_bytes(b"x" * size)
    stamp = time.time() - age_days * 86400
    os.utime(clip, (stamp, stamp))
    return clip


def test_above_watermark_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(disk_guard, "_disk_usage", lambda p: _FakeUsage(10 * 1024**3))

    stats = disk_guard.ensure_free_space(tmp_path / "clips", min_gb=2)

    assert stats["skipped"] is False
    assert stats["deleted_clips"] == 0
    assert stats["free_before_gb"] > stats["watermark_gb"]


def test_below_watermark_prunes_oldest_first(tmp_path, monkeypatch):
    # 1 GB free vs a 2 GB watermark — must free ~1 GB from the clips.
    monkeypatch.setattr(disk_guard, "_disk_usage", lambda p: _FakeUsage(1024**3))
    clips_root = tmp_path / "clips"
    oldest = _make_clip(clips_root, "old.mp4", 700 * 1024**2, age_days=30)
    middle = _make_clip(clips_root, "mid.mp4", 500 * 1024**2, age_days=10)
    newest = _make_clip(clips_root, "new.mp4", 100 * 1024**2, age_days=1)

    stats = disk_guard.ensure_free_space(clips_root, min_gb=2)

    # 1 GB free + (700 + 500) MB = ~2.17 GB >= 2 GB — the two oldest go and
    # the watermark is reached, so the newest clip survives.
    assert stats["deleted_clips"] == 2
    assert stats["freed_bytes"] == 700 * 1024**2 + 500 * 1024**2
    assert not oldest.exists() and not middle.exists()
    assert newest.exists()
    assert stats["free_after_gb"] >= 2.0
    assert disk_guard.STATS["clips_pruned_total"] >= 2


def test_deletes_only_until_watermark_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(disk_guard, "_disk_usage", lambda p: _FakeUsage(1024**3))
    clips_root = tmp_path / "clips"
    a = _make_clip(clips_root, "a.mp4", 900 * 1024**2, age_days=30)
    b = _make_clip(clips_root, "b.mp4", 900 * 1024**2, age_days=20)
    c = _make_clip(clips_root, "c.mp4", 900 * 1024**2, age_days=10)

    stats = disk_guard.ensure_free_space(clips_root, min_gb=1.5)

    # 1 GB + 900 MB = 1.875 GB >= 1.5 GB after the first deletion.
    assert stats["deleted_clips"] == 1
    assert not a.exists()
    assert b.exists() and c.exists()


def test_zero_disables_the_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(disk_guard, "_disk_usage", lambda p: _FakeUsage(1))
    clips_root = tmp_path / "clips"
    clip = _make_clip(clips_root, "keep.mp4", 10, age_days=30)

    stats = disk_guard.ensure_free_space(clips_root, min_gb=0)

    assert stats["skipped"] is True
    assert clip.exists()


def test_unusable_filesystem_never_raises(tmp_path, monkeypatch):
    def _boom(path):
        raise OSError("no such device")

    monkeypatch.setattr(disk_guard, "_disk_usage", _boom)

    stats = disk_guard.ensure_free_space(tmp_path / "clips", min_gb=2)

    assert stats.get("error")


def test_missing_clips_root_is_survivable(tmp_path, monkeypatch):
    monkeypatch.setattr(disk_guard, "_disk_usage", lambda p: _FakeUsage(1024**3))

    stats = disk_guard.ensure_free_space(tmp_path / "does-not-exist", min_gb=2)

    assert stats["deleted_clips"] == 0
    assert stats["free_after_gb"] < stats["watermark_gb"]  # honest: still low


def test_stats_snapshot_includes_counters_and_watermark():
    snap = disk_guard.stats_snapshot()
    assert "clips_pruned_total" in snap
    assert "min_free_gb" in snap
    assert snap == {**disk_guard.STATS, "min_free_gb": snap["min_free_gb"]}
