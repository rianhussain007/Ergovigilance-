"""Session lifecycle endpoints — start/stop the live pipeline."""

import logging
import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import ELEVATED_ROLES, get_current_user, require_live_session_access
from app.core.database import get_worker, insert_audit_log
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service
from app.schemas.api import SessionActionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class SessionStartRequest(BaseModel):
    camera_index: int = 0
    worker_id: str
    camera_id: str | None = None


@router.post("/session/start", response_model=SessionActionResponse)
def start_session(
    req: SessionStartRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Open camera and start the CV pipeline."""
    service = get_live_service()
    if service.is_running():
        owner_id = getattr(service, "current_created_by_user_id", None)
        if owner_id is not None and owner_id != user.id and user.role not in ELEVATED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Another user's session is active. Ask a supervisor to stop it.",
            )
        service.stop_session()
        logger.info("Force-stopped stale session before starting new one (user=%s)", user.id)
    if get_worker(req.worker_id) is None:
        raise HTTPException(status_code=400, detail=f"Unknown worker_id: {req.worker_id}")

    try:
        # camera_id may be a numeric index, a configured CAMERA_SOURCES id, or
        # an RTSP URL — resolution happens in start_session() so USB and IP
        # cameras share one code path.
        session_id = service.start_session(
            camera_index=req.camera_index,
            worker_id=req.worker_id,
            created_by_user_id=user.id,
            camera_id=req.camera_id,
        )

        # Log to audit trail
        worker = get_worker(req.worker_id)
        details = json.dumps({"worker_id": req.worker_id, "worker_name": worker["name"] if worker else None})
        insert_audit_log(
            id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            actor_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            action_type="session_started",
            target_type="session",
            target_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details,
        )

        logger.info("Session started: %s", session_id)
        return SessionActionResponse(
            id=session_id,
            status="started",
            message="Session started successfully. Camera and pipeline running.",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/stop", response_model=SessionActionResponse)
def stop_session(user: AuthenticatedUser = Depends(get_current_user)):
    """Stop the pipeline, save session data, release camera."""
    service = get_live_service()
    if not service.is_running():
        return SessionActionResponse(
            id="",
            status="noop",
            message="No active session to stop.",
        )

    owner_id = getattr(service, "current_created_by_user_id", None)
    if owner_id is not None and owner_id != user.id and user.role not in ELEVATED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot stop another user's session. Ask a supervisor.",
        )

    session_id = service.state.session_id or "unknown"
    worker_id = getattr(service, "current_worker_id", None)

    result = service.stop_session()
    logger.info("Session stopped by %s: %s", user.id, session_id)

    # Log to audit trail
    details = json.dumps({"worker_id": worker_id})
    insert_audit_log(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action_type="session_stopped",
        target_type="session",
        target_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details,
    )

    return SessionActionResponse(
        id=session_id,
        status="ended",
        message=f"Session ended. Summary: {result.get('saved_path', 'not saved')}",
    )


@router.get("/session/status")
async def session_status(user: AuthenticatedUser = Depends(get_current_user)):
    """Check if a live session is currently active."""
    service = get_live_service()
    require_live_session_access(user, service)
    state = service.get_state_snapshot()
    return {
        "active": state.session_active,
        "session_id": state.session_id,
        "worker_id": getattr(service, "current_worker_id", None),
        "created_by_user_id": getattr(service, "current_created_by_user_id", None),
        "camera_id": getattr(service, "current_camera_id", None),
        "person_detected": state.person_detected,
        "risk_level": state.risk_level,
        "fps": state.fps,
        "task": state.task_name,
        "timestamp": state.timestamp,
    }
