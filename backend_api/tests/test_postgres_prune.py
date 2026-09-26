"""Tests for Postgres telemetry age-pruning (P0-6 residual).

``prune_telemetry`` deletes per-frame timeline rows and then session summary
rows older than the policy horizon. 0 disables, an unavailable Postgres is
reported as skipped, and failures never raise (file mode is the fallback).
The SQL itself is exercised with a fake connection/mock cursor — no live
Postgres is needed for the unit tests.
"""

from __future__ import annotations

from app.core import postgres


class _FakeCursor:
    """Minimal cursor double: records SQL, returns a settable rowcount."""

    def __init__(self, rowcounts: list[int]):
        self._rowcounts = list(rowcounts)
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql, params))
        self.rowcount = self._rowcounts.pop(0) if self._rowcounts else 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, rowcounts: list[int]):
        self.cursor_obj = _FakeCursor(rowcounts)
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_prune_disabled_at_zero(monkeypatch):
    monkeypatch.setattr(postgres, "get_connection", lambda: _FakeConn([0, 0]))
    stats = postgres.prune_telemetry(0)
    assert stats == {"skipped": True, "deleted_frames": 0, "deleted_sessions": 0}


def test_prune_skipped_when_pg_unavailable(monkeypatch):
    monkeypatch.setattr(postgres, "get_connection", lambda: None)
    stats = postgres.prune_telemetry(30)
    assert stats["skipped"] is True
    assert stats["reason"] == "pg_unavailable"


def test_prune_deletes_frames_then_sessions(monkeypatch):
    conn = _FakeConn([1500, 12])
    monkeypatch.setattr(postgres, "get_connection", lambda: conn)
    stats = postgres.prune_telemetry(90)

    assert stats == {"skipped": False, "deleted_frames": 1500, "deleted_sessions": 12}
    assert len(conn.cursor_obj.executed) == 2
    frames_sql, sessions_sql = conn.cursor_obj.executed
    assert "DELETE FROM ergo_session_frames" in frames_sql[0]
    assert "DELETE FROM ergo_sessions" in sessions_sql[0]
    # Frames are deleted BEFORE sessions (children before parents).
    assert conn.cursor_obj.executed.index(frames_sql) < conn.cursor_obj.executed.index(sessions_sql)
    # A cutoff parameter is bound on both statements.
    assert len(frames_sql[1]) == 1 and len(sessions_sql[1]) == 1
    assert conn.committed == 1


def test_prune_failure_does_not_raise(monkeypatch):
    class _BoomConn:
        def cursor(self):
            raise RuntimeError("db gone")

    monkeypatch.setattr(postgres, "get_connection", lambda: _BoomConn())
    stats = postgres.prune_telemetry(90)
    assert stats["skipped"] is False
    assert "error" in stats
    assert stats["deleted_frames"] == 0 and stats["deleted_sessions"] == 0


def test_prune_wired_into_retention_pass(monkeypatch):
    """run_retention() must apply the DB telemetry policy."""
    from app.services import retention

    cfg = retention.retention_config()
    assert "db_telemetry_retention_days" in cfg

    called = {}

    def _fake_prune(days):
        called["days"] = days
        return {"skipped": False, "deleted_frames": 0, "deleted_sessions": 0}

    monkeypatch.setattr("app.core.postgres.prune_telemetry", _fake_prune)
    stats = retention.run_retention()
    assert called["days"] == cfg["db_telemetry_retention_days"]
    assert stats["db_telemetry"] == {"skipped": False, "deleted_frames": 0, "deleted_sessions": 0}
