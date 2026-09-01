"""Health check utilities."""

import time
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_start_time: float = time.time()


def get_uptime() -> float:
    return time.time() - _start_time


def _check_database() -> dict:
    """Check SQLite database connectivity."""
    try:
        from app.core.database import get_connection
        t0 = time.time()
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {"status": "connected", "latency_ms": latency_ms}
    except Exception as e:
        logger.warning("Database health check failed: %s", e)
        return {"status": "disconnected", "latency_ms": 0}


def _check_disk() -> dict:
    """Check disk usage for key directories — resolves relative to project root."""
    # Find project root (parent of backend_api/)
    project_root = Path(__file__).resolve().parent.parent.parent
    result = {}
    for name, path in [("sessions", "sessions"), ("models", "models"), ("recordings", "recordings")]:
        try:
            total = 0
            dir_path = project_root / path
            if dir_path.is_dir():
                for f in dir_path.rglob("*"):  # recursive to catch .registry subdirs
                    if f.is_file():
                        total += f.stat().st_size
            result[name] = round(total / (1024 * 1024), 2)  # MB
        except Exception:
            result[name] = 0
    return result


def health_status() -> dict:
    db = _check_database()
    disk = _check_disk()
    uptime = get_uptime()
    return {
        "status": "healthy" if db["status"] == "connected" else "degraded",
        "app": "ErgoVigilance API",
        "version": "0.1.0",
        "uptime_seconds": round(uptime, 2),
        "uptime": _format_uptime(uptime),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database_status": db["status"],
        "db_latency_ms": db["latency_ms"],
        "disk_usage_mb": disk,
    }


def _format_uptime(seconds: float) -> str:
    """Human-readable uptime string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# --- Prometheus-compatible metrics ---
_request_count = 0
_request_errors = 0
_active_websockets = 0
_active_sessions = 0

def increment_requests():
    global _request_count
    _request_count += 1

def increment_errors():
    global _request_errors
    _request_errors += 1

def set_websocket_count(count: int):
    global _active_websockets
    _active_websockets = count

def set_session_count(count: int):
    global _active_sessions
    _active_sessions = count

def prometheus_metrics() -> str:
    """Generate Prometheus-format metrics text."""
    db = _check_database()
    disk = _check_disk()
    uptime = get_uptime()

    metrics = []
    metrics.append('# HELP ergovigilance_uptime_seconds Time since server start')
    metrics.append('# TYPE ergovigilance_uptime_seconds gauge')
    metrics.append(f'ergovigilance_uptime_seconds {uptime:.2f}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_requests_total Total HTTP requests')
    metrics.append('# TYPE ergovigilance_requests_total counter')
    metrics.append(f'ergovigilance_requests_total {_request_count}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_request_errors_total Total HTTP errors')
    metrics.append('# TYPE ergovigilance_request_errors_total counter')
    metrics.append(f'ergovigilance_request_errors_total {_request_errors}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_websockets_active Active WebSocket connections')
    metrics.append('# TYPE ergovigilance_websockets_active gauge')
    metrics.append(f'ergovigilance_websockets_active {_active_websockets}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_sessions_active Active monitoring sessions')
    metrics.append('# TYPE ergovigilance_sessions_active gauge')
    metrics.append(f'ergovigilance_sessions_active {_active_sessions}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_db_latency_ms Database query latency')
    metrics.append('# TYPE ergovigilance_db_latency_ms gauge')
    metrics.append(f'ergovigilance_db_latency_ms {db["latency_ms"]}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_disk_usage_bytes Disk usage per directory')
    metrics.append('# TYPE ergovigilance_disk_usage_bytes gauge')
    for name, mb in disk.items():
        metrics.append(f'ergovigilance_disk_usage_bytes{{dir="{name}"}} {mb * 1024 * 1024}')
    metrics.append('')
    metrics.append('# HELP ergovigilance_db_connected Database connection status')
    metrics.append('# TYPE ergovigilance_db_connected gauge')
    metrics.append(f'ergovigilance_db_connected {1 if db["status"] == "connected" else 0}')

    return '\n'.join(metrics)
