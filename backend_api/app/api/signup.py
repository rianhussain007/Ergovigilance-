"""Self-service signup endpoint.

Creates a new organization and admin user in a single request.
This is the entry point for new SaaS customers.
"""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.database import get_connection, get_user_by_email
from app.core.security import (
    AuthenticatedUser,
    JWT_TTL_SECONDS,
    create_access_token,
    hash_password,
)

router = APIRouter()

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class SignupRequest(BaseModel):
    """New organization + admin user creation."""
    organization_name: str
    industry: str = "Manufacturing"
    country: str = "IN"
    email: EmailStr
    password: str
    full_name: str = ""
    agree_terms: bool = False


class SignupResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: str
    organization: dict
    user: dict


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from organization name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    # Ensure uniqueness by appending a short uuid fragment
    return slug[:40] or f"org-{uuid.uuid4().hex[:6]}"


@router.post("/auth/signup", response_model=SignupResponse)
async def signup(body: SignupRequest):
    """Create a new organization and admin user.

    Flow:
    1. Validate inputs (name, email, password strength)
    2. Check email not already taken
    3. Create organization with pilot plan
    4. Create admin user linked to the organization
    5. Generate API key for cloud core access
    6. Return JWT token so user lands directly in their dashboard
    """
    # --- Validation ---
    if not body.agree_terms:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You must agree to the Terms of Service.",
        )
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )
    if len(body.organization_name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Organization name must be at least 2 characters.",
        )

    with get_connection() as conn:
        # Check email uniqueness (use same connection to see uncommitted writes)
        existing = conn.execute(
            "SELECT id FROM users WHERE lower(email) = lower(?)",
            (body.email.strip(),),
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        now = datetime.now(timezone.utc).isoformat()
        slug = _slugify(body.organization_name.strip())

        # Ensure slug uniqueness
        existing_slug = conn.execute(
            "SELECT id FROM organizations WHERE slug = ?", (slug,)
        ).fetchone()
        if existing_slug:
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"

        # --- Create organization ---
        cursor = conn.execute(
            """INSERT INTO organizations
               (name, slug, plan, industry, country, max_cameras, max_workers,
                api_key, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.organization_name.strip(),
                slug,
                "pilot",
                body.industry,
                body.country,
                4,       # pilot plan: 4 cameras (Starter parity — Q2)
                50,      # pilot plan: 50 workers
                f"ergo_signup_{uuid.uuid4().hex[:16]}",
                now,
                now,
            ),
        )
        org_id = cursor.lastrowid

        # --- Create admin user ---
        password_hash = hash_password(body.password)
        cursor = conn.execute(
            """INSERT INTO users (email, password_hash, role, org_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                body.email.strip(),
                password_hash,
                "admin",
                org_id,
                now,
            ),
        )
        user_id = cursor.lastrowid

        # --- Audit trail ---
        conn.execute(
            """INSERT INTO audit_log
               (id, actor_id, actor_email, actor_role, action_type,
                target_type, target_id, timestamp, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"AUD-{uuid.uuid4().hex[:8].upper()}",
                user_id,
                body.email.strip(),
                "admin",
                "org_created",
                "organization",
                str(org_id),
                now,
                f"New organization '{body.organization_name}' created via self-service signup",
            ),
        )

        # --- Build token ---
        user_obj = AuthenticatedUser(
            id=user_id,
            email=body.email.strip(),
            role="admin",
            org_id=org_id,
            org_slug=slug,
        )
        token = create_access_token(user_obj)

        from datetime import timedelta
        import time

        now_ts = int(time.time())
        from app.core.security import JWT_TTL_SECONDS as ttl

        return SignupResponse(
            token=token,
            expires_in=ttl,
            expires_at=datetime.fromtimestamp(now_ts + ttl, tz=timezone.utc).isoformat(),
            organization={
                "id": org_id,
                "name": body.organization_name.strip(),
                "slug": slug,
                "plan": "pilot",
                "industry": body.industry,
                "country": body.country,
                "max_cameras": 4,
                "max_workers": 50,
            },
            user={
                "id": user_id,
                "email": body.email.strip(),
                "role": "admin",
                "full_name": body.full_name,
            },
        )
