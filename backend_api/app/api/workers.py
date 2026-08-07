"""Worker CRUD endpoints — backed by the existing SQLite workers table."""

from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_roles
from app.core.database import (
    delete_worker,
    get_worker,
    insert_worker,
    insert_audit_log,
    list_workers,
    update_worker,
    worker_has_sessions,
)
from app.core.security import AuthenticatedUser

router = APIRouter()


class WorkerResponse(BaseModel):
    worker_id: str
    employee_id: str
    name: str
    department: str
    shift: str


class WorkerCreateRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, description="Unique employee identifier")
    name: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    shift: str = Field(..., min_length=1)


class WorkerUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    shift: str = Field(..., min_length=1)


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
    worker_id = insert_worker(body.employee_id, body.name, body.department, body.shift)
    row = get_worker(worker_id)

    # Log to audit trail
    details = json.dumps({
        "employee_id": body.employee_id,
        "name": body.name,
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
    updated = update_worker(worker_id, body.name, body.department, body.shift)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update worker")
    row = get_worker(worker_id)

    # Log to audit trail
    details = json.dumps({
        "old_name": existing_worker["name"],
        "new_name": body.name,
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

    # Log to audit trail
    details = json.dumps({
        "name": existing_worker["name"],
        "employee_id": existing_worker["employee_id"]
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
