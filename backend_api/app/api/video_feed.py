"""Video streaming endpoint — MJPEG feed from the live pipeline with pose overlay."""

import logging
import os
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.auth import require_live_session_access
from app.core.database import get_user_by_id
from app.core.security import AuthenticatedUser, decode_access_token
from app.services.live_monitor import get_live_service

logger = logging.getLogger(__name__)
router = APIRouter()

from app.services.pose_overlay import draw_skeleton

# Serve the MJPEG stream at the camera's native rate (~30 fps). The pose
# pipeline is throttled separately (POSE_PROCESS_FPS) — the VIDEO path is
# decoupled from inference, so it can run at full capture rate while the
# skeleton refreshes as fast as inference allows. Override with
# VIDEO_FEED_FPS.
def _feed_fps() -> float:
    try:
        return max(5.0, min(30.0, float(os.environ.get("VIDEO_FEED_FPS", "30"))))
    except (TypeError, ValueError):
        return 30.0

FRAME_INTERVAL_S = 1.0 / _feed_fps()

# Encode the MJPEG stream at a reduced resolution. draw_skeleton + JPEG
# encode at native 1280x720 cost ~19 ms/frame — at 30 fps that's ~570 ms/s
# of GIL-bound CPU, starving the pose-inference thread (pipeline fps halved
# when the stream went to 30 fps). The browser scales the feed to its
# container anyway, so 640 wide looks near-identical on the dashboard while
# cutting stream cost ~4x. Override with STREAM_WIDTH.
def _stream_width() -> int:
    try:
        return max(320, int(os.environ.get("STREAM_WIDTH", "640")))
    except (TypeError, ValueError):
        return 640


def _generate_mjpeg(overlay: bool = True):
    """Generate multipart MJPEG frames from the live service with optional pose overlay.

    Serves EVERY captured camera frame (keyed off the capture counter, which
    advances at the camera's native rate), so the feed stays continuous even
    when pose inference lags behind. When *overlay* is enabled, the latest
    processed skeleton is redrawn on each fresh frame — the video keeps
    moving and the skeleton refreshes whenever inference completes.
    """
    import cv2
    import time

    service = get_live_service()
    last_capture_counter = None
    last_frame_time = time.perf_counter()
    while True:
        capture_counter = service.get_capture_counter()
        if capture_counter is None or capture_counter == last_capture_counter:
            time.sleep(0.005)
            continue

        frame = service.get_frame(overlaid=False)
        if frame is None:
            time.sleep(0.005)
            continue
        last_capture_counter = capture_counter

        # Downscale for the stream: drawing the skeleton + JPEG encoding at
        # native 1280x720 at 30 fps starves the inference thread (GIL). The
        # browser scales the feed to its container, so this looks the same
        # on the dashboard at ~4x less CPU.
        max_w = _stream_width()
        if frame.shape[1] > max_w:
            scale = max_w / float(frame.shape[1])
            frame = cv2.resize(
                frame, (max_w, max(1, int(frame.shape[0] * scale)))
            )

        if overlay:
            try:
                # Pass the current capture counter so the service interpolates
                # keypoints between processed poses — the skeleton tracks the
                # moving body at video rate instead of jumping once per
                # inference (~8 fps), which made the overlay visibly lag.
                payload = service.get_overlay_payload(capture_counter)
                keypoints = payload.get("keypoints") or []
                if keypoints:
                    draw_skeleton(
                        frame,
                        keypoints,
                        payload.get("risk_level", "LOW"),
                        payload.get("features") or {},
                        standard_assessment=payload.get("standard_assessment"),
                    )
            except Exception:
                pass  # never let overlay drawing kill the stream

        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if not ret:
            continue

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            jpeg.tobytes() +
            b'\r\n'
        )

        # Throttle to ~15fps max
        elapsed = time.perf_counter() - last_frame_time
        if elapsed < FRAME_INTERVAL_S:
            time.sleep(FRAME_INTERVAL_S - elapsed)
        last_frame_time = time.perf_counter()


def _resolve_camera_source(camera_id: str | None, service) -> int | str | None:
    """Map a requested ``camera_id`` to a camera source, or None for the session camera.

    The active analysis session records its camera source (``current_camera_source``
    — an int index or an RTSP URL). A request for that camera — or one without
    ``camera_id`` — serves the analyzed feed with overlay. A request for a
    *different* camera routes to the per-camera raw feed manager (multi-camera
    support). ``camera_id`` may be:

    - ``None`` / the session camera  -> ``None`` (analyzed feed)
    - a configured ``CAMERA_SOURCES`` id -> that camera's RTSP URL
    - an RTSP/HTTP URL directly
    - ``"0"`` / ``"cam-0"`` -> int index 0
    """
    if camera_id is None:
        return None
    cid = camera_id.strip()
    if not cid:
        return None

    # Match a configured IP camera by id -> serve its RTSP URL raw.
    try:
        from app.core.config import settings
        for cam in settings.CAMERA_SOURCES:
            if cam["id"] == cid:
                return cam["url"]
    except Exception:
        pass

    # Direct RTSP/HTTP URL (e.g. camera_id=rtsp://...).
    if cid.lower().startswith(("rtsp://", "rtmp://", "http://", "https://")):
        return cid

    # Accept both "0" and "cam-0" id formats.
    raw = cid
    if raw.lower().startswith("cam-"):
        raw = raw[4:]
    try:
        requested = int(raw)
    except (ValueError, TypeError):
        return None  # non-numeric ids fall back to the session feed
    session_source = getattr(service, "current_camera_source", None)
    if session_source is not None and requested == int(session_source):
        return None  # it IS the analysis camera
    return requested


def _generate_raw_mjpeg(source: int | str):
    """MJPEG frames from a raw per-camera feed (no pose overlay)."""
    import time

    from backend.services.raw_camera_feed import get_feed, release_feed

    feed = get_feed(source)
    feed.acquire()
    last_frame_number = None
    try:
        while True:
            frame_number = feed.get_frame_number()
            if frame_number is None or frame_number == last_frame_number:
                time.sleep(0.05)
                continue
            frame = feed.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            last_frame_number = frame_number
            ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not ret:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            )
    finally:
        release_feed(source)


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
        Camera index ("0", "1", …). When it matches the active analysis session
        camera — or is omitted — the analyzed feed (with optional pose overlay)
        is served. A different camera index routes to that camera's RAW feed
        (multi-camera support).
    overlay : bool, optional
        Set to false to receive raw video without skeleton overlay.
    """
    service = get_live_service()
    if not service.is_running():
        raise HTTPException(status_code=503, detail="No active session. POST /api/session/start first.")

    # Multi-camera: a camera_id naming a different camera serves its raw feed.
    raw_source = _resolve_camera_source(camera_id, service)
    if raw_source is not None:
        return StreamingResponse(
            _generate_raw_mjpeg(raw_source),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-cache"},
        )

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
