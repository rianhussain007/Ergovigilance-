"""Privacy endpoints — admin-only data deletion (right-to-erasure).

Deleting a worker's data removes everything attributable to that worker:

- the ``recordings/<worker_id>/`` directory tree (video + timeline + summary)
- alert rows in the SQLite store for that worker

Limitation: session summary JSONs under ``outputs/sessions/`` are NOT
worker-attributed (they store no worker_id), so they cannot be matched to a
worker and are governed by the age-based retention policy instead.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_roles
from app.core.database import delete_alerts_for_worker, insert_audit_log
from app.core.security import AuthenticatedUser
from app.services.retention import dir_size

logger = logging.getLogger(__name__)

router = APIRouter()

_DEFAULT_RECORDINGS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")
)


def _recordings_dir() -> Path:
    return Path(os.environ.get("RECORDINGS_DIR") or _DEFAULT_RECORDINGS_DIR)


@router.post("/privacy/delete-worker-data/{worker_id}")
async def delete_worker_data(
    worker_id: str,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Delete all stored data attributable to a worker (admin only).

    Removes ``recordings/<worker_id>/`` and the worker's alert history.
    """
    # Guard against path traversal — worker_id becomes a directory name.
    safe_id = Path(worker_id).name
    if safe_id != worker_id or safe_id in {"", ".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid worker_id")

    result: dict = {
        "worker_id": worker_id,
        "recordings_deleted": 0,
        "recordings_freed_bytes": 0,
        "recordings_dir": None,
        "alerts_deleted": 0,
    }

    target = _recordings_dir() / safe_id
    if target.is_dir():
        try:
            result["recordings_freed_bytes"] = dir_size(target)
            shutil.rmtree(target)
            # Report deleted only if the directory is actually gone — rmtree can
            # silently no-op on a symlink target, and we must not log a deletion
            # that did not happen.
            if target.exists():
                raise OSError("directory still present after rmtree")
            result["recordings_deleted"] = 1
            result["recordings_dir"] = str(target)
            logger.warning("Privacy: deleted recordings dir %s (admin %s)", target, user.email)
        except OSError as exc:
            logger.exception("Privacy: failed to delete recordings dir %s", target)
            return {"status": "error", "detail": f"Failed to delete recordings: {exc}"}

    result["alerts_deleted"] = delete_alerts_for_worker(worker_id)

    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_data_deleted",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=f"recordings_deleted={result['recordings_deleted']} alerts_deleted={result['alerts_deleted']}",
    )

    return {"status": "ok", **result}


@router.get("/privacy/export-worker-data/{worker_id}")
async def export_worker_data(
    worker_id: str,
    user: AuthenticatedUser = Depends(require_roles("admin", "safety_mgr")),
):
    """GDPR Article 20 — Data Portability.

    Exports all data attributable to a worker as a downloadable JSON bundle:
    - Worker profile
    - Session history
    - Alert history
    - Recommendations
    - Consent records

    Returns a JSON response that can be saved or downloaded.
    """
    safe_id = Path(worker_id).name
    if safe_id != worker_id or safe_id in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid worker_id")

    from app.core.database import get_connection
    conn = get_connection()

    # Worker profile
    worker_row = conn.execute(
        "SELECT * FROM workers WHERE worker_id = ?", (safe_id,)
    ).fetchone()

    worker_profile = None
    if worker_row:
        worker_profile = {k: worker_row[k] for k in worker_row.keys()}

    # Sessions for this worker
    sessions = []
    sessions_dir = Path("outputs/sessions")
    if sessions_dir.is_dir():
        for f in sessions_dir.glob("*.json"):
            try:
                import json
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("worker_id") == safe_id:
                    sessions.append(data)
            except Exception:
                continue

    # Alerts for this worker
    alert_rows = conn.execute(
        "SELECT * FROM alerts WHERE worker_id = ? ORDER BY created_at DESC",
        (safe_id,),
    ).fetchall()
    alerts = [{k: row[k] for k in row.keys()} for row in alert_rows]

    # Consent records
    consent_rows = conn.execute(
        "SELECT * FROM worker_consent WHERE worker_id = ?",
        (safe_id,),
    ).fetchall()
    consents = [{k: row[k] for k in row.keys()} for row in consent_rows]

    export = {
        "export_info": {
            "worker_id": safe_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": user.email,
            "gdpr_article": "Article 20 — Right to Data Portability",
            "format": "JSON",
        },
        "worker_profile": worker_profile,
        "sessions": sessions,
        "alerts": alerts,
        "consent_records": consents,
        "summary": {
            "total_sessions": len(sessions),
            "total_alerts": len(alerts),
            "total_consents": len(consents),
        },
    }

    # Log the export for audit
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_data_exported",
        target_type="worker",
        target_id=safe_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=f"sessions={len(sessions)} alerts={len(alerts)}",
    )

    return export
