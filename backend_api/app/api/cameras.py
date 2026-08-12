"""Camera endpoints."""

import logging
import time
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_repository
from app.core.auth import require_roles
from app.core.security import AuthenticatedUser
from app.repositories.base import DashboardRepository
from app.schemas.api import CameraInfo

logger = logging.getLogger(__name__)
router = APIRouter()

# Module-level cache for camera detection (same pattern as session cache in live.py)
_camera_detect_cache: list = []
_camera_detect_cache_time: float = 0
_CAMERA_DETECT_CACHE_TTL = 60  # seconds


class DetectedCamera(BaseModel):
    index: int
    name: str
    width: int
    height: int
    fps: float
    backend: str


@router.get("/cameras", response_model=List[CameraInfo])
async def get_cameras(
    repo: DashboardRepository = Depends(get_repository),
    _: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Camera status and metadata for all connected cameras."""
    return await repo.get_cameras()


@router.get("/cameras/detect", response_model=List[DetectedCamera])
async def detect_cameras(
    _: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Detect physically connected cameras using OpenCV. Results are cached for 60s."""
    global _camera_detect_cache, _camera_detect_cache_time

    now = time.time()
    if _camera_detect_cache and (now - _camera_detect_cache_time) < _CAMERA_DETECT_CACHE_TTL:
        return _camera_detect_cache

    try:
        from backend.services.camera_manager import detect_cameras as _detect
        cams = _detect(fast=True, max_index=5)
        result = [
            DetectedCamera(
                index=c.index,
                name=c.name or f"Camera {c.index}",
                width=c.width,
                height=c.height,
                fps=round(c.fps, 1),
                backend=c.backend_name,
            )
            for c in cams
        ]
        # Include configured IP/RTSP cameras (CAMERA_SOURCES env) so factory
        # cameras appear in camera pickers even when no USB camera is attached.
        from app.core.config import settings
        for cam in settings.CAMERA_SOURCES:
            result.append(DetectedCamera(
                index=-1,
                name=cam["name"],
                width=0,
                height=0,
                fps=0.0,
                backend="RTSP",
            ))
        _camera_detect_cache = result
        _camera_detect_cache_time = now
        return result
    except Exception as e:
        logger.warning("Camera detection failed: %s", e)
        return []
