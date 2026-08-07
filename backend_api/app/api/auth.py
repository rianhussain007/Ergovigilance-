"""Authentication endpoints."""

import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.database import get_user_by_email, insert_audit_log
from app.core.security import AuthenticatedUser, create_access_token, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginUser(BaseModel):
    id: int
    email: str
    role: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: LoginUser


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    row = get_user_by_email(body.email.strip())
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user = AuthenticatedUser(id=row["id"], email=row["email"], role=row["role"])

    # Log to audit trail
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="user_login",
        target_type=None,
        target_id=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=None,
    )

    return LoginResponse(
        token=create_access_token(user),
        user=LoginUser(id=user.id, email=user.email, role=user.role),
    )
