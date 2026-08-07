"""Tests for the data-retention service (P0 #4).

All tests operate on temporary directories only — never on real data.
"""

import os
import time
from pathlib import Path

from app.services import retention


def _make_old(path: Path, days: int) -> None:
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


def test_age_based_session_cleanup(tmp_path: Path) -> None:
    sess = tmp_path / "sessions"
    sess.mkdir()
    old = sess / "session_old.json"
    new = sess / "session_new.json"
    old.write_text("{}")
    new.write_text("{}")
    _make_old(old, 40)  # older than the 30-day policy

    stats = retention.cleanup_sessions(30, sess)

    assert stats["deleted_files"] == 1
    assert not old.exists()
    assert new.exists()


def test_session_cleanup_skips_non_session_files(tmp_path: Path) -> None:
    sess = tmp_path / "sessions"
    sess.mkdir()
    stray = sess / "notes.txt"
    stray.write_text("keep me")
    _make_old(stray, 40)

    stats = retention.cleanup_sessions(30, sess)

    assert stats["deleted_files"] == 0
    assert stray.exists()


def test_age_based_recording_cleanup(tmp_path: Path) -> None:
    rec = tmp_path / "recordings" / "w1"
    rec.mkdir(parents=True)
    old = rec / "old_rec"
    old.mkdir()
    (old / "summary.json").write_text("{}")
    new = rec / "new_rec"
    new.mkdir()
    (new / "summary.json").write_text("{}")
    _make_old(old, 40)

    stats = retention.cleanup_recordings(30, rec.parent)

    assert stats["deleted_dirs"] == 1
    assert not old.exists()
    assert new.exists()


def test_recording_age_uses_summary_timestamp(tmp_path: Path) -> None:
    """A recent dir mtime must not mask an old session_timestamp in summary.json."""
    rec = tmp_path / "recordings" / "w1"
    rec.mkdir(parents=True)
    session = rec / "sess"
    session.mkdir()
    (session / "summary.json").write_text(
        '{"session_timestamp": "20260501_120000_000"}'  # May 1 — >30 days old
    )
    # Dir mtime is recent — a git checkout / rsync rewrote it

    stats = retention.cleanup_recordings(30, rec.parent)

    assert stats["deleted_dirs"] == 1
    assert not session.exists()


def test_orphan_recording_dir_is_evictable(tmp_path: Path) -> None:
    """A crash-mid-save dir (timeline only, no summary.json) is still a candidate."""
    rec = tmp_path / "recordings" / "w1"
    rec.mkdir(parents=True)
    orphan = rec / "orphan"
    orphan.mkdir()
    (orphan / "timeline.json").write_text("[]")
    _make_old(orphan, 40)

    stats = retention.cleanup_recordings(30, rec.parent)

    assert stats["deleted_dirs"] == 1
    assert not orphan.exists()


def test_disk_cap_evicts_oldest_first(tmp_path: Path) -> None:
    rec = tmp_path / "recordings" / "w1"
    rec.mkdir(parents=True)
    a = rec / "a"
    a.mkdir()
    (a / "summary.json").write_text("x" * 10)
    b = rec / "b"
    b.mkdir()
    (b / "summary.json").write_text("y" * 10)
    _make_old(a, 10)  # 'a' is the oldest

    # ~1 byte cap — forces eviction of every session
    stats = retention.enforce_recordings_cap(0.000000001, rec.parent)

    assert stats["evicted_dirs"] >= 1
    assert not a.exists()


def test_disabled_policy_is_noop(tmp_path: Path) -> None:
    sess = tmp_path / "sessions"
    sess.mkdir()
    old = sess / "session_old.json"
    old.write_text("{}")
    _make_old(old, 40)

    stats = retention.cleanup_sessions(0, sess)

    assert stats["skipped"] is True
    assert old.exists()
