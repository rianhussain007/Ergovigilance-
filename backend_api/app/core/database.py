"""Small local SQLite store for auth users, worker seed records, and alerts."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.core.config import settings
from app.core.migrations import run_migrations
from app.core.security import hash_password, verify_password


# For container compatibility: use relative paths inside /app
if settings.AUTH_DB_PATH:
    DB_PATH = Path(settings.AUTH_DB_PATH)
    # Put credentials file in same directory as DB
    CREDENTIALS_PATH = DB_PATH.parent / "SEED_CREDENTIALS.local.txt"
else:
    try:
        ROOT = Path(__file__).resolve().parents[3]
        DB_PATH = ROOT / "backend_api" / "local_auth.db"
        CREDENTIALS_PATH = ROOT / "backend_api" / "SEED_CREDENTIALS.local.txt"
    except (IndexError, FileNotFoundError):
        # Container fallback
        DB_PATH = Path("/data/local_auth.db")
        CREDENTIALS_PATH = Path("/data/SEED_CREDENTIALS.local.txt")

# Ensure parent directory exists before writing credentials
CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)

SEED_USERS = [
    ("operator@example.local", "OperatorPass123!", "operator"),
    ("supervisor@example.local", "SupervisorPass123!", "supervisor"),
    ("safety@example.local", "SafetyPass123!", "safety_mgr"),
    ("admin@example.local", "AdminPass123!", "admin"),
]

SEED_WORKERS = [
    ("worker-001", "EMP-001", "Asha Patel", "Assembly", "Day"),
    ("worker-002", "EMP-002", "Rohan Mehta", "Inspection", "Evening"),
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_local_database() -> None:
    """Apply schema migrations and seed the database.

    Schema is versioned via ``app.core.migrations`` (SQLite ``PRAGMA
    user_version``); seeding and the credentials file remain idempotent.
    """
    with get_connection() as conn:
        run_migrations(conn)
        _seed_users(conn, SEED_USERS)
        _seed_workers(conn, SEED_WORKERS)
        conn.commit()
    _write_local_credentials_file()


def insert_pilot_request(
    company_name: str,
    contact_name: str,
    email: str,
    role: str,
    num_stations: str | None,
    message: str | None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO pilot_requests (company_name, contact_name, email, role, num_stations, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (company_name, contact_name, email, role, num_stations or "", message or "", now),
        )
        conn.commit()
        return cur.lastrowid


def load_pilot_requests() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pilot_requests ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_settings(user_id: int) -> dict:
    """Get user settings from database. Returns empty dict if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT settings_json FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if row is None:
            return {}
        import json
        return json.loads(row["settings_json"])


def save_user_settings(user_id: int, settings_dict: dict) -> None:
    """Save or update user settings."""
    import json
    now = datetime.now(timezone.utc).isoformat()
    settings_json = json.dumps(settings_dict)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, settings_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = excluded.updated_at
            """,
            (user_id, settings_json, now)
        )
        conn.commit()


def _seed_users(conn: sqlite3.Connection, seed_users: Iterable[tuple[str, str, str]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for email, password, role in seed_users:
        existing = conn.execute("SELECT id, password_hash, role FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO users (email, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (email, hash_password(password), role, now),
            )
            continue

        password_matches = verify_password(password, existing["password_hash"])
        role_matches = existing["role"] == role
        if not password_matches or not role_matches:
            conn.execute(
                "UPDATE users SET email = ?, password_hash = ?, role = ? WHERE id = ?",
                (email, hash_password(password), role, existing["id"]),
            )


def _seed_workers(conn: sqlite3.Connection, seed_workers: Iterable[tuple[str, str, str, str, str]]) -> None:
    for worker_id, employee_id, name, department, shift in seed_workers:
        conn.execute(
            """
            INSERT INTO workers (worker_id, employee_id, name, department, shift)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
                employee_id = excluded.employee_id,
                name = excluded.name,
                department = excluded.department,
                shift = excluded.shift
            """,
            (worker_id, employee_id, name, department, shift),
        )


def _write_local_credentials_file() -> None:
    if CREDENTIALS_PATH.exists():
        return
    lines = [
        "Local seed credentials for ErgoVigilance auth testing",
        "Do not commit this file.",
        "",
        "operator@example.local / OperatorPass123! / operator",
        "supervisor@example.local / SupervisorPass123! / supervisor",
        "safety@example.local / SafetyPass123! / safety_mgr",
        "admin@example.local / AdminPass123! / admin",
        "",
        "Seed workers:",
        "worker-001 / EMP-001 / Asha Patel / Assembly / Day",
        "worker-002 / EMP-002 / Rohan Mehta / Inspection / Evening",
        "",
    ]
    CREDENTIALS_PATH.write_text("\n".join(lines), encoding="utf-8")


LOGIN_ATTEMPTS_RETENTION_SECONDS = 24 * 60 * 60


def record_login_attempt(email: str, ip: str, success: bool) -> None:
    """Record a login attempt for brute-force / lockout tracking.

    Old rows are pruned opportunistically so the table stays bounded.
    """
    now = datetime.now(timezone.utc).isoformat()
    cutoff = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - LOGIN_ATTEMPTS_RETENTION_SECONDS, tz=timezone.utc
    ).isoformat()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM login_attempts WHERE created_at < ?",
            (cutoff,),
        )
        conn.execute(
            "INSERT INTO login_attempts (email, ip, success, created_at) VALUES (?, ?, ?, ?)",
            (email, ip, 1 if success else 0, now),
        )
        conn.commit()


def count_recent_login_failures(
    email: str | None = None,
    ip: str | None = None,
    window_seconds: int = 900,
) -> int:
    """Count failed login attempts within a rolling window, filtered by email and/or IP."""
    cutoff = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - window_seconds, tz=timezone.utc
    ).isoformat()
    conditions = ["success = 0", "created_at >= ?"]
    params: list[str] = [cutoff]
    if email:
        conditions.append("lower(email) = lower(?)")
        params.append(email)
    if ip:
        conditions.append("ip = ?")
        params.append(ip)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM login_attempts WHERE {' AND '.join(conditions)}",
            params,
        ).fetchone()
        return int(row["cnt"])


def clear_login_failures(email: str | None = None, ip: str | None = None) -> None:
    """Delete recorded login failures for the given email and/or IP."""
    conditions: list[str] = []
    params: list[str] = []
    if email:
        conditions.append("lower(email) = lower(?)")
        params.append(email)
    if ip:
        conditions.append("ip = ?")
        params.append(ip)
    if not conditions:
        return
    with get_connection() as conn:
        conn.execute(
            f"DELETE FROM login_attempts WHERE success = 0 AND {' AND '.join(conditions)}",
            params,
        )
        conn.commit()


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_workers() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT worker_id, employee_id, name, department, shift FROM workers ORDER BY worker_id").fetchall()


def get_worker(worker_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT worker_id, employee_id, name, department, shift FROM workers WHERE worker_id = ?", (worker_id,)).fetchone()


def get_next_worker_id() -> str:
    with get_connection() as conn:
        rows = conn.execute("SELECT worker_id FROM workers ORDER BY worker_id").fetchall()
        max_num = 0
        for row in rows:
            wid = row["worker_id"]
            if wid.startswith("worker-"):
                try:
                    num = int(wid.split("-", 1)[1])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f"worker-{max_num + 1:03d}"


def insert_worker(employee_id: str, name: str, department: str, shift: str) -> str:
    worker_id = get_next_worker_id()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO workers (worker_id, employee_id, name, department, shift) VALUES (?, ?, ?, ?, ?)",
            (worker_id, employee_id, name, department, shift),
        )
        conn.commit()
    return worker_id


def update_worker(worker_id: str, name: str, department: str, shift: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE workers SET name = ?, department = ?, shift = ? WHERE worker_id = ?",
            (name, department, shift, worker_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_worker(worker_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM workers WHERE worker_id = ?", (worker_id,))
        conn.commit()
        return cur.rowcount > 0


def worker_has_sessions(worker_id: str) -> bool:
    """Check if any alerts or session files reference this worker."""
    import json
    from pathlib import Path

    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM alerts WHERE worker_id = ?", (worker_id,)
        ).fetchone()
        if row and row["cnt"] > 0:
            return True

    sessions_dir = Path(__file__).resolve().parents[3] / "outputs" / "sessions"
    if sessions_dir.is_dir():
        for f in sessions_dir.iterdir():
            if f.suffix == ".json":
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if data.get("worker_id") == worker_id:
                        return True
                except (json.JSONDecodeError, OSError):
                    pass
    return False


def count_workers() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM workers").fetchone()
        return int(row["count"])


def count_users() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        return int(row["count"])


def count_users_by_role() -> dict[str, int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT role, COUNT(*) AS count FROM users GROUP BY role ORDER BY role").fetchall()
        return {row["role"]: int(row["count"]) for row in rows}


def database_is_healthy() -> bool:
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


# ── Alert persistence helpers ────────────────────────────────────────────


def insert_alert(
    alert_id: str,
    severity: str,
    title: str,
    message: str,
    trigger_rule: str,
    state: str,
    session_id: str = "",
    worker_id: str = "",
    frame_number: int = 0,
    confidence: float = 0.0,
    requires_ack: bool = False,
    created_at: str = "",
    updated_at: str = "",
) -> None:
    """Insert a new alert row into the alerts table."""
    now = created_at or datetime.now(timezone.utc).isoformat()
    upd = updated_at or now
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO alerts
               (id, severity, title, message, trigger_rule, state,
                session_id, worker_id, frame_number, confidence, requires_ack,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert_id, severity, title, message, trigger_rule, state,
             session_id, worker_id, frame_number, int(requires_ack), now, now, upd),
        )
        conn.commit()


def update_alert_state(alert_id: str, state: str, updated_at: str = "") -> None:
    """Update an alert's state (ACKNOWLEDGED or RESOLVED)."""
    upd = updated_at or datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE alerts SET state = ?, updated_at = ? WHERE id = ?",
            (state, upd, alert_id),
        )
        conn.commit()


def load_active_alerts() -> list[dict]:
    """Load all ACTIVE alerts from the database."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE state = 'ACTIVE' ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_alerts_for_worker(worker_id: str) -> int:
    """Delete all alert rows for a worker (used by the privacy wipe endpoint)."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM alerts WHERE worker_id = ?", (worker_id,))
        conn.commit()
        return cur.rowcount


def load_alert_history() -> list[dict]:
    """Load all ACKNOWLEDGED and RESOLVED alerts from the database."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE state IN ('ACKNOWLEDGED', 'RESOLVED') ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def insert_audit_log(
    id: str,
    actor_id: int | None,
    actor_email: str,
    actor_role: str,
    action_type: str,
    target_type: str | None,
    target_id: str | None,
    timestamp: str,
    details: str | None,
) -> None:
    """Insert a new audit log entry into the audit_log table."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO audit_log
               (id, actor_id, actor_email, actor_role, action_type, target_type, target_id, timestamp, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (id, actor_id, actor_email, actor_role, action_type, target_type, target_id, timestamp, details),
        )
        conn.commit()


def load_audit_log(
    action_type: str | None = None,
    actor_email: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Load audit log entries, most recent first, with optional filters."""
    query = "SELECT * FROM audit_log"
    params = []
    conditions = []

    if action_type:
        conditions.append("action_type = ?")
        params.append(action_type)
    if actor_email:
        conditions.append("actor_email = ?")
        params.append(actor_email)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
