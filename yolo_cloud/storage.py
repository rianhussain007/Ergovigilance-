"""YOLO Cloud Core — PostgreSQL Storage.

Persistent storage for cloud sessions, cameras, and alerts.
When DATABASE_URL is configured, data is stored in PostgreSQL.
When unset, falls back to JSON files (current behavior).

Tables:
  - cloud_cameras     — camera configurations (id, name, url, tenant)
  - cloud_sessions    — session summaries (JSONB payload)
  - cloud_alerts      — alert history
  - cloud_api_keys    — API key authentication
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_conn_lock = threading.Lock()
_conn = None
_conn_error_at: float = 0.0
_RETRY_BACKOFF_S = 30.0


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def pg_enabled() -> bool:
    return bool(_database_url())


def _connect():
    import psycopg
    return psycopg.connect(_database_url(), connect_timeout=5)


def get_connection():
    global _conn, _conn_error_at
    if _conn is not None:
        try:
            _conn.execute("SELECT 1")
            return _conn
        except Exception:
            logger.warning("Cloud DB connection lost — reconnecting")
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
    if _conn_error_at and time.time() - _conn_error_at < _RETRY_BACKOFF_S:
        return None
    with _conn_lock:
        if _conn is None:
            try:
                _conn = _connect()
                _conn_error_at = 0.0
                logger.info("Connected to cloud PostgreSQL storage")
            except Exception as exc:
                _conn_error_at = time.time()
                logger.warning("Cloud Postgres unavailable (%s) — file mode", exc)
                return None
        return _conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cloud_cameras (
    camera_id   TEXT PRIMARY KEY,
    camera_name TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    is_active   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cloud_sessions (
    session_id  TEXT PRIMARY KEY,
    camera_id   TEXT NOT NULL REFERENCES cloud_cameras(camera_id),
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    payload     JSONB NOT NULL DEFAULT '{}',
    start_time  TIMESTAMPTZ NOT NULL,
    end_time    TIMESTAMPTZ,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cloud_alerts (
    alert_id    TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    camera_id   TEXT NOT NULL,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    severity    TEXT NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    risk_score  REAL NOT NULL DEFAULT 0,
    task        TEXT NOT NULL DEFAULT '',
    track_id    INTEGER NOT NULL DEFAULT 0,
    timestamp   TIMESTAMPTZ NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cloud_api_keys (
    key_id      TEXT PRIMARY KEY,
    api_key     TEXT NOT NULL UNIQUE,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    name        TEXT NOT NULL DEFAULT '',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cloud_sessions_camera ON cloud_sessions(camera_id);
CREATE INDEX IF NOT EXISTS idx_cloud_sessions_tenant ON cloud_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cloud_sessions_time ON cloud_sessions(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_alerts_camera ON cloud_alerts(camera_id);
CREATE INDEX IF NOT EXISTS idx_cloud_alerts_tenant ON cloud_alerts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cloud_alerts_time ON cloud_alerts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_api_keys_key ON cloud_api_keys(api_key);

CREATE TABLE IF NOT EXISTS cloud_webhooks (
    webhook_id  TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    webhook_url TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    events      TEXT[] NOT NULL DEFAULT ARRAY['alert.fired'],
    secret      TEXT NOT NULL DEFAULT '',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_webhooks_tenant ON cloud_webhooks(tenant_id);
"""


def init_schema() -> bool:
    """Create tables if they don't exist. Returns True on success."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        conn.execute(SCHEMA_SQL)
        conn.commit()
        logger.info("Cloud PostgreSQL schema initialized")
        return True
    except Exception as exc:
        logger.warning("Cloud schema init failed: %s", exc)
        return False


def _json_safe(value):
    import math
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


# ── Camera Operations ────────────────────────────────────────────────────────


def upsert_camera(camera_id: str, name: str, url: str, tenant_id: str = "default") -> bool:
    conn = get_connection()
    if conn is None:
        return False
    try:
        conn.execute(
            """INSERT INTO cloud_cameras (camera_id, camera_name, url, tenant_id, is_active, updated_at)
               VALUES (%s, %s, %s, %s, TRUE, NOW())
               ON CONFLICT (camera_id) DO UPDATE SET
                 camera_name = EXCLUDED.camera_name,
                 url = EXCLUDED.url,
                 is_active = TRUE,
                 updated_at = NOW()""",
            (camera_id, name, url, tenant_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to upsert camera %s: %s", camera_id, exc)
        return False


def set_camera_active(camera_id: str, active: bool) -> bool:
    conn = get_connection()
    if conn is None:
        return False
    try:
        conn.execute(
            "UPDATE cloud_cameras SET is_active = %s, updated_at = NOW() WHERE camera_id = %s",
            (active, camera_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to update camera %s: %s", camera_id, exc)
        return False


def delete_camera(camera_id: str) -> bool:
    conn = get_connection()
    if conn is None:
        return False
    try:
        conn.execute("DELETE FROM cloud_cameras WHERE camera_id = %s", (camera_id,))
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to delete camera %s: %s", camera_id, exc)
        return False


def get_cameras(tenant_id: str = "default") -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT camera_id, camera_name, url, is_active, created_at FROM cloud_cameras WHERE tenant_id = %s ORDER BY created_at",
            (tenant_id,),
        ).fetchall()
        return [
            {
                "camera_id": r[0],
                "camera_name": r[1],
                "url": r[2],
                "is_active": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Failed to get cameras: %s", exc)
        return []


# ── Session Operations ───────────────────────────────────────────────────────


def save_session(session_data: dict, tenant_id: str = "default") -> bool:
    conn = get_connection()
    if conn is None:
        return False
    try:
        safe_data = _json_safe(session_data)
        conn.execute(
            """INSERT INTO cloud_sessions (session_id, camera_id, tenant_id, payload, start_time, end_time, is_active)
               VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
               ON CONFLICT (session_id) DO UPDATE SET
                 payload = EXCLUDED.payload,
                 end_time = EXCLUDED.end_time,
                 is_active = EXCLUDED.is_active""",
            (
                safe_data.get("session_id", ""),
                safe_data.get("camera_id", ""),
                tenant_id,
                json.dumps(safe_data),
                safe_data.get("start_time"),
                safe_data.get("end_time"),
                safe_data.get("is_active", True),
            ),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to save session %s: %s", session_data.get("session_id"), exc)
        return False


def get_sessions(limit: int = 50, tenant_id: str = "default") -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT payload FROM cloud_sessions WHERE tenant_id = %s ORDER BY start_time DESC LIMIT %s",
            (tenant_id, limit),
        ).fetchall()
        return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows]
    except Exception as exc:
        logger.warning("Failed to get sessions: %s", exc)
        return []


# ── Alert Operations ─────────────────────────────────────────────────────────


def save_alert(alert_data: dict, tenant_id: str = "default") -> bool:
    conn = get_connection()
    if conn is None:
        return False
    try:
        conn.execute(
            """INSERT INTO cloud_alerts (alert_id, session_id, camera_id, tenant_id, severity, message, risk_score, task, track_id, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (alert_id) DO NOTHING""",
            (
                alert_data.get("alert_id", ""),
                alert_data.get("session_id", ""),
                alert_data.get("camera_id", ""),
                tenant_id,
                alert_data.get("severity", "LOW"),
                alert_data.get("message", ""),
                alert_data.get("risk_score", 0),
                alert_data.get("task", ""),
                alert_data.get("track_id", 0),
                alert_data.get("timestamp"),
            ),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to save alert: %s", exc)
        return False


def get_alerts(limit: int = 100, tenant_id: str = "default") -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """SELECT alert_id, session_id, camera_id, severity, message, risk_score, task, track_id, timestamp, acknowledged
               FROM cloud_alerts WHERE tenant_id = %s ORDER BY timestamp DESC LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()
        return [
            {
                "alert_id": r[0],
                "session_id": r[1],
                "camera_id": r[2],
                "severity": r[3],
                "message": r[4],
                "risk_score": r[5],
                "task": r[6],
                "track_id": r[7],
                "timestamp": r[8].isoformat() if r[8] else None,
                "acknowledged": r[9],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Failed to get alerts: %s", exc)
        return []


# ── API Key Operations ───────────────────────────────────────────────────────


def validate_api_key(api_key: str) -> Optional[dict]:
    """Validate an API key. Returns tenant info if valid, None if invalid."""
    conn = get_connection()
    if conn is None:
        # No DB — allow all requests (dev mode)
        return {"tenant_id": "default", "name": "dev-mode"}
    try:
        row = conn.execute(
            """SELECT key_id, tenant_id, name FROM cloud_api_keys
               WHERE api_key = %s AND is_active = TRUE""",
            (api_key,),
        ).fetchone()
        if row:
            # Update last_used
            conn.execute(
                "UPDATE cloud_api_keys SET last_used = NOW() WHERE api_key = %s",
                (api_key,),
            )
            conn.commit()
            return {"key_id": row[0], "tenant_id": row[1], "name": row[2]}
        return None
    except Exception as exc:
        logger.warning("API key validation failed: %s", exc)
        return None


def create_api_key(api_key: str, tenant_id: str = "default", name: str = "") -> bool:
    import uuid
    conn = get_connection()
    if conn is None:
        return False
    try:
        key_id = str(uuid.uuid4())[:8]
        conn.execute(
            """INSERT INTO cloud_api_keys (key_id, api_key, tenant_id, name)
               VALUES (%s, %s, %s, %s)""",
            (key_id, api_key, tenant_id, name),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to create API key: %s", exc)
        return False


# ── Data Retention ───────────────────────────────────────────────────────────


def cleanup_old_sessions(retention_days: int = 30, tenant_id: str = "default") -> int:
    """Delete sessions older than retention_days. Returns count deleted."""
    conn = get_connection()
    if conn is None:
        return 0
    try:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = conn.execute(
            "DELETE FROM cloud_sessions WHERE tenant_id = %s AND start_time < %s",
            (tenant_id, cutoff.isoformat()),
        )
        deleted = result.rowcount if hasattr(result, 'rowcount') else 0
        conn.commit()
        if deleted > 0:
            logger.info("Retention cleanup: deleted %d sessions older than %d days", deleted, retention_days)
        return deleted
    except Exception as exc:
        logger.warning("Retention cleanup failed: %s", exc)
        return 0


def cleanup_old_alerts(retention_days: int = 90, tenant_id: str = "default") -> int:
    """Delete alerts older than retention_days. Returns count deleted."""
    conn = get_connection()
    if conn is None:
        return 0
    try:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = conn.execute(
            "DELETE FROM cloud_alerts WHERE tenant_id = %s AND timestamp < %s",
            (tenant_id, cutoff.isoformat()),
        )
        deleted = result.rowcount if hasattr(result, 'rowcount') else 0
        conn.commit()
        if deleted > 0:
            logger.info("Retention cleanup: deleted %d alerts older than %d days", deleted, retention_days)
        return deleted
    except Exception as exc:
        logger.warning("Alert retention cleanup failed: %s", exc)
        return 0


def get_storage_stats(tenant_id: str = "default") -> dict:
    """Get storage statistics for a tenant."""
    conn = get_connection()
    if conn is None:
        return {"mode": "file"}
    try:
        sessions = conn.execute(
            "SELECT COUNT(*) FROM cloud_sessions WHERE tenant_id = %s",
            (tenant_id,),
        ).fetchone()[0]
        alerts = conn.execute(
            "SELECT COUNT(*) FROM cloud_alerts WHERE tenant_id = %s",
            (tenant_id,),
        ).fetchone()[0]
        cameras = conn.execute(
            "SELECT COUNT(*) FROM cloud_cameras WHERE tenant_id = %s",
            (tenant_id,),
        ).fetchone()[0]
        return {
            "mode": "postgresql",
            "sessions": sessions,
            "alerts": alerts,
            "cameras": cameras,
        }
    except Exception as exc:
        logger.warning("Failed to get storage stats: %s", exc)
        return {"mode": "error"}
