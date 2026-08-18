"""Camera setup wizard status — live guidance for positioning the camera.

The wizard polls this endpoint while a monitoring session runs (or Demo
mode replays a recording) and turns the signals into a checklist: is the
camera streaming, is the worker fully visible, is the lighting adequate, is
a face visible for identification. Lighting is a real measurement (mean
brightness of the current raw frame), not a guess.
"""

import logging

import cv2
from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Comfortable working range for an indoor workstation camera (0-255 scale).
_BRIGHTNESS_MIN = 60.0
_BRIGHTNESS_MAX = 200.0


def _mean_brightness() -> float | None:
    """Mean brightness (0-255) of the current raw camera frame, or None."""
    service = get_live_service()
    frame = service.get_frame(overlaid=False)
    if frame is None:
        return None
    try:
        small = cv2.resize(frame, (96, 54))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return round(float(gray.mean()), 1)
    except Exception as exc:  # noqa: BLE001 - brightness is best-effort
        logger.debug("Brightness read failed: %s", exc)
        return None


@router.get("/setup/status")
async def setup_status(
    user=Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Live camera-setup checklist signals (framing, light, person, face)."""
    service = get_live_service()
    running = service.is_running()
    state = service.get_state_snapshot()

    framing = dict(state.framing or {})
    brightness = _mean_brightness()

    identities = list(getattr(state, "person_identities", []) or [])
    faces_seen = any(
        r.get("seen") or r.get("matched") or bool(r.get("confidence", 0) > 0)
        for r in identities
    )

    framing_state = framing.get("framing_state")
    guidance = framing.get("guidance") or []
    quality = framing.get("quality_score")
    if not running:
        guidance = ["Start a monitoring session (or use Demo mode) — the wizard reads the live assessment."]

    return {
        "session_active": bool(running),
        "camera_status": state.camera_status,
        "camera_reconnecting": bool(state.camera_reconnecting),
        "streaming": bool(running) and not state.camera_reconnecting,
        "fps": round(state.fps or 0.0, 1),
        "framing_state": framing_state,
        "quality_score": quality,
        "guidance": guidance,
        "brightness": brightness,
        "brightness_ok": brightness is not None and _BRIGHTNESS_MIN <= brightness <= _BRIGHTNESS_MAX,
        "person_detected": bool(state.person_detected),
        "person_count": int(state.person_count or 0),
        "faces_seen": faces_seen,
        "lower_body_confidence": state.lower_body_confidence,
        # Checklist gates — the wizard renders these directly.
        "checks": {
            "streaming": bool(running) and not state.camera_reconnecting,
            "worker_visible": bool(running) and framing_state not in (None, "poor", "upper_body")
                and (quality is None or float(quality) >= 40),
            "lighting_ok": brightness is not None and _BRIGHTNESS_MIN <= brightness <= _BRIGHTNESS_MAX,
            "face_visible": faces_seen,
            "full_body": (state.lower_body_confidence or 0.0) >= 50.0,
        },
    }
