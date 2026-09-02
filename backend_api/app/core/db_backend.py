"""Database backend abstraction — PostgreSQL (via psycopg3) or SQLite fallback.

When DATABASE_URL is set to a postgres:// or postgresql:// URL the backend
uses psycopg3 with a connection pool.  Otherwise it falls back to the
existing sqlite3-based local_auth.db.  This keeps local dev zero-config
while giving production a proper relational store.

Usage:
    from app.core.db_backend import get_db, is_postgres

    with get_db() as conn:
        cur = conn.execute("SELECT 1")
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Generator

# ---------------------------------------------------------------------------
# Detect PostgreSQL from DATABASE_URL
# ---------------------------------------------------------------------------

_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def is_postgres() -> bool:
    """Return True when the app should use PostgreSQL."""
    return _DATABASE_URL.lower().startswith(("postgresql://", "postgres://"))


# ---------------------------------------------------------------------------
# PostgreSQL adapter (psycopg3)
# ---------------------------------------------------------------------------

_pg_pool: Any = None  # lazily initialised
_pg_lock = threading.Lock()


def _get_pg_pool() -> Any:
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _pg_lock:
        if _pg_pool is not None:
            return _pg_pool
        try:
            import psycopg  # psycopg3
        except ImportError:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg is not installed.  "
                "Run: pip install 'psycopg[binary]>=3.1,<4'"
            )
        _pg_pool = psycopg.ConnectionPool(
            conninfo=_DATABASE_URL,
            min_size=2,
            max_size=10,
            kwargs={"autocommit": False},
        )
        return _pg_pool


class PgRow:
    """Thin wrapper to mimic sqlite3.Row attribute access on psycopg tuples."""

    __slots__ = ("_cols", "_vals")

    def __init__(self, columns: tuple[str, ...], values: tuple[Any, ...]):
        object.__setattr__(self, "_cols", columns)
        object.__setattr__(self, "_vals", values)

    def __getattr__(self, name: str) -> Any:
        cols = object.__getattribute__(self, "_cols")
        vals = object.__getattribute__(self, "_vals")
        try:
            idx = cols.index(name)
        except ValueError:
            raise AttributeError(name)
        return vals[idx]

    def __getitem__(self, key: int | str) -> Any:
        cols = object.__getattribute__(self, "_cols")
        vals = object.__getattribute__(self, "_vals")
        if isinstance(key, int):
            return vals[key]
        return self.__getattr__(key)

    def __iter__(self):
        return iter(object.__getattribute__(self, "_vals"))

    def __contains__(self, item):
        return item in object.__getattribute__(self, "_vals")

    def __len__(self):
        return len(object.__getattribute__(self, "_vals"))

    def keys(self):
        return list(object.__getattribute__(self, "_cols"))


@contextmanager
def _pg_cursor() -> Generator:
    """Yield a cursor from the connection pool, auto-committing on success."""
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def _pg_connection() -> Generator:
    """Yield a context manager that behaves like a sqlite3 connection.

    The returned object provides:
    - execute(sql, params) -> cursor with .fetchone / .fetchall
    - row_factory attribute (accepted but ignored — rows are PgRow-wrapped)
    - commit() / rollback()
    """
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        wrapper = _PgConnectionWrapper(conn)
        yield wrapper
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


class _PgConnectionWrapper:
    """Wraps a psycopg connection to look like sqlite3.Connection."""

    def __init__(self, conn: Any):
        self._conn = conn
        self.row_factory = None  # accepted but unused

    def execute(self, sql: str, params: tuple | list = ()) -> "_PgCursorWrapper":
        # Convert ?-style placeholders to psycopg %s-style
        adapted = sql.replace("?", "%s")
        cur = self._conn.cursor()
        cur.execute(adapted, params)
        return _PgCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


class _PgCursorWrapper:
    """Wraps a psycopg cursor with fetchone / fetchall returning PgRow objects."""

    def __init__(self, cur: Any):
        self._cur = cur

    @property
    def lastrowid(self) -> int | None:
        # psycopg3: cur.fetchone() after INSERT ... RETURNING or cur.pgresult
        return None  # callers that need lastrowid should use RETURNING

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def fetchone(self) -> PgRow | None:
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = tuple(d.name for d in self._cur.description) if self._cur.description else ()
        return PgRow(cols, row)

    def fetchall(self) -> list[PgRow]:
        rows = self._cur.fetchall()
        cols = tuple(d.name for d in self._cur.description) if self._cur.description else ()
        return [PgRow(cols, r) for r in rows]


# ---------------------------------------------------------------------------
# SQLite backend (existing behaviour, unchanged)
# ---------------------------------------------------------------------------

from pathlib import Path

try:
    from app.core.config import settings
    if settings.AUTH_DB_PATH:
        _SQLITE_DB_PATH = Path(settings.AUTH_DB_PATH)
    else:
        try:
            ROOT = Path(__file__).resolve().parents[3]
            _SQLITE_DB_PATH = ROOT / "backend_api" / "local_auth.db"
        except (IndexError, FileNotFoundError):
            _SQLITE_DB_PATH = Path("/data/local_auth.db")
except Exception:
    _SQLITE_DB_PATH = Path("local_auth.db")


@contextmanager
def _sqlite_connection() -> Generator:
    _SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@contextmanager
def get_db() -> Generator:
    """Yield a database connection (PostgreSQL or SQLite).

    The returned connection behaves uniformly:
        with get_db() as conn:
            row = conn.execute("SELECT ...").fetchone()
            val = row["column"]  # or row[0]
    """
    if is_postgres():
        with _pg_connection() as conn:
            yield conn
    else:
        with _sqlite_connection() as conn:
            yield conn


def ensure_schema() -> None:
    """Create tables if they don't exist (PostgreSQL only — SQLite uses migrations)."""
    if not is_postgres():
        return

    DDL = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('operator','supervisor','safety_mgr','admin')),
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS workers (
        worker_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        shift TEXT NOT NULL
    );

    ALTER TABLE workers ADD COLUMN IF NOT EXISTS identity_mode TEXT DEFAULT 'off';
    ALTER TABLE workers ADD COLUMN IF NOT EXISTS consent_status TEXT DEFAULT 'pending';
    CREATE TABLE IF NOT EXISTS consent_records (
        worker_id TEXT PRIMARY KEY,
        name TEXT,
        department TEXT,
        status TEXT DEFAULT 'pending',
        consent_date TEXT,
        consent_expiry TEXT,
        consent_version TEXT DEFAULT '1.0',
        purposes TEXT DEFAULT '[]',
        data_categories TEXT DEFAULT '[]',
        retention_days INTEGER DEFAULT 90,
        withdrawal_date TEXT,
        updated_at TEXT
    );
    """

    with get_db() as conn:
        cur = conn._conn.cursor() if hasattr(conn, '_conn') else conn
        for stmt in DDL.split(';'):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass
        if hasattr(conn, '_conn'):
            conn._conn.commit()
        else:
            conn.commit()
