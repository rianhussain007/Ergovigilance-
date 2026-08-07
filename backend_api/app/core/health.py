"""Health check utilities."""

import time
import logging

logger = logging.getLogger(__name__)

_start_time: float = time.time()


def get_uptime() -> float:
    return time.time() - _start_time


def health_status() -> dict:
    return {
        "status": "healthy",
        "app": "ErgoVigilance API",
        "version": "0.1.0",
        "uptime_seconds": round(get_uptime(), 2),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
