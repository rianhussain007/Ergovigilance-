"""WebSocket endpoint handlers — live data streaming."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import dashboard_manager, alert_manager, camera_manager
from app.services.live_monitor import get_live_service_or_none

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_state(state) -> dict:
    """Serialize LiveState to a JSON-safe dict."""
    return {
        "session_active": state.session_active,
        "session_id": state.session_id,
        "risk_level": state.risk_level,
        "risk_score": state.risk_score,
        "confidence": state.confidence,
        "person_detected": state.person_detected,
        "task_name": state.task_name,
        "task_confidence": state.task_confidence,
        "task_duration_seconds": state.task_duration_seconds,
        "issues": state.issues,
        "worker_recommendation": state.worker_recommendation,
        "supervisor_recommendation": state.supervisor_recommendation,
        "fps": state.fps,
        "inference_latency_ms": state.inference_latency_ms,
        "timestamp": state.timestamp,
        "camera_status": state.camera_status,
        "frame_width": state.frame_width,
        "frame_height": state.frame_height,
        "features": state.features,
    }


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """Live dashboard updates — risk changes, features, issues."""
    await dashboard_manager.connect(websocket)
    try:
        while True:
            service = get_live_service_or_none()
            if service is not None and service.is_running():
                state = service.get_state_snapshot()
                await websocket.send_json({
                    "type": "dashboard_update",
                    "data": _serialize_state(state),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                await websocket.send_json({
                    "type": "dashboard_update",
                    "data": {"session_active": False},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        dashboard_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Dashboard WS error: %s", e)
        dashboard_manager.disconnect(websocket)


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """Live alert notifications."""
    await alert_manager.connect(websocket)
    last_alert_count = 0
    try:
        while True:
            service = get_live_service_or_none()
            if service is not None and service.is_running():
                engine = service.alert_engine
                active = engine.get_active_alerts()
                if len(active) != last_alert_count:
                    last_alert_count = len(active)
                    await websocket.send_json({
                        "type": "alerts_update",
                        "data": {
                            "active_count": len(active),
                            "alerts": [a.to_dict() for a in active],
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Alerts WS error: %s", e)
        alert_manager.disconnect(websocket)


@router.websocket("/ws/camera")
async def ws_camera(websocket: WebSocket):
    """Live camera frame updates and status."""
    await camera_manager.connect(websocket)
    try:
        while True:
            service = get_live_service_or_none()
            if service is not None and service.is_running():
                state = service.get_state_snapshot()
                await websocket.send_json({
                    "type": "camera_update",
                    "data": {
                        "camera_status": state.camera_status,
                        "fps": state.fps,
                        "frame_width": state.frame_width,
                        "frame_height": state.frame_height,
                        "person_detected": state.person_detected,
                        "inference_latency_ms": state.inference_latency_ms,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                await websocket.send_json({
                    "type": "camera_update",
                    "data": {"camera_status": "disconnected"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        camera_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Camera WS error: %s", e)
        camera_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Camera WS error: %s", e)
        camera_manager.disconnect(websocket)
