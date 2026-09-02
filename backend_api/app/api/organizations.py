"""Organization management endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user, require_roles
from app.core.security import AuthenticatedUser
from app.core.database import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    plan: str
    industry: str
    country: str
    max_cameras: int
    max_workers: int
    created_at: str


class OrganizationListResponse(BaseModel):
    organizations: List[OrganizationResponse]
    current_org_id: Optional[int] = None


@router.get("/orgs", response_model=OrganizationListResponse)
async def list_organizations(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """List all organizations the user has access to.

    Admins see all orgs. Other users see only their own org.
    """
    with get_connection() as conn:
        if user.role == "admin":
            # Admins can see all organizations
            rows = conn.execute(
                "SELECT id, name, slug, plan, industry, country, max_cameras, max_workers, created_at "
                "FROM organizations ORDER BY name"
            ).fetchall()
        else:
            # Non-admins see only their own organization
            rows = conn.execute(
                "SELECT id, name, slug, plan, industry, country, max_cameras, max_workers, created_at "
                "FROM organizations WHERE id = ?",
                (user.org_id,)
            ).fetchall()

    orgs = [OrganizationResponse(**dict(r)) for r in rows]
    return OrganizationListResponse(
        organizations=orgs,
        current_org_id=user.org_id,
    )


@router.get("/orgs/current", response_model=OrganizationResponse)
async def get_current_organization(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Get the current user's organization details."""
    if user.org_id is None:
        raise HTTPException(status_code=404, detail="User not associated with an organization")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, slug, plan, industry, country, max_cameras, max_workers, created_at "
            "FROM organizations WHERE id = ?",
            (user.org_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrganizationResponse(**dict(row))


@router.get("/orgs/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: int,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Get organization details by ID (admin only)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, slug, plan, industry, country, max_cameras, max_workers, created_at "
            "FROM organizations WHERE id = ?",
            (org_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrganizationResponse(**dict(row))
