"""
Consent management endpoints for GDPR/CCPA compliance.

Workers must grant consent before monitoring begins. Consent can be
withdrawn at any time, triggering automatic data deletion after the
configured retention period.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.core.database import get_connection

router = APIRouter(prefix="/api/consent", tags=["Consent Management"])


class ConsentGrantRequest(BaseModel):
    purposes: list[str]
    data_categories: list[str]


class ConsentActionResponse(BaseModel):
    worker_id: str
    status: str
    message: str


CONSENT_POLICY = {
    "version": "1.0",
    "title": "ErgoVigilance Worker Monitoring Consent",
    "description": (
        "ErgoVigilance collects body pose data to assess ergonomic risk and improve "
        "workplace safety. All processing happens locally on-premise. No video or image "
        "data leaves your facility. You may withdraw consent at any time."
    ),
    "purposes": [
        "Ergonomic posture risk assessment",
        "Workplace safety monitoring",
        "Incident investigation and prevention",
        "Regulatory compliance reporting",
        "Worker health and wellness analytics",
    ],
    "data_categories": [
        "Body pose keypoints (2D)",
        "Posture risk scores (estimated)",
        "Session metadata (timestamps, duration)",
        "Worker identification (employee ID)",
        "Alert history (risk events)",
    ],
    "retention_days": 90,
    "rights": [
        "Right to access your monitoring data",
        "Right to withdraw consent at any time",
        "Right to request data deletion",
        "Right to data portability (export)",
        "Right to be informed about processing",
        "Right to object to automated decisions",
    ],
    "last_updated": "2025-01-15",
}


def _ensure_consent_table(db):
    """Create consent_records table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
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
            )
        """)
        conn.commit()


def _worker_in_scope(conn, worker_id: str, org_id: int | None) -> bool:
    """True when the worker exists and belongs to the caller's org.

    Legacy seed rows with NULL org stay visible to everyone (demo data).
    Missing or foreign-org workers return False, and callers answer 404
    (never disclose another tenant's team by existence).
    """
    row = conn.execute(
        "SELECT org_id FROM workers WHERE worker_id = ?", (worker_id,)
    ).fetchone()
    if row is None:
        return False
    return row[0] is None or org_id is None or row[0] == org_id


@router.get("/worker-consents")
async def get_worker_consents(current_user=Depends(get_current_user)):
    """Get consent status for all workers."""
    import json

    with get_connection() as conn:
        _ensure_consent_table(conn)

        # Get all workers visible to this org: own workers plus legacy
        # seed rows with no org (demo data). Never leak another org's team.
        if current_user.org_id is None:
            cursor = conn.execute("SELECT worker_id, name, department FROM workers ORDER BY name")
        else:
            cursor = conn.execute(
                "SELECT worker_id, name, department FROM workers "
                "WHERE org_id IS NULL OR org_id = ? ORDER BY name",
                (current_user.org_id,),
            )
        workers_db = cursor.fetchall()

        # Get consent records
        cursor = conn.execute("SELECT * FROM consent_records")
        consent_map = {}
        for row in cursor.fetchall():
            consent_map[row[0]] = {
                "status": row[3],
                "consent_date": row[4],
                "consent_expiry": row[5],
                "consent_version": row[6],
                "purposes": json.loads(row[7]) if row[7] else [],
                "data_categories": json.loads(row[8]) if row[8] else [],
                "retention_days": row[9],
                "withdrawal_date": row[10],
            }

    workers = []
    for w in workers_db:
        worker_id = w[0]
        consent = consent_map.get(worker_id, {})
        status = consent.get("status", "pending")

        workers.append({
            "worker_id": worker_id,
            "name": w[1],
            "department": w[2],
            "consent_status": status,
            "consent_date": consent.get("consent_date"),
            "consent_expiry": consent.get("consent_expiry"),
            "consent_version": consent.get("consent_version", "1.0"),
            "purpose": "; ".join(consent.get("purposes", [])),
            "data_categories": consent.get("data_categories", []),
            "retention_days": consent.get("retention_days", 90),
            "withdrawal_date": consent.get("withdrawal_date"),
            "consent_proof": None,
        })

    return {
        "workers": workers,
        "policy": CONSENT_POLICY,
    }


@router.post("/worker-consents/{worker_id}/grant")
async def grant_consent(
    worker_id: str,
    request: ConsentGrantRequest,
    current_user=Depends(get_current_user),
):
    """Grant monitoring consent for a worker."""
    import json
    from datetime import timezone

    with get_connection() as conn:
        _ensure_consent_table(conn)

        if not _worker_in_scope(conn, worker_id, current_user.org_id):
            raise HTTPException(status_code=404, detail="Worker not found")

        now = datetime.now(timezone.utc).isoformat()
        expiry = (datetime.now(timezone.utc) + timedelta(days=CONSENT_POLICY["retention_days"])).isoformat()

        conn.execute("""
            INSERT OR REPLACE INTO consent_records
            (worker_id, status, consent_date, consent_expiry, consent_version,
             purposes, data_categories, retention_days, updated_at)
            VALUES (?, 'granted', ?, ?, ?, ?, ?, ?, ?)
        """, (worker_id, now, expiry, CONSENT_POLICY["version"],
              json.dumps(request.purposes), json.dumps(request.data_categories),
              CONSENT_POLICY["retention_days"], now))
        conn.commit()

    return ConsentActionResponse(
        worker_id=worker_id,
        status="granted",
        message="Consent granted successfully.",
    )


@router.post("/worker-consents/{worker_id}/deny")
async def deny_consent(
    worker_id: str,
    current_user=Depends(get_current_user),
):
    """Deny monitoring consent for a worker."""
    from datetime import timezone

    with get_connection() as conn:
        _ensure_consent_table(conn)

        if not _worker_in_scope(conn, worker_id, current_user.org_id):
            raise HTTPException(status_code=404, detail="Worker not found")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT OR REPLACE INTO consent_records
            (worker_id, status, updated_at) VALUES (?, 'denied', ?)
        """, (worker_id, now))
        conn.commit()

    return ConsentActionResponse(
        worker_id=worker_id,
        status="denied",
        message="Consent denied.",
    )


@router.post("/worker-consents/{worker_id}/withdraw")
async def withdraw_consent(
    worker_id: str,
    current_user=Depends(get_current_user),
):
    """Withdraw previously granted consent. Triggers data deletion after retention period."""
    from datetime import timezone

    with get_connection() as conn:
        _ensure_consent_table(conn)

        if not _worker_in_scope(conn, worker_id, current_user.org_id):
            raise HTTPException(status_code=404, detail="Worker not found")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            UPDATE consent_records
            SET status = 'withdrawn', withdrawal_date = ?, updated_at = ?
            WHERE worker_id = ?
        """, (now, now, worker_id))
        conn.commit()

    return ConsentActionResponse(
        worker_id=worker_id,
        status="withdrawn",
        message="Consent withdrawn. Session data will be purged after retention period.",
    )
