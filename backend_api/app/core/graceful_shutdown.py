"""Graceful shutdown manager for FastAPI.

Ensures in-flight requests complete before the server stops.
Tracks active connections and waits for them to finish.

Usage in lifespan:
    from app.core.graceful_shutdown import shutdown_manager

    @asynccontextmanager
    async def lifespan(app):
        yield
        await shutdown_manager.drain()
"""

import asyncio
import logging
import signal
import time
from typing import Optional

logger = logging.getLogger(__name__)


class GracefulShutdownManager:
    """Track active connections and drain them on shutdown."""

    def __init__(self, drain_timeout: float = 30.0):
        self.drain_timeout = drain_timeout
        self._active_connections = 0
        self._shutdown_event = asyncio.Event()
        self._drain_complete = asyncio.Event()
        self._drain_complete.set()  # Initially complete (no connections)

    @property
    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()

    @property
    def active_count(self) -> int:
        return self._active_connections

    def connection_started(self) -> None:
        """Call when a new connection/request starts."""
        self._active_connections += 1
        self._drain_complete.clear()

    def connection_finished(self) -> None:
        """Call when a connection/request completes."""
        self._active_connections = max(0, self._active_connections - 1)
        if self._active_connections == 0 and self._shutdown_event.is_set():
            self._drain_complete.set()

    async def drain(self) -> None:
        """Wait for all active connections to complete, up to drain_timeout."""
        if self._active_connections == 0:
            logger.info("No active connections, shutting down immediately")
            return

        self._shutdown_event.set()
        logger.info(
            "Draining %d active connection(s) (timeout: %.0fs)",
            self._active_connections, self.drain_timeout
        )

        start = time.time()
        try:
            await asyncio.wait_for(
                self._drain_complete.wait(),
                timeout=self.drain_timeout
            )
            elapsed = time.time() - start
            logger.info("All connections drained in %.2fs", elapsed)
        except asyncio.TimeoutError:
            remaining = self._active_connections
            logger.warning(
                "Drain timeout reached with %d connection(s) still active. "
                "Forcing shutdown.",
                remaining
            )

    def get_status(self) -> dict:
        """Get current shutdown manager status."""
        return {
            "active_connections": self._active_connections,
            "is_shutting_down": self.is_shutting_down,
            "drain_timeout_seconds": self.drain_timeout,
        }


# Singleton instance
shutdown_manager = GracefulShutdownManager()
