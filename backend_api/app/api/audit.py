"""Audit trail endpoints — read-only access to audit log entries."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.auth import get_current_user, require_roles
from app.core.security import AuthenticatedUser
from app.core.database import load_audit_log

router = APIRouter()


class AuditEntryResponse(BaseModel):
    id: str
    actor_id: Optional[int]
    actor_email: str
    actor_role: str
    action_type: str
    target_type: Optional[str]
    target_id: Optional[str]
    timestamp: str
    details: Optional[str]


@router.get("/audit", response_model=List[AuditEntryResponse])
async def get_audit_log(
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor_email: Optional[str] = Query(None, description="Filter by actor email"),
    limit: int = Query(100, ge=1, le=1000, description="Number of entries to return"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    user: AuthenticatedUser = Depends(require_roles("safety_mgr", "admin")),
):
    """Get audit log entries (admin/safety_mgr only)."""
    return load_audit_log(
        action_type=action_type,
        actor_email=actor_email,
        limit=limit,
        offset=offset,
    )
