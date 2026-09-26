"""Tests for the lightweight versioned SQLite migration runner."""

from __future__ import annotations

import sqlite3

import pytest

from app.core import migrations as migrations_module
from app.core.migrations import MIGRATIONS, current_version, run_migrations

EXPECTED_TABLES = {
    "users",
    "workers",
    "alerts",
    "audit_log",
    "pilot_requests",
    "user_settings",
    "login_attempts",
}


@pytest.fixture
def conn(tmp_path):
    db = sqlite3.connect(tmp_path / "migrate.db")
    yield db
    db.close()


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def test_fresh_database_reaches_latest_version(conn):
    applied = run_migrations(conn)
    assert applied == [v for v, _ in MIGRATIONS]
    assert current_version(conn) == MIGRATIONS[-1][0]
    assert EXPECTED_TABLES <= _table_names(conn)


def test_reapplying_migrations_is_a_noop(conn):
    run_migrations(conn)
    version = current_version(conn)

    applied = run_migrations(conn)
    assert applied == []
    assert current_version(conn) == version
    assert EXPECTED_TABLES <= _table_names(conn)


def test_migrations_apply_incrementally(conn, monkeypatch):
    """An existing DB at version N only receives migrations > N."""
    first = MIGRATIONS[0]
    monkeypatch.setattr(migrations_module, "MIGRATIONS", [first])
    assert run_migrations(conn) == [first[0]]

    # Simulate a newer migration being added later.
    monkeypatch.setattr(migrations_module, "MIGRATIONS", MIGRATIONS)
    applied = run_migrations(conn)
    assert applied == [v for v, _ in MIGRATIONS[1:]]
    assert current_version(conn) == MIGRATIONS[-1][0]
    assert EXPECTED_TABLES <= _table_names(conn)


def test_upgrade_from_previous_version(conn):
    """A DB that claims version N only receives migrations > N."""
    first = MIGRATIONS[0]
    # A real v1 database has the v1 schema on disk (tables created before
    # versioning was introduced, or by migration 001 itself).
    for statement in first[1]:
        conn.execute(statement)
    conn.execute(f"PRAGMA user_version = {first[0]}")
    conn.commit()

    applied = run_migrations(conn)
    assert applied == [v for v, _ in MIGRATIONS[1:]]
    assert current_version(conn) == MIGRATIONS[-1][0]


def test_concurrent_fresh_boot_applies_once(tmp_path):
    """Concurrent first-boots (multi-worker fresh deploys) must not raise.

    Regression test for the k8s crash-loop note: two workers racing
    init-style startup on a fresh DB used to collide in DDL ("already
    exists"). BEGIN IMMEDIATE serializes them; the loser re-checks the
    version inside the transaction and skips.
    """
    import threading

    db = str(tmp_path / "race.db")
    barrier = threading.Barrier(4)
    errors: list = []

    def boot():
        try:
            barrier.wait(timeout=30)
            worker = sqlite3.connect(db, timeout=30)
            try:
                run_migrations(worker)
            finally:
                worker.close()
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            errors.append(exc)

    threads = [threading.Thread(target=boot) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    assert errors == []
    check = sqlite3.connect(db)
    try:
        assert current_version(check) == MIGRATIONS[-1][0]
        assert EXPECTED_TABLES <= _table_names(check)
    finally:
        check.close()
