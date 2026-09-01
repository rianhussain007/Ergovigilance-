"""Circuit Breaker Pattern for External Service Calls.

Prevents cascading failures when external services (Ollama, SMTP, webhooks)
are unavailable. States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are rejected immediately
- HALF_OPEN: Testing if service recovered, limited requests pass through

Usage:
    breaker = CircuitBreaker("ollama", failure_threshold=5, recovery_timeout=30)
    
    @breaker.protect
    async def call_ollama():
        ...
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for protecting external service calls."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Check if we should transition from OPEN to HALF_OPEN."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit breaker '%s' transitioning to HALF_OPEN", self.name)
        return self._state

    def record_success(self):
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info("Circuit breaker '%s' recovered — CLOSED", self.name)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker '%s' failed in HALF_OPEN — reopening", self.name)
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker '%s' OPEN after %d failures",
                self.name,
                self._failure_count,
            )

    def is_available(self) -> bool:
        """Check if the service is available (not in OPEN state)."""
        return self.state != CircuitState.OPEN

    def protect(self, func: Callable) -> Callable:
        """Decorator to protect a function with the circuit breaker."""
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not self.is_available():
                raise CircuitBreakerOpenError(
                    f"Service '{self.name}' is unavailable (circuit breaker OPEN). "
                    f"Retry after {self.recovery_timeout}s."
                )

            try:
                if self._state == CircuitState.HALF_OPEN:
                    self._half_open_calls += 1

                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except CircuitBreakerOpenError:
                raise
            except Exception as e:
                self.record_failure()
                raise

        return wrapper

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is in OPEN state."""
    pass


# --- Global circuit breakers for external services ---

ollama_breaker = CircuitBreaker(
    "ollama",
    failure_threshold=3,
    recovery_timeout=60.0,
)

smtp_breaker = CircuitBreaker(
    "smtp",
    failure_threshold=5,
    recovery_timeout=120.0,
)

webhook_breaker = CircuitBreaker(
    "webhook",
    failure_threshold=3,
    recovery_timeout=30.0,
)
