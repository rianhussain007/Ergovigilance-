"""WebSocket connection manager.

Tracks live WebSocket connections and drops stale ones. Live updates are
currently pushed by per-connection polling loops in ``app/api/websocket.py``
(each connection receives a fresh payload every 2–3s); ``broadcast()`` is kept
for event-driven fan-out but is not yet wired to the event bus.
"""

import json
import logging
from typing import Set, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time dashboard updates."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WebSocket connected — %d active", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.info("WebSocket disconnected — %d active", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        stale: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self._connections.discard(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


dashboard_manager = ConnectionManager()
alert_manager = ConnectionManager()
camera_manager = ConnectionManager()
