"""Pilot request endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.core.database import insert_pilot_request, load_pilot_requests

router = APIRouter()


class PilotRequestSubmit(BaseModel):
    company_name: str
    contact_name: str
    email: EmailStr
    role: str
    num_stations: Optional[str] = None
    message: Optional[str] = None


class PilotRequestResponse(BaseModel):
    id: int
    company_name: str
    contact_name: str
    email: str
    role: str
    num_stations: Optional[str]
    message: Optional[str]
    created_at: str


@router.post("/pilot-requests", status_code=201)
async def submit_pilot_request(body: PilotRequestSubmit):
    """Submit a new pilot request (public, no auth required)."""
    insert_pilot_request(
        company_name=body.company_name,
        contact_name=body.contact_name,
        email=body.email,
        role=body.role,
        num_stations=body.num_stations,
        message=body.message,
    )
    return {"detail": "Pilot request submitted successfully"}


@router.get("/pilot-requests", response_model=List[PilotRequestResponse])
async def list_pilot_requests(
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """List all pilot requests (admin only)."""
    return load_pilot_requests()
