"""WebSocket connection manager with heartbeat support.

Tracks live WebSocket connections, drops stale ones, and sends periodic
heartbeats to keep connections alive through proxies and load balancers.
"""

import asyncio
import json
import logging
import time
from typing import Set, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # seconds between heartbeats
STALE_TIMEOUT = 45  # seconds before considering a connection stale


class ConnectionManager:
    """Manages WebSocket connections for real-time dashboard updates."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._last_seen: dict[WebSocket, float] = {}
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        self._last_seen[websocket] = time.time()
        logger.info("WebSocket connected — %d active", len(self._connections))

        # Start heartbeat loop if not running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        self._last_seen.pop(websocket, None)
        logger.info("WebSocket disconnected — %d active", len(self._connections))

    async def _heartbeat_loop(self) -> None:
        """Send periodic pings and clean up stale connections."""
        while self._connections:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                stale: set[WebSocket] = set()
                now = time.time()

                for ws in list(self._connections):
                    try:
                        # Send ping (client should respond with pong)
                        await ws.send_json({"type": "ping", "ts": now})
                        self._last_seen[ws] = now
                    except Exception:
                        stale.add(ws)

                # Remove stale connections
                for ws in stale:
                    self.disconnect(ws)
                    logger.info("Cleaned stale WebSocket connection")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: %s", e)
                await asyncio.sleep(HEARTBEAT_INTERVAL)

    def pong_received(self, websocket: WebSocket) -> None:
        """Update last-seen timestamp when client responds to ping."""
        self._last_seen[websocket] = time.time()

    async def broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        stale: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
                self._last_seen[ws] = time.time()
            except Exception:
                stale.add(ws)
        for ws in stale:
            self.disconnect(ws)

    def get_status(self) -> dict:
        """Get connection manager status."""
        return {
            "active_connections": len(self._connections),
            "heartbeat_interval": HEARTBEAT_INTERVAL,
            "stale_timeout": STALE_TIMEOUT,
        }

    @property
    def active_count(self) -> int:
        return len(self._connections)


dashboard_manager = ConnectionManager()
alert_manager = ConnectionManager()
camera_manager = ConnectionManager()
