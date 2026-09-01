"""Structured JSON Logging for Enterprise Log Aggregation.

Outputs logs in JSON format compatible with:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Datadog
- Splunk
- CloudWatch Logs
- Loki/Grafana

Usage:
    from app.core.structured_logging import setup_logging
    setup_logging()  # Call once at startup
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request context if available
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "extra_data") and record.extra_data:
            log_entry["extra"] = record.extra_data

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"{timestamp} | {color}{record.levelname:8}{reset} | "
            f"{record.name:30} | {record.getMessage()}"
        )

        if record.exc_info and record.exc_info[1]:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    level: str = None,
    json_format: bool = None,
    log_file: str = None,
):
    """Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Default from LOG_LEVEL env.
        json_format: Use JSON format. Default: True in production, False in dev.
        log_file: Optional file path to write logs to.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    if json_format is None:
        json_format = os.getenv("LOG_FORMAT", "json").lower() == "json"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)

    # Suppress noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info(
        "Logging configured: level=%s format=%s",
        level,
        "json" if json_format else "text",
    )


class RequestLoggingMiddleware:
    """Logs every HTTP request with timing and status code."""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("http.access")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        import time
        start = time.time()
        method = scope.get("method", "?")
        path = scope.get("path", "?")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status = message.get("status", 0)
                duration = round((time.time() - start) * 1000, 1)

                # Track SLA metrics
                try:
                    from app.core.sla_monitor import sla_monitor
                    sla_monitor.record_request(
                        success=status < 500,
                        response_time_ms=duration,
                    )
                except ImportError:
                    pass

                # Skip health check noise
                if path not in ("/healthz", "/readyz", "/metrics"):
                    extra = {
                        "method": method,
                        "path": path,
                        "status_code": status,
                        "duration_ms": duration,
                    }
                    if status >= 500:
                        self.logger.error("%s %s -> %s (%sms)", method, path, status, duration, extra=extra)
                    elif status >= 400:
                        self.logger.warning("%s %s -> %s (%sms)", method, path, status, duration, extra=extra)
                    else:
                        self.logger.info("%s %s -> %s (%sms)", method, path, status, duration, extra=extra)

            await send(message)

        await self.app(scope, receive, send_wrapper)
