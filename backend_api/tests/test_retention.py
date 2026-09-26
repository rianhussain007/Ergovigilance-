"""Tests for the data-retention service (P0 #4).

All tests operate on temporary directories only — never on real data.
"""

import os
import time
from datetime import datetime, timedelta, timezone
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


def test_audit_log_age_prune_and_disable(tmp_path: Path) -> None:
    """Audit JSONL files older than the policy age are deleted; 0 disables."""
    from app.core.audit_log import AuditLogger

    audit = AuditLogger(tmp_path / "audit_logs")
    old = audit.log_dir / "audit_2025-01-01.jsonl"
    fresh = audit.log_dir / "audit_recent.jsonl"
    old.write_text("{}")
    fresh.write_text("{}")
    _make_old(old, 400)

    deleted = audit.cleanup_old_logs(365)

    assert deleted == 1
    assert not old.exists()
    assert fresh.exists()

    ancient = audit.log_dir / "audit_2024-01-01.jsonl"
    ancient.write_text("{}")
    _make_old(ancient, 400)
    assert audit.cleanup_old_logs(0) == 0  # 0 disables — platform convention
    assert ancient.exists()


def test_alert_age_prune_and_disable() -> None:
    """Alert rows older than the policy age are deleted; 0 disables."""
    from app.core.database import (
        delete_alerts_older_than,
        get_connection,
        init_local_database,
        insert_alert,
    )

    init_local_database()
    old_created = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    try:
        insert_alert("ret-old", "high", "t", "m", "rule", "ACTIVE", created_at=old_created)
        insert_alert("ret-new", "low", "t", "m", "rule", "ACTIVE")

        deleted = delete_alerts_older_than(30)
        assert deleted >= 1

        with get_connection() as conn:
            ids = {
                r[0]
                for r in conn.execute(
                    "SELECT id FROM alerts WHERE id IN ('ret-old', 'ret-new')"
                ).fetchall()
            }
        assert ids == {"ret-new"}

        assert delete_alerts_older_than(0) == 0  # 0 disables
        with get_connection() as conn:
            still = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE id = 'ret-new'"
            ).fetchone()[0]
        assert still == 1
    finally:
        with get_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE id IN ('ret-old', 'ret-new')")
            conn.commit()


def test_run_retention_enforces_audit_and_alerts(tmp_path: Path, monkeypatch) -> None:
    """The unified pass prunes audit files and alert rows under one policy."""
    from app.core import audit_log
    from app.core.audit_log import AuditLogger
    from app.core.database import (
        get_connection,
        init_local_database,
        insert_alert,
    )

    init_local_database()
    # Deterministic policy: no admin override file, explicit env values.
    monkeypatch.setattr(retention, "_OVERRIDE_PATH", str(tmp_path / "retention.json"))
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.setenv("ALERT_RETENTION_DAYS", "30")

    audit = AuditLogger(tmp_path / "audit_logs")
    old_file = audit.log_dir / "audit_old.jsonl"
    old_file.write_text("{}")
    _make_old(old_file, 400)
    monkeypatch.setattr(audit_log, "audit_logger", audit)

    old_created = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    insert_alert("rrt-old", "high", "t", "m", "rule", "ACTIVE", created_at=old_created)
    insert_alert("rrt-new", "low", "t", "m", "rule", "ACTIVE")
    try:
        stats = retention.run_retention()

        assert stats["audit_log_retention_days"] == 365
        assert stats["alert_retention_days"] == 30
        assert stats["audit_logs"]["deleted_files"] == 1
        assert not old_file.exists()
        assert stats["alerts"]["deleted_rows"] >= 1
        with get_connection() as conn:
            ids = {
                r[0]
                for r in conn.execute(
                    "SELECT id FROM alerts WHERE id IN ('rrt-old', 'rrt-new')"
                ).fetchall()
            }
        assert ids == {"rrt-new"}
        # Conftest disables file retention — the rest of the pass must no-op.
        assert stats["sessions"]["skipped"] is True
        assert stats["recordings"]["skipped"] is True
    finally:
        with get_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE id IN ('rrt-old', 'rrt-new')")
            conn.commit()
