"""User settings endpoints."""

import logging
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.database import get_user_settings, save_user_settings
from app.core.security import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current user's settings."""
    return get_user_settings(user.id)


@router.put("/settings")
async def update_settings(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Save current user's settings."""
    save_user_settings(user.id, body)
    return {"status": "ok"}
