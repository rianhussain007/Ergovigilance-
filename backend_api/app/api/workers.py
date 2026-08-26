"""Worker CRUD endpoints — backed by the existing SQLite workers table."""

from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from fastapi.responses import Response

from app.core.auth import get_current_user, require_roles
from app.core.database import (
    delete_worker,
    get_worker,
    get_worker_by_badge_id,
    insert_worker,
    insert_audit_log,
    list_workers,
    set_worker_badge,
    update_worker,
    update_worker_identity,
    worker_has_sessions,
)
from app.core.security import AuthenticatedUser
from app.services.worker_faces import (
    enroll_worker,
    delete_worker_face,
    get_face_status,
)

router = APIRouter()


def _normalize_name(name: str) -> str:
    """Title-case an all-lowercase name so entries are stored consistently
    ("praneeth" -> "Praneeth"). Names with any capitalization are left as-is
    so proper names like "McDonald" or "van der Berg" are never mangled."""
    if not name or name != name.lower():
        return name
    return " ".join(part.capitalize() for part in name.split())


class WorkerResponse(BaseModel):
    worker_id: str
    employee_id: str
    name: str
    department: str
    shift: str
    identity_mode: str = "face"
    consent_status: str = "pending"
    badge_id: str | None = None


class WorkerCreateRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, description="Unique employee identifier")
    name: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    shift: str = Field(..., min_length=1)


class WorkerUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    shift: str = Field(..., min_length=1)


class WorkerIdentityUpdateRequest(BaseModel):
    identity_mode: str = Field(..., pattern="^(face|badge|off)$")
    consent_status: str = Field(..., pattern="^(granted|pending|denied)$")


class BadgeUpdateRequest(BaseModel):
    badge_id: str = Field(..., min_length=2, max_length=64)


class BadgeCheckinRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=256, description="Scanned badge/QR code value")


@router.get("/workers", response_model=List[WorkerResponse])
async def get_workers(_: AuthenticatedUser = Depends(get_current_user)):
    """List all workers. Available to all authenticated users."""
    return [WorkerResponse(**dict(row)) for row in list_workers()]


@router.post("/workers", response_model=WorkerResponse, status_code=201)
async def create_worker(
    body: WorkerCreateRequest,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Create a new worker. Allowed for supervisor, safety_mgr, admin."""
    existing = get_worker_by_employee_id(body.employee_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Employee ID '{body.employee_id}' already belongs to worker '{existing['worker_id']}'",
        )
    worker_id = insert_worker(body.employee_id, _normalize_name(body.name), body.department, body.shift)
    row = get_worker(worker_id)

    # Log to audit trail
    details = json.dumps({
        "employee_id": body.employee_id,
        "name": _normalize_name(body.name),
        "department": body.department,
        "shift": body.shift
    })
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_created",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )

    return WorkerResponse(**dict(row))


@router.put("/workers/{worker_id}", response_model=WorkerResponse)
async def update_worker_endpoint(
    worker_id: str,
    body: WorkerUpdateRequest,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Update a worker's name, department, shift. Allowed for supervisor, safety_mgr, admin."""
    existing_worker = get_worker(worker_id)
    if not existing_worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    updated = update_worker(worker_id, _normalize_name(body.name), body.department, body.shift)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update worker")
    row = get_worker(worker_id)

    # Log to audit trail
    details = json.dumps({
        "old_name": existing_worker["name"],
        "new_name": _normalize_name(body.name),
        "old_department": existing_worker["department"],
        "new_department": body.department,
        "old_shift": existing_worker["shift"],
        "new_shift": body.shift
    })
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_updated",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )

    return WorkerResponse(**dict(row))


@router.delete("/workers/{worker_id}", status_code=204)
async def delete_worker_endpoint(
    worker_id: str,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Delete a worker. Blocked if worker has existing session history or alerts."""
    existing_worker = get_worker(worker_id)
    if not existing_worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    if worker_has_sessions(worker_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete worker with existing session history or alerts. "
            "Remove all session records and alerts for this worker first.",
        )
    deleted = delete_worker(worker_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete worker")
    # Cascade: erase all stored biometric samples with the worker record.
    face_erased = delete_worker_face(worker_id)

    # Log to audit trail
    details = json.dumps({
        "name": existing_worker["name"],
        "employee_id": existing_worker["employee_id"],
        "biometric_samples_erased": face_erased,
    })
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_deleted",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )


def get_worker_by_employee_id(employee_id: str) -> dict | None:
    from app.core.database import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workers WHERE lower(employee_id) = lower(?)", (employee_id,)
        ).fetchone()
        return dict(row) if row else None


# ── Identity mode, consent & badge/QR ────────────────────────────────────


@router.patch("/workers/{worker_id}/identity", response_model=WorkerResponse)
async def update_worker_identity_endpoint(
    worker_id: str,
    body: WorkerIdentityUpdateRequest,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Set a worker's identity mode (face/badge/off) and consent status.

    Setting ``identity_mode`` to ``badge`` or ``off`` (or ``consent_status``
    to ``denied``) immediately removes the worker from face-recognition
    matching — their stored embedding is never compared at runtime.
    """
    existing = get_worker(worker_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Worker not found")
    updated = update_worker_identity(worker_id, body.identity_mode, body.consent_status)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update identity settings")
    # Consent withdrawal is irreversible for biometrics: physically erase the
    # stored embeddings, not just exclude them from matching. Re-enrollment
    # after a re-grant requires fresh photos anyway.
    biometric_erased = False
    if body.consent_status == "denied" and existing["consent_status"] != "denied":
        biometric_erased = delete_worker_face(worker_id)
    row = get_worker(worker_id)

    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_identity_updated",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=json.dumps({
            "worker_id": worker_id,
            "old_identity_mode": existing["identity_mode"],
            "new_identity_mode": body.identity_mode,
            "old_consent_status": existing["consent_status"],
            "new_consent_status": body.consent_status,
            "biometric_samples_erased": biometric_erased,
        }),
    )
    return WorkerResponse(**dict(row))


@router.put("/workers/{worker_id}/badge", response_model=WorkerResponse)
async def set_worker_badge_endpoint(
    worker_id: str,
    body: BadgeUpdateRequest,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Assign a badge/QR identifier to a worker."""
    existing = get_worker(worker_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Worker not found")
    conflict = get_worker_by_badge_id(body.badge_id)
    if conflict and conflict["worker_id"] != worker_id:
        raise HTTPException(
            status_code=409,
            detail=f"Badge '{body.badge_id}' already belongs to worker '{conflict['employee_id']}'",
        )
    updated = set_worker_badge(worker_id, body.badge_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to assign badge")
    row = get_worker(worker_id)

    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_badge_set",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=json.dumps({"worker_id": worker_id, "badge_id": body.badge_id}),
    )
    return WorkerResponse(**dict(row))


@router.delete("/workers/{worker_id}/badge", response_model=WorkerResponse)
async def clear_worker_badge_endpoint(
    worker_id: str,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Remove a worker's badge/QR identifier."""
    existing = get_worker(worker_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Worker not found")
    set_worker_badge(worker_id, None)
    row = get_worker(worker_id)

    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_badge_removed",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=json.dumps({"worker_id": worker_id, "had_badge": bool(existing["badge_id"])}),
    )
    return WorkerResponse(**dict(row))


@router.get("/workers/{worker_id}/badge/qr")
async def get_worker_badge_qr(
    worker_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Return the worker's badge as a scannable QR code (SVG).

    The payload embeds the employee ID and badge ID in a recognizable format:
    ``ERGOVIGILANCE:BADGE:<employee_id>:<badge_id>`` — any standard QR
    scanner shows the worker's identity without network access.
    """
    existing = get_worker(worker_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Worker not found")
    badge_id = existing["badge_id"] or existing["employee_id"]
    payload = f"ERGOVIGILANCE:BADGE:{existing['employee_id']}:{badge_id}"
    try:
        import segno
        qr = segno.make(payload, error="m")
        import io
        buf = io.BytesIO()
        qr.save(buf, kind="svg", scale=4, dark="#111827", light="#ffffff")
        return Response(content=buf.getvalue(), media_type="image/svg+xml")
    except ImportError:
        # segno is a tiny pure-Python dependency; without it, return the
        # payload as plain text so a supervisor can still encode it.
        return Response(content=payload, media_type="text/plain")


@router.post("/workers/identify-badge", response_model=WorkerResponse)
async def identify_worker_by_badge(
    body: BadgeCheckinRequest,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Identify a worker from a scanned badge/QR code.

    Accepts either the raw badge code or the full QR payload
    (``ERGOVIGILANCE:BADGE:EMP-001:<code>``) so both a generic scanner and a
    re-scan of this product's own QR work.
    """
    code = body.code.strip()
    # Accept the full payload form too (split off the trailing badge code).
    if code.startswith("ERGOVIGILANCE:BADGE:"):
        parts = code.split(":")
        if len(parts) >= 4:
            code = parts[3]
    row = get_worker_by_badge_id(code)
    if row is None:
        # Fall back to employee ID (a supervisor may scan the EMP tag itself).
        from app.api.workers import get_worker_by_employee_id
        row = get_worker_by_employee_id(code)
    if row is None:
        raise HTTPException(status_code=404, detail="No worker matches this badge code")
    return WorkerResponse(**dict(row))


# ── Face enrollment ───────────────────────────────────────────────────────


@router.get("/workers/{worker_id}/face", response_model=dict)
async def get_worker_face_status(
    worker_id: str,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Return whether a worker has an enrolled face photo."""
    if not get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    return get_face_status(worker_id)


@router.post("/workers/{worker_id}/face", response_model=dict)
async def upload_worker_face(
    worker_id: str,
    file: UploadFile = File(..., description="Face photo (jpg/png)"),
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Enroll a worker's face photo for live recognition.

    Accepts a single image (jpg/png/webp). Computes a 128-dim SFace
    embedding and stores it keyed by worker_id. Returns 422 if the photo
    contains no usable face.
    """
    if not get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Empty file uploaded")
    # Guard against absurd uploads (10 MB cap) so a huge file can't pin the
    # worker thread decoding it.
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB)")
    try:
        result = enroll_worker(worker_id, image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Log to audit trail
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_face_enrolled",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=json.dumps({"worker_id": worker_id, "enrolled_at": result.get("enrolled_at")}),
    )
    return result


@router.delete("/workers/{worker_id}/face", status_code=204)
async def remove_worker_face(
    worker_id: str,
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Remove a worker's face enrollment."""
    if not get_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    deleted = delete_worker_face(worker_id)

    # Log to audit trail
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="worker_face_removed",
        target_type="worker",
        target_id=worker_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=json.dumps({"worker_id": worker_id, "had_enrollment": deleted}),
    )
    return None
