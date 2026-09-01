"""Auto-recovery system for ErgoVigilance services.

Monitors health of dependent services (Ollama, PostgreSQL, YOLO Cloud Core)
and attempts automatic recovery when failures are detected.

Configurable via environment:
- AUTO_RECOVERY_ENABLED: enable/disable (default true)
- AUTO_RECOVERY_CHECK_INTERVAL: seconds between checks (default 30)
- AUTO_RECOVERY_MAX_RETRIES: max restart attempts before giving up (default 3)
- AUTO_RECOVERY_COOLDOWN: seconds between restart attempts (default 60)

Usage in lifespan:
    from app.core.auto_recovery import recovery_monitor
    recovery_monitor.start()
    # ... app runs ...
    recovery_monitor.stop()
"""

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)

AUTO_RECOVERY_ENABLED = os.getenv("AUTO_RECOVERY_ENABLED", "true").lower() == "true"
CHECK_INTERVAL = int(os.getenv("AUTO_RECOVERY_CHECK_INTERVAL", "30"))
MAX_RETRIES = int(os.getenv("AUTO_RECOVERY_MAX_RETRIES", "3"))
COOLDOWN = int(os.getenv("AUTO_RECOVERY_COOLDOWN", "60"))


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    RECOVERING = "recovering"


@dataclass
class ServiceHealth:
    """Health status of a monitored service."""
    name: str
    status: ServiceStatus = ServiceStatus.HEALTHY
    last_check: float = 0.0
    last_healthy: float = 0.0
    consecutive_failures: int = 0
    restart_attempts: int = 0
    last_restart: float = 0.0
    error_message: str = ""
    latency_ms: float = 0.0


class RecoveryMonitor:
    """Monitor service health and attempt auto-recovery."""

    def __init__(self):
        self.services: dict[str, ServiceHealth] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._health_checks: dict[str, Callable] = {}
        self._restart_handlers: dict[str, Callable] = {}

    def register_service(
        self,
        name: str,
        health_check: Callable,
        restart_handler: Optional[Callable] = None,
    ) -> None:
        """Register a service for monitoring."""
        self.services[name] = ServiceHealth(name=name)
        self._health_checks[name] = health_check
        if restart_handler:
            self._restart_handlers[name] = restart_handler
        logger.info("Registered service for auto-recovery: %s", name)

    async def _check_service(self, name: str) -> ServiceHealth:
        """Check health of a single service."""
        health = self.services[name]
        check_fn = self._health_checks.get(name)

        if not check_fn:
            health.status = ServiceStatus.DOWN
            health.error_message = "No health check registered"
            return health

        start = time.time()
        try:
            result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
            health.latency_ms = (time.time() - start) * 1000
            health.last_check = time.time()
            health.error_message = ""

            if result is True or (isinstance(result, dict) and result.get("healthy", False)):
                health.status = ServiceStatus.HEALTHY
                health.last_healthy = time.time()
                health.consecutive_failures = 0
            elif isinstance(result, dict) and result.get("degraded"):
                health.status = ServiceStatus.DEGRADED
                health.consecutive_failures = 0
            else:
                health.consecutive_failures += 1
                health.status = ServiceStatus.DOWN
                health.error_message = str(result) if result else "Health check failed"

        except Exception as e:
            health.latency_ms = (time.time() - start) * 1000
            health.last_check = time.time()
            health.consecutive_failures += 1
            health.status = ServiceStatus.DOWN
            health.error_message = str(e)

        return health

    async def _attempt_recovery(self, name: str) -> bool:
        """Attempt to restart a failed service."""
        health = self.services[name]
        restart_fn = self._restart_handlers.get(name)

        if not restart_fn:
            logger.warning("No restart handler for %s, cannot recover", name)
            return False

        # Check cooldown
        if time.time() - health.last_restart < COOLDOWN:
            remaining = COOLDOWN - (time.time() - health.last_restart)
            logger.info("Recovery cooldown for %s: %.0fs remaining", name, remaining)
            return False

        # Check max retries
        if health.restart_attempts >= MAX_RETRIES:
            logger.error(
                "Max restart attempts (%d) reached for %s. Manual intervention required.",
                MAX_RETRIES, name
            )
            health.status = ServiceStatus.DOWN
            return False

        health.status = ServiceStatus.RECOVERING
        health.restart_attempts += 1
        health.last_restart = time.time()

        logger.info(
            "Attempting recovery for %s (attempt %d/%d)",
            name, health.restart_attempts, MAX_RETRIES
        )

        try:
            result = await restart_fn() if asyncio.iscoroutinefunction(restart_fn) else restart_fn()
            if result is True:
                logger.info("Successfully recovered %s", name)
                health.status = ServiceStatus.HEALTHY
                health.consecutive_failures = 0
                health.restart_attempts = 0
                return True
            else:
                logger.warning("Recovery attempt for %s returned: %s", name, result)
                health.status = ServiceStatus.DOWN
                return False
        except Exception as e:
            logger.error("Recovery attempt for %s failed: %s", name, e)
            health.status = ServiceStatus.DOWN
            return False

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Auto-recovery monitor started (interval: %ds)", CHECK_INTERVAL)

        while self._running:
            try:
                for name in list(self.services.keys()):
                    health = await self._check_service(name)

                    if health.status == ServiceStatus.DOWN and health.consecutive_failures >= 2:
                        logger.warning(
                            "Service %s has failed %d consecutive checks, attempting recovery",
                            name, health.consecutive_failures
                        )
                        await self._attempt_recovery(name)

            except Exception as e:
                logger.error("Error in recovery monitor loop: %s", e)

            await asyncio.sleep(CHECK_INTERVAL)

    def start(self) -> None:
        """Start the monitoring loop in the background."""
        if not AUTO_RECOVERY_ENABLED:
            logger.info("Auto-recovery is disabled (AUTO_RECOVERY_ENABLED=false)")
            return

        if self._running:
            return

        self._running = True
        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            # No event loop running, will start when one is available
            logger.info("No event loop available, recovery monitor will start with app lifespan")

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("Auto-recovery monitor stopped")

    def get_status(self) -> dict:
        """Get status of all monitored services."""
        return {
            "enabled": AUTO_RECOVERY_ENABLED,
            "check_interval_seconds": CHECK_INTERVAL,
            "services": {
                name: {
                    "status": health.status.value,
                    "latency_ms": round(health.latency_ms, 1),
                    "consecutive_failures": health.consecutive_failures,
                    "restart_attempts": health.restart_attempts,
                    "error": health.error_message,
                    "last_healthy": health.last_healthy,
                }
                for name, health in self.services.items()
            }
        }


# Singleton instance
recovery_monitor = RecoveryMonitor()
