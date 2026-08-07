"""Lightweight versioned migrations for the local SQLite store.

Each file in ``migrations/`` is a numbered SQL script (``NNN_name.sql``).
``run_migrations`` applies every script whose version is greater than the
database's current ``PRAGMA user_version``, in ascending order, each inside
its own transaction, then advances ``user_version``.

Rules for contributors:

- Never edit an applied migration file. Existing databases track their applied
  version, so editing file ``001`` would do nothing for them and silently
  diverge fresh installs.
- Add schema changes as a new numbered file (``002_...sql``, ``003_...sql``).
  Only SQLite DDL/DML is supported (no triggers with embedded semicolons).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _load_migrations() -> list[tuple[int, list[str]]]:
    """Load ``(version, [statements])`` pairs from numbered .sql files."""
    migrations: list[tuple[int, list[str]]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = re.match(r"(\d+)", path.name)
        if not match:
            logger.warning("Ignoring migration file with non-numeric prefix: %s", path.name)
            continue
        version = int(match.group(1))
        raw = path.read_text(encoding="utf-8")
        statements = [
            stmt.strip()
            for stmt in re.split(r";\s*(?:\n|$)", raw)
            if stmt.strip()
        ]
        if not statements:
            logger.warning("Ignoring empty migration file: %s", path.name)
            continue
        migrations.append((version, statements))
    return sorted(migrations, key=lambda m: m[0])


MIGRATIONS: list[tuple[int, list[str]]] = _load_migrations()


def current_version(conn: sqlite3.Connection) -> int:
    """Read the database's applied schema version (PRAGMA user_version)."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def run_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply pending migrations, returning the versions applied in this call.

    Each migration runs inside an explicit transaction (``BEGIN``…
    ``COMMIT``/``ROLLBACK``) so a partial failure leaves the database on its
    previous version. An explicit ``BEGIN`` is required because Python's
    sqlite3 autocommits DDL statements when no transaction is open.
    """
    applied: list[int] = []
    version = current_version(conn)
    for migration_version, statements in MIGRATIONS:
        if migration_version <= version:
            continue
        conn.execute("BEGIN")
        try:
            for statement in statements:
                conn.execute(statement)
            # user_version cannot be bound as a parameter; migration_version is
            # an int parsed from a filename, so this is injection-safe.
            conn.execute(f"PRAGMA user_version = {migration_version}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        applied.append(migration_version)
        logger.info("Applied database migration %d (%d statement(s))", migration_version, len(statements))
    return applied
