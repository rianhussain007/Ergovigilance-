"""Postgres graceful fallback (sell-readiness R1a: fresh compose builds crashed).

With DATABASE_URL set but PostgreSQL unreachable (or psycopg_pool
missing), boot and requests must continue in SQLite file mode — never
raise. Hermetic: unresolvable hostnames fail fast, no live PG needed.
"""

from __future__ import annotations

import sys

import pytest

from app.core import db_backend

BOGUS_URL = "postgresql://u:p@invalid-hostname-xyz:5432/db"


@pytest.fixture
def bogus_pg(monkeypatch):
    monkeypatch.setattr(db_backend, "_DATABASE_URL", BOGUS_URL)
    monkeypatch.setattr(db_backend, "_pg_pool", None)
    monkeypatch.setattr(db_backend, "_pg_unavailable_until", 0.0)
    return db_backend


def test_boot_completes_with_dead_database(bogus_pg):
    """The reported crash: init with DATABASE_URL set must not raise."""
    from app.core.database import init_local_database

    init_local_database()  # must not raise


def test_get_db_falls_back_to_sqlite(bogus_pg):
    with db_backend.get_db() as conn:
        row = conn.execute("SELECT 1").fetchone()
    assert row[0] == 1


def test_missing_pool_package_names_the_fix(monkeypatch):
    monkeypatch.setattr(db_backend, "_pg_pool", None)
    monkeypatch.setitem(sys.modules, "psycopg_pool", None)
    with pytest.raises(RuntimeError, match="psycopg_pool"):
        db_backend._get_pg_pool()


def test_backoff_avoids_repeat_probes(bogus_pg):
    assert db_backend._pg_reachable() is False
    assert db_backend._pg_unavailable_until > 0
    # Second call short-circuits on the backoff without touching the net.
    assert db_backend._pg_reachable() is False
