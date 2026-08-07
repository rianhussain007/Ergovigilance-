"""Video streaming endpoint — MJPEG feed from the live pipeline with pose overlay."""

import logging
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.auth import require_live_session_access
from app.core.database import get_user_by_id
from app.core.security import AuthenticatedUser, decode_access_token
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Risk-level BGR colors matching Video Review (green-400, amber-400, red-400)
RISK_COLORS = {
    "LOW": (128, 222, 74),     # rgb(74, 222, 128) → BGR
    "MEDIUM": (36, 191, 251),  # rgb(251, 191, 36) → BGR
    "HIGH": (113, 113, 248),   # rgb(248, 113, 113) → BGR
}

# MediaPipe Pose connections for skeleton drawing
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # Arms
    (11, 23), (12, 24), (23, 24),  # Torso
    (23, 25), (25, 27), (24, 26), (26, 28),  # Legs
    (27, 29), (29, 31), (28, 30), (30, 32),  # Lower legs
    (15, 17), (15, 19), (15, 21), (16, 18), (16, 20), (16, 22),  # Hands
    (0, 1), (1, 2), (2, 3), (3, 7),  # Face
    (0, 4), (4, 5), (5, 6), (6, 8),  # Face
    (9, 10),  # Mouth
]

# Label positions: (feature_name, short_label, landmark_index, (dx, dy))
LABEL_CONFIG = [
    ("neck_flexion", "N", 0, (-20, -30)),
    ("trunk_flexion", "T", 23, (15, -10)),
    ("left_shoulder_elev", "LS", 11, (-30, -20)),
    ("right_shoulder_elev", "RS", 12, (10, -20)),
    ("shoulder_symmetry", "Sym", 11, (-55, -35)),
    ("knee_angle", "K", 25, (15, 5)),
]


def _draw_skeleton(frame, keypoints, risk_level, features=None, feature_scores=None):
    """Draw pose skeleton overlay on the frame using risk-level colors only.

    Uses the same green/orange/red color scheme as Video Review.
    Confidence-based dimming and angle labels are preserved.
    """
    import cv2

    if not keypoints:
        return frame

    features = features or {}

    glow = frame.copy()
    overlay = frame.copy()
    h, w = frame.shape[:2]

    color = RISK_COLORS.get(risk_level, (128, 128, 128))

    def _dimmed(c, visibility):
        if visibility >= 0.75:
            return c
        if visibility >= 0.35:
            factor = 0.5 + 0.5 * (visibility - 0.35) / 0.4
        else:
            factor = max(0.15, visibility / 0.35 * 0.35)
        return tuple(int(v * factor) for v in c)

    # ── 1. Draw connections ──
    for start_idx, end_idx in POSE_CONNECTIONS:
        if start_idx < len(keypoints) and end_idx < len(keypoints):
            start_kp = keypoints[start_idx]
            end_kp = keypoints[end_idx]

            if len(start_kp) >= 2 and len(end_kp) >= 2:
                x1, y1 = int(start_kp[0] * w), int(start_kp[1] * h)
                x2, y2 = int(end_kp[0] * w), int(end_kp[1] * h)

                vis_start = start_kp[3] if len(start_kp) > 3 else 1.0
                vis_end = end_kp[3] if len(end_kp) > 3 else 1.0
                c = _dimmed(color, min(vis_start, vis_end))

                cv2.line(glow, (x1, y1), (x2, y2), c, 8, cv2.LINE_AA)
                cv2.line(overlay, (x1, y1), (x2, y2), c, 3, cv2.LINE_AA)

    # ── 2. Draw keypoints ──
    for i, kp in enumerate(keypoints):
        if len(kp) >= 2:
            x, y = int(kp[0] * w), int(kp[1] * h)
            visibility = kp[3] if len(kp) > 3 else 1.0
            c = _dimmed(color, visibility)

            cv2.circle(glow, (x, y), 9, c, -1, cv2.LINE_AA)
            cv2.circle(overlay, (x, y), 5, c, -1, cv2.LINE_AA)
            cv2.circle(overlay, (x, y), 6, _dimmed((235, 255, 245), visibility), 1, cv2.LINE_AA)

    # Blend overlay with original frame
    cv2.addWeighted(glow, 0.28, frame, 0.72, 0, frame)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

    # ── 3. Per-joint angle labels ──
    import math
    for feat_name, short, kp_idx, (dx, dy) in LABEL_CONFIG:
        if kp_idx >= len(keypoints) or len(keypoints[kp_idx]) < 2:
            continue
        value = features.get(feat_name)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        kp = keypoints[kp_idx]
        kx = int(kp[0] * w)
        ky = int(kp[1] * h)
        lx = kx + dx
        ly = ky + dy
        lx = max(4, min(lx, w - 80))
        ly = max(14, min(ly, h - 4))
        text = f"{short}:{value:.1f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.45
        thick = 1
        (tw, th), base = cv2.getTextSize(text, font, scale, thick)
        pad = 4
        cv2.rectangle(frame, (lx - pad, ly - th - pad),
                      (lx + tw + pad, ly + base + pad), (8, 12, 18), -1)
        cv2.rectangle(frame, (lx - pad, ly - th - pad),
                      (lx + tw + pad, ly + base + pad), color, 1)
        cv2.putText(frame, text, (lx, ly), font, scale, color, thick, cv2.LINE_AA)

    # Add risk level indicator
    cv2.rectangle(frame, (10, h - 46), (180, h - 12), (8, 12, 18), -1)
    cv2.rectangle(frame, (10, h - 46), (180, h - 12), color, 1)
    cv2.putText(frame, f"RISK: {risk_level}", (20, h - 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2, cv2.LINE_AA)

    return frame


def _generate_mjpeg(overlay: bool = True):
    """Generate multipart MJPEG frames from the live service with optional pose overlay."""
    import cv2

    service = get_live_service()
    while True:
        frame = service.get_frame()
        if frame is None:
            import asyncio
            asyncio.sleep(0.05)
            continue

        if overlay:
            state = service.get_state_snapshot()
            keypoints = state.keypoints if hasattr(state, 'keypoints') else []
            risk_level = state.risk_level
            features = state.features if hasattr(state, 'features') else {}
            frame = _draw_skeleton(frame.copy(), keypoints, risk_level, features)

        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            jpeg.tobytes() +
            b'\r\n'
        )


@router.get("/video/feed")
async def video_feed(
    request: Request,
    camera_id: str | None = None,
    overlay: bool = True,
):
    """MJPEG video stream from the live camera pipeline with optional pose overlay.

    Parameters
    ----------
    camera_id : str, optional
        Reserved for multi-camera support.
    overlay : bool, optional
        Set to false to receive raw video without skeleton overlay.
    """
    service = get_live_service()
    if not service.is_running():
        raise HTTPException(status_code=503, detail="No active session. POST /api/session/start first.")

    auth_header = request.headers.get("authorization", "")
    token = request.query_params.get("token")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    if token:
        try:
            payload = decode_access_token(token)
            row = get_user_by_id(int(payload["sub"]))
            if row is not None:
                user = AuthenticatedUser(id=row["id"], email=row["email"], role=row["role"])
                require_live_session_access(user, service)
        except Exception:
            pass

    return StreamingResponse(
        _generate_mjpeg(overlay=overlay),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
