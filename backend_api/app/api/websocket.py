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


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """Live dashboard updates — risk changes, features, issues."""
    await dashboard_manager.connect(websocket)
    try:
        while True:
            service = get_live_service_or_none()
            if service is not None and service.is_running():
                await websocket.send_json({
                    "type": "dashboard_update",
                    "data": service.get_ws_payload(),
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
                payload = service.get_ws_payload()
                await websocket.send_json({
                    "type": "camera_update",
                    "data": {
                        "camera_status": payload["camera_status"],
                        "fps": payload["fps"],
                        "frame_width": payload["frame_width"],
                        "frame_height": payload["frame_height"],
                        "person_detected": payload["person_detected"],
                        "inference_latency_ms": payload["inference_latency_ms"],
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
