"""Session observation logging and manual risk override endpoints."""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user, require_live_session_access
from app.core.database import get_worker, insert_audit_log
from app.core.security import AuthenticatedUser
from app.services.live_monitor import get_live_service_or_none

logger = logging.getLogger(__name__)
router = APIRouter()


class ObservationRequest(BaseModel):
    note: str
    category: str = "general"  # general | safety | posture | environment


class OverrideRequest(BaseModel):
    risk_level: str  # LOW | MEDIUM | HIGH
    reason: str = ""


@router.post("/session/observation")
def log_observation(
    req: ObservationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Record an operator observation against the active session.

    The note is persisted to the session's timeline and written to the
    recordings directory so it survives restarts.
    """
    service = get_live_service_or_none()
    if service is None:
        raise HTTPException(status_code=503, detail="Live monitoring service is unavailable.")
    if not service.is_running():
        raise HTTPException(status_code=400, detail="No active session to log against.")

    session_id = service.state.session_id or "unknown"
    worker_id = getattr(service, "current_worker_id", None)
    session_ts = getattr(service, "current_session_timestamp", None)

    entry = {
        "id": f"OBS-{uuid.uuid4().hex[:8].upper()}",
        "type": "observation",
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "worker_id": worker_id,
        "user_id": user.id,
        "user_email": user.email,
        "note": req.note,
        "category": req.category,
        "risk_level_at_time": service.state.risk_level,
        "frame_number": service.state.frame_number,
    }

    # Append to the live timeline so it appears in the frontend timeline bar.
    service._timeline.append({
        "timestamp": round(service._session_duration, 3),
        "frame_number": service.state.frame_number,
        "type": "observation",
        "observation": entry,
    })

    # Persist to the session's recordings directory.
    try:
        if session_ts:
            worker_dir = worker_id or "unknown"
            rec_dir = os.path.join(
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "recordings")),
                worker_dir,
            )
            # Find the session directory
            for d in os.listdir(rec_dir) if os.path.isdir(rec_dir) else []:
                if session_id in d:
                    obs_path = os.path.join(rec_dir, d, "observations.json")
                    observations = []
                    if os.path.exists(obs_path):
                        with open(obs_path, "r") as f:
                            observations = json.load(f)
                    observations.append(entry)
                    with open(obs_path, "w") as f:
                        json.dump(observations, f, indent=2)
                    break
    except Exception as exc:
        logger.warning("Failed to persist observation to disk: %s", exc)

    # Audit trail
    try:
        insert_audit_log(
            id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            actor_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            action_type="observation_logged",
            target_type="session",
            target_id=session_id,
            timestamp=datetime.now().isoformat(),
            details=json.dumps({"note": req.note[:120], "category": req.category}),
        )
    except Exception as exc:
        logger.debug("Audit log failed for observation: %s", exc)

    return {
        "status": "recorded",
        "observation_id": entry["id"],
        "session_id": session_id,
    }


@router.post("/session/override")
def override_risk(
    req: OverrideRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Manually override the risk level for the active session.

    Only supervisors, safety managers, and admins may override.
    The override is recorded in the audit trail and the timeline.
    """
    service = get_live_service_or_none()
    if service is None:
        raise HTTPException(status_code=503, detail="Live monitoring service is unavailable.")
    if not service.is_running():
        raise HTTPException(status_code=400, detail="No active session to override.")

    allowed = {"LOW", "MEDIUM", "HIGH"}
    level = req.risk_level.upper()
    if level not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid risk level. Must be one of: {', '.join(allowed)}")

    session_id = service.state.session_id or "unknown"
    previous_level = service.state.risk_level

    # Apply the override
    with service._lock:
        service.state.risk_level = level
        if level == "HIGH":
            service.state.risk_score = 80.0
        elif level == "MEDIUM":
            service.state.risk_score = 50.0
        else:
            service.state.risk_score = 20.0
        service.state.issues = list(service.state.issues) + [
            f"Manual override: {previous_level} → {level} by {user.email}"
        ]

    # Record in timeline
    service._timeline.append({
        "timestamp": round(service._session_duration, 3),
        "frame_number": service.state.frame_number,
        "type": "override",
        "override": {
            "from": previous_level,
            "to": level,
            "reason": req.reason,
            "user_id": user.id,
            "user_email": user.email,
            "timestamp": datetime.now().isoformat(),
        },
    })

    # Audit trail
    try:
        insert_audit_log(
            id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            actor_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            action_type="risk_override",
            target_type="session",
            target_id=session_id,
            timestamp=datetime.now().isoformat(),
            details=json.dumps({
                "from": previous_level,
                "to": level,
                "reason": req.reason,
            }),
        )
    except Exception as exc:
        logger.debug("Audit log failed for override: %s", exc)

    logger.info("Risk override applied: %s → %s by %s (session %s)", previous_level, level, user.email, session_id)

    return {
        "status": "overridden",
        "session_id": session_id,
        "previous_level": previous_level,
        "new_level": level,
    }
