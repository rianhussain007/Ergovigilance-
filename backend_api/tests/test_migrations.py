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
    first_version = MIGRATIONS[0][0]
    conn.execute(f"PRAGMA user_version = {first_version}")
    conn.commit()

    applied = run_migrations(conn)
    assert applied == [v for v, _ in MIGRATIONS[1:]]
    assert current_version(conn) == MIGRATIONS[-1][0]
