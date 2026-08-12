"""PostgreSQL / TimescaleDB telemetry store (Tier 1).

Additive layer: when ``DATABASE_URL`` is set the session summaries and
per-frame timeline rows are mirrored into Postgres and reads prefer the DB
(fast indexed queries for analytics / predictive ML training). When unset
or unreachable, the app behaves exactly as before (JSON files / SQLite) —
this module never raises and never blocks startup.

Design:
  - ``ergo_sessions``      — one row per session summary (payload kept as
                             JSONB so the file-shaped dict round-trips losslessly)
  - ``ergo_session_frames`` — one row per timeline entry (time-series; created
                             as a TimescaleDB hypertable when PG_TIMESCALEDB=1)
  - All access is lazy + guarded; a broken DB falls back to file mode.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def _json_safe(value):
    """Recursively replace NaN/Infinity with None (Postgres JSONB rejects them).

    Old session files contain NaN sentinels for unavailable features
    (e.g. avg_trunk_flexion: NaN) which ``json.dumps`` would emit as the
    literal ``NaN`` token — invalid for JSONB. Converted to null instead so
    the row round-trips and downstream consumers keep their NaN handling.
    """
    import math
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


_conn_lock = threading.Lock()
_conn = None
_conn_error_at: float = 0.0
# Back off reconnect attempts after a failure so a down DB can't stall requests.
_RETRY_BACKOFF_S = 30.0


def database_url() -> str:
    from app.core.config import settings
    return (settings.DATABASE_URL or "").strip()


def pg_enabled() -> bool:
    """True when DATABASE_URL is configured (connection lazily verified)."""
    return bool(database_url())


def _connect():
    """Create a new psycopg connection (imported lazily so a minimal install
    without psycopg still runs in file mode)."""
    import psycopg
    return psycopg.connect(database_url(), connect_timeout=5)


def get_connection():
    """Return a shared connection, reconnecting after failures with backoff."""
    global _conn, _conn_error_at
    if _conn is not None:
        try:
            _conn.execute("SELECT 1")
            return _conn
        except Exception:
            logger.warning("Postgres connection lost — reconnecting")
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
                logger.info("Connected to PostgreSQL telemetry store")
            except Exception as exc:
                _conn_error_at = time.time()
                logger.warning("Postgres unavailable (%s) — running in file mode", exc)
                return None
        return _conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ergo_sessions (
    session_id        TEXT PRIMARY KEY,
    session_timestamp TEXT NOT NULL,
    worker_id         TEXT,
    created_by_user_id INTEGER,
    camera_id         TEXT,
    task_name         TEXT,
    highest_risk_level TEXT,
    session_duration_seconds REAL,
    total_frames      INTEGER,
    risk_percentages  JSONB,
    most_frequent_issue TEXT,
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ergo_sessions_ts
    ON ergo_sessions (session_timestamp);
CREATE INDEX IF NOT EXISTS idx_ergo_sessions_worker
    ON ergo_sessions (worker_id);
CREATE INDEX IF NOT EXISTS idx_ergo_sessions_risk
    ON ergo_sessions (highest_risk_level);

CREATE TABLE IF NOT EXISTS ergo_session_frames (
    session_id   TEXT NOT NULL,
    frame_number INTEGER NOT NULL,
    sample_time  TIMESTAMPTZ NOT NULL,
    risk_score   REAL,
    risk_level   TEXT,
    confidence   REAL,
    fatigue      REAL,
    exposure     REAL,
    current_task TEXT,
    features     JSONB,
    PRIMARY KEY (session_id, frame_number)
);
CREATE INDEX IF NOT EXISTS idx_ergo_frames_session
    ON ergo_session_frames (session_id, frame_number);
"""

_TIMESCALE_HYPERTABLE = (
    "SELECT create_hypertable('ergo_session_frames', 'sample_time', "
    "if_not_exists => TRUE);"
)


def init_postgres_schema() -> bool:
    """Create tables (and hypertable when enabled). Returns False on failure."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            from app.core.config import settings
            if settings.PG_TIMESCALEDB:
                try:
                    cur.execute(_TIMESCALE_HYPERTABLE)
                    logger.info("ergo_session_frames created as TimescaleDB hypertable")
                except Exception as exc:
                    logger.warning(
                        "TimescaleDB hypertable creation failed (%s) — "
                        "using plain table; install the timescaledb extension to enable",
                        exc,
                    )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("Postgres schema init failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def upsert_session(payload: dict) -> bool:
    """Insert or update one session summary row. Returns True on success."""
    conn = get_connection()
    if conn is None:
        return False
    try:
        rp = payload.get("risk_percentages") or {}
        clean_payload = _json_safe(payload)
        session_id = payload.get("session_id")
        if not session_id:
            # Legacy sessions predate session_id — synthesize one from the
            # timestamp so every row has a stable primary key.
            ts = str(payload.get("session_timestamp") or "")
            session_id = f"SESH-{ts}" if ts else f"SESH-{int(time.time())}"
            clean_payload["session_id"] = session_id
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ergo_sessions (
                    session_id, session_timestamp, worker_id, created_by_user_id,
                    camera_id, task_name, highest_risk_level,
                    session_duration_seconds, total_frames, risk_percentages,
                    most_frequent_issue, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    session_timestamp = EXCLUDED.session_timestamp,
                    worker_id = EXCLUDED.worker_id,
                    task_name = EXCLUDED.task_name,
                    highest_risk_level = EXCLUDED.highest_risk_level,
                    session_duration_seconds = EXCLUDED.session_duration_seconds,
                    total_frames = EXCLUDED.total_frames,
                    risk_percentages = EXCLUDED.risk_percentages,
                    most_frequent_issue = EXCLUDED.most_frequent_issue,
                    payload = EXCLUDED.payload
                """,
                (
                    session_id,
                    payload.get("session_timestamp", ""),
                    payload.get("worker_id"),
                    payload.get("created_by_user_id"),
                    payload.get("camera_id"),
                    payload.get("task_name"),
                    payload.get("highest_risk_level", "LOW"),
                    payload.get("session_duration_seconds", 0.0),
                    payload.get("total_frames", 0),
                    json.dumps(_json_safe(rp)),
                    payload.get("most_frequent_issue"),
                    json.dumps(clean_payload),
                ),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("Postgres upsert_session failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _sample_time(payload: dict, frame_ts: float) -> str:
    """Synthesize an absolute TIMESTAMPTZ for a timeline entry.

    Timeline entries store ``timestamp`` as seconds since session start; the
    session file stores ``session_timestamp`` (YYYYMMDD_HHMMSS...). Combine
    them into an absolute time so TimescaleDB partitioning / range queries
    work.
    """
    ts = str(payload.get("session_timestamp") or "")
    base = None
    try:
        from datetime import datetime, timezone
        clean = ts.rsplit("_", 1)[0] if ts.count("_") > 1 and ts.rsplit("_", 1)[1].isdigit() else ts
        base = datetime.strptime(clean, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        base = None
    if base is None:
        return "1970-01-01T00:00:00Z"
    from datetime import timedelta
    return (base + timedelta(seconds=float(frame_ts or 0.0))).isoformat()


def bulk_insert_frames(payload: dict, frames: list[dict]) -> bool:
    """Insert timeline rows for a session. Returns True on success."""
    conn = get_connection()
    if conn is None or not frames:
        return False if conn is None else True
    session_id = payload.get("session_id")
    if not session_id:
        return False
    try:
        rows = []
        if not session_id:
            ts = str(payload.get("session_timestamp") or "")
            session_id = f"SESH-{ts}" if ts else f"SESH-{int(time.time())}"
        for f in frames:
            rows.append((
                session_id,
                f.get("frame_number", 0),
                _sample_time(payload, f.get("timestamp", 0.0)),
                f.get("risk_score"),
                f.get("risk_level"),
                f.get("confidence"),
                f.get("fatigue"),
                f.get("exposure"),
                f.get("current_task"),
                json.dumps(_json_safe(f.get("features") or {})),
            ))
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ergo_session_frames (
                    session_id, frame_number, sample_time, risk_score,
                    risk_level, confidence, fatigue, exposure, current_task, features
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, frame_number) DO UPDATE SET
                    risk_score = EXCLUDED.risk_score,
                    risk_level = EXCLUDED.risk_level,
                    confidence = EXCLUDED.confidence,
                    fatigue = EXCLUDED.fatigue,
                    exposure = EXCLUDED.exposure,
                    current_task = EXCLUDED.current_task,
                    features = EXCLUDED.features
                """,
                rows,
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("Postgres bulk_insert_frames failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def fetch_sessions() -> list[dict]:
    """Return all session payloads (file-shaped dicts), newest first."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM ergo_sessions ORDER BY session_timestamp DESC"
            )
            out = []
            for row in cur.fetchall():
                val = row[0]
                # psycopg3 returns JSONB columns already parsed (dict); older
                # drivers/plain text return a JSON string — handle both.
                if isinstance(val, str):
                    val = json.loads(val)
                out.append(val)
            return out
    except Exception as exc:
        logger.warning("Postgres fetch_sessions failed: %s", exc)
        return []


def fetch_frames(session_id: str, limit: int | None = None) -> list[dict]:
    """Return timeline rows for a session (dict-shaped, oldest first)."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        sql = (
            "SELECT frame_number, sample_time, risk_score, risk_level, confidence, "
            "fatigue, exposure, current_task, features "
            "FROM ergo_session_frames WHERE session_id = %s "
            "ORDER BY frame_number"
        )
        params: list = [session_id]
        if limit:
            sql += " LIMIT %s"
            params.append(int(limit))
        with conn.cursor() as cur:
            cur.execute(sql, params)
            out = []
            for r in cur.fetchall():
                feats = r[8]
                if isinstance(feats, str):
                    feats = json.loads(feats) if feats else {}
                out.append({
                    "frame_number": r[0],
                    "sample_time": r[1].isoformat() if r[1] else None,
                    "risk_score": r[2],
                    "risk_level": r[3],
                    "confidence": r[4],
                    "fatigue": r[5],
                    "exposure": r[6],
                    "current_task": r[7],
                    "features": feats if isinstance(feats, dict) else (feats or {}),
                })
            return out
    except Exception as exc:
        logger.warning("Postgres fetch_frames failed: %s", exc)
        return []


def reset_connection() -> None:
    """Close the shared connection (used by tests / config changes)."""
    global _conn, _conn_error_at
    with _conn_lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
        _conn_error_at = 0.0


def iter_timeline_files(project_root: str) -> Iterator[tuple[dict, list[dict]]]:
    """Yield (payload, frames) pairs for every persisted session.

    Reads the JSON session summaries and their recording timelines — the
    source for the migration script (and a convenient re-import path).
    Recording dirs are named {worker}/{timestamp}_{session_id}/ and hold a
    summary.json keyed by session_id, so timelines are matched by reading
    each recording summary (reliable) rather than parsing dir names.
    """
    import glob

    sessions_dir = os.path.join(project_root, "outputs", "sessions")
    recordings_dir = os.path.join(project_root, "recordings")

    # session_id -> timeline.json path (from recording summary.json files)
    id_to_timeline: dict[str, str] = {}
    for summary_path in glob.glob(os.path.join(recordings_dir, "*", "*", "summary.json")):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        sid = meta.get("session_id")
        if sid:
            id_to_timeline[sid] = os.path.join(os.path.dirname(summary_path), "timeline.json")

    for path in sorted(glob.glob(os.path.join(sessions_dir, "session_*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            logger.warning("Skipping unreadable session file %s: %s", path, exc)
            continue
        session_id = payload.get("session_id")
        frames: list[dict] = []
        tl_path = id_to_timeline.get(session_id) if session_id else None
        if tl_path and os.path.exists(tl_path):
            try:
                with open(tl_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                frames = data if isinstance(data, list) else []
            except Exception as exc:
                logger.warning("Skipping unreadable timeline %s: %s", tl_path, exc)
        yield payload, frames
