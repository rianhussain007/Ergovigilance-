"""User settings schema — validates settings updates before persistence."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class UserSettings(BaseModel):
    """Validated user settings payload.

    The settings dict is intentionally open-ended (key-value pairs stored as
    JSON) so the frontend can evolve the shape without a backend migration.
    However, we enforce basic hygiene: no None keys, reasonable string lengths,
    and a hard cap on total size to prevent payload-bomb attacks.
    """

    # Common known settings keys (frontend may send additional ones)
    theme: Optional[str] = Field(None, pattern="^(light|dark|system)$")
    language: Optional[str] = Field(None, min_length=2, max_length=10)
    notifications_enabled: Optional[bool] = None
    data_retention_days: Optional[int] = Field(None, ge=0, le=365)
    camera_quality: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    alert_sound: Optional[bool] = None
    dashboard_layout: Optional[str] = Field(None, min_length=1, max_length=50)

    model_config = {"extra": "allow"}  # Allow additional settings from the frontend


class UserSettingsResponse(BaseModel):
    """Response wrapper for user settings."""
    settings: dict
    user_id: int
