"""User settings endpoints."""

import logging
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.database import get_user_settings, save_user_settings
from app.core.security import AuthenticatedUser
from app.schemas.user_settings import UserSettings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current user's settings."""
    return get_user_settings(user.id)


@router.put("/settings")
async def update_settings(
    body: UserSettings,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Save current user's settings."""
    # Only save non-None fields (partial update)
    settings_dict = body.model_dump(exclude_none=True)
    if not settings_dict:
        return {"status": "ok", "message": "No settings to update"}
    save_user_settings(user.id, settings_dict)
    return {"status": "ok", "updated_fields": list(settings_dict.keys())}
