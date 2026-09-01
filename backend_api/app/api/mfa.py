"""MFA/TOTP API endpoints for enterprise accounts.

Provides:
- POST /api/mfa/setup — Generate TOTP secret + QR code
- POST /api/mfa/enable — Enable MFA after verifying code
- POST /api/mfa/disable — Disable MFA
- POST /api/mfa/verify — Verify a TOTP code
- GET /api/mfa/status — Check MFA status
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser
from app.core.mfa import (
    generate_mfa_secret,
    verify_totp,
    enable_mfa,
    disable_mfa,
    get_mfa_status,
)

router = APIRouter(prefix="/mfa", tags=["MFA"])


class MFAVerifyRequest(BaseModel):
    code: str


class MFAEnableRequest(BaseModel):
    code: str


@router.get("/status")
async def mfa_status(user=Depends(get_current_user)):
    """Check MFA status for the current user."""
    return get_mfa_status(user.id)


@router.post("/setup")
async def mfa_setup(user=Depends(get_current_user)):
    """Generate a new TOTP secret for the current user.
    
    Returns:
    - secret: The TOTP secret key (store securely)
    - provisioning_uri: URI for QR code generation
    - backup_codes: One-time recovery codes
    """
    # Only admins and safety managers can enable MFA
    if user.role not in ("admin", "safety_mgr"):
        raise HTTPException(
            status_code=403,
            detail="MFA is only available for admin and safety manager accounts.",
        )

    result = generate_mfa_secret(user.id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/enable")
async def mfa_enable(body: MFAEnableRequest, user=Depends(get_current_user)):
    """Enable MFA after verifying the TOTP code."""
    if user.role not in ("admin", "safety_mgr"):
        raise HTTPException(status_code=403, detail="MFA is only for admin/safety_mgr accounts.")

    result = enable_mfa(user.id, body.code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/disable")
async def mfa_disable(body: MFAVerifyRequest, user=Depends(get_current_user)):
    """Disable MFA after verifying the current code."""
    result = disable_mfa(user.id, body.code)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/verify")
async def mfa_verify(body: MFAVerifyRequest, user=Depends(get_current_user)):
    """Verify a TOTP code (used during login flow)."""
    valid = verify_totp(user.id, body.code)
    return {"valid": valid}
