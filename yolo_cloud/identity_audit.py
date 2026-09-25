"""Append-only audit log for every identity bind / unbind.

Recorded events: ``bind``, ``rebind`` (ID switch), ``override`` (supervisor),
``reentry`` (heuristic re-attach), ``unbind``, ``face_rejected`` (refused below
the verified band), ``consent_withdraw``, ``consent_restore``.

Storage is append-only JSONL on disk so it survives a restart and can be grepped
during an incident. When ``DATABASE_URL`` is configured the same event is also
best-effort mirrored to PostgreSQL (see ``_pg_mirror``).

Nothing here may raise into the request path: a failed audit write logs a
warning and returns ``False`` rather than failing a safety operation. Losing an
audit line is bad; failing a supervisor's override mid-shift is worse.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

# Durable, greppable, no schema migration needed.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_AUDIT_PATH = os.path.join(_REPO_ROOT, "outputs", "audit", "identity_audit.jsonl")


def audit_path() -> str:
    return os.getenv("IDENTITY_AUDIT_PATH", DEFAULT_AUDIT_PATH)


def record(event: str, **fields) -> Optional[dict]:
    """Append one audit event. Returns the record, or None if the write failed."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    try:
        path = audit_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = json.dumps(entry, separators=(",", ":"), default=str)
        with _LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        _pg_mirror(entry)
        return entry
    except Exception as exc:  # noqa: BLE001 - auditing must never break a request
        logger.warning("Identity audit write failed (%s): %s", event, exc)
        return None


def read(
    limit: int = 200,
    camera_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    event: Optional[str] = None,
) -> list[dict]:
    """Most-recent-first audit events, optionally filtered."""
    path = audit_path()
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    try:
        with _LOCK:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if camera_id and entry.get("camera_id") != camera_id:
                continue
            if worker_id and entry.get("worker_id") != worker_id:
                continue
            if event and entry.get("event") != event:
                continue
            out.append(entry)
            if len(out) >= max(1, limit):
                break
    except Exception as exc:  # noqa: BLE001
        logger.warning("Identity audit read failed: %s", exc)
    return out


def _pg_mirror(entry: dict) -> None:
    """Best-effort mirror to PostgreSQL. Never raises."""
    try:
        from yolo_cloud import storage

        if not storage.pg_enabled():
            return
        conn = storage.get_connection()
        if conn is None:
            return
        conn.execute(
            """INSERT INTO cloud_identity_audit
                 (ts, event, camera_id, track_id, worker_id, method, actor, reason, confidence, payload)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
               ON CONFLICT DO NOTHING""",
            (
                entry.get("ts"), entry.get("event"), entry.get("camera_id"),
                entry.get("track_id"), entry.get("worker_id"), entry.get("method"),
                entry.get("actor"), entry.get("reason"), entry.get("confidence", 0),
                json.dumps(entry),
            ),
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - table may not exist yet
        logger.debug("Identity audit PG mirror skipped: %s", exc)
