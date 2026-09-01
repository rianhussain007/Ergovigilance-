"""User admin endpoints — admin-only CRUD for user accounts."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import string
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_roles
from app.core.database import get_connection, get_user_by_email, get_user_by_id
from app.core.security import AuthenticatedUser, hash_password

router = APIRouter()

VALID_ROLES = {"operator", "supervisor", "safety_mgr", "admin"}


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    created_at: str


class UserCreateRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    role: str = Field(...)


class UserUpdateRequest(BaseModel):
    role: str = Field(...)


class UserInviteRequest(BaseModel):
    email: str = Field(..., min_length=3)
    role: str = Field(...)
    name: str = Field(default="", description="Optional display name")


class UserResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8)


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def _user_row_to_response(row) -> UserResponse:
    return UserResponse(
        id=row["id"],
        email=row["email"],
        role=row["role"],
        created_at=row["created_at"],
    )


def _require_admin(user: AuthenticatedUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


@router.get("/users", response_model=List[UserResponse])
async def list_users(user: AuthenticatedUser = Depends(require_roles("admin"))):
    """List all users. Admin only."""
    _require_admin(user)
    with get_connection() as conn:
        rows = conn.execute("SELECT id, email, role, created_at FROM users ORDER BY id").fetchall()
        return [_user_row_to_response(r) for r in rows]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreateRequest,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Create a new user. Admin only. Password is hashed server-side."""
    _require_admin(user)
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
    existing = get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = await asyncio.to_thread(hash_password, body.password)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (body.email, pw_hash, body.role, now),
        )
        conn.commit()
        new_id = cur.lastrowid
    row = get_user_by_id(new_id)
    return _user_row_to_response(row)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Update a user's role. Admin only. Email and password cannot be changed via this endpoint."""
    _require_admin(user)
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (body.role, user_id),
        )
        conn.commit()
    updated = get_user_by_id(user_id)
    return _user_row_to_response(updated)


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    body: UserResetPasswordRequest | None = None,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Reset a user's password. Admin only.

    If a password is provided in the body, use it. Otherwise generate a random one.
    The new password hash is stored; the plain text is returned ONCE to the caller.
    """
    _require_admin(user)
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    new_password = body.password if body and body.password else _generate_temp_password()
    pw_hash = await asyncio.to_thread(hash_password, new_password)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (pw_hash, user_id),
        )
        conn.commit()
    return {"message": "Password reset successful", "new_password": new_password, "user_id": user_id}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Delete a user. Admin only. Cannot delete your own account (lockout prevention)."""
    _require_admin(user)
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["id"] == user.id:
        raise HTTPException(status_code=409, detail="Cannot delete your own account")
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


@router.post("/users/invite", status_code=201)
async def invite_user(
    body: UserInviteRequest,
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    """Invite a new user by email. Creates the account with a temporary password
    and sends an invitation email (if SMTP is configured).

    The invitee receives their login URL and temporary password via email.
    They should change their password on first login.
    """
    _require_admin(user)
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
    existing = get_user_by_email(body.email)
    if existing:
        raise HTTPException(409, f"A user with {body.email} already exists")

    # Generate temporary password
    temp_password = _generate_temp_password()
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = await asyncio.to_thread(hash_password, temp_password)

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (body.email, pw_hash, body.role, now),
        )
        conn.commit()
        new_id = cur.lastrowid

    # Send invitation email (non-blocking)
    try:
        from app.services.notifications import _send_email_sync
        invite_link = f"{os.getenv('APP_URL', 'http://localhost:3000')}/login"
        subject = f"You've been invited to ErgoVigilance ({body.role})"
        body_html = f"""
        <h2>Welcome to ErgoVigilance</h2>
        <p>{body.name or 'An administrator'} has invited you to join ErgoVigilance as a <strong>{body.role}</strong>.</p>
        <p><strong>Login URL:</strong> {invite_link}</p>
        <p><strong>Email:</strong> {body.email}</p>
        <p><strong>Temporary Password:</strong> <code>{temp_password}</code></p>
        <p>Please log in and change your password immediately.</p>
        """
        _send_email_sync(subject, body_html, [body.email], severity="LOW")
    except Exception as e:
        logger.debug("Invite email send failed (non-fatal): %s", e)

    return {
        "message": f"Invitation sent to {body.email}",
        "user_id": new_id,
        "temp_password": temp_password,  # Return once; not stored
        "role": body.role,
    }
