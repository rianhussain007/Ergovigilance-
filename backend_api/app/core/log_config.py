"""Production logging configuration with rotation and structured output.

Provides:
- Rotating file handlers (prevent disk exhaustion)
- Structured JSON logging for log aggregation
- Separate log files for different concerns
- Log level filtering per module

Configurable via environment:
- LOG_DIR: directory for log files (default ./logs)
- LOG_MAX_SIZE_MB: max size per log file (default 50)
- LOG_BACKUP_COUNT: number of backup files (default 10)
- LOG_LEVEL: global log level (default INFO)
- LOG_JSON_FORMAT: use JSON format (default true in production)

Usage:
    from app.core.log_config import setup_production_logging
    setup_production_logging()
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_MAX_SIZE_MB = int(os.getenv("LOG_MAX_SIZE_MB", "50"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "10"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_JSON_FORMAT = os.getenv("LOG_JSON_FORMAT", "true").lower() == "true"


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data

        return json.dumps(log_entry, default=str)


class HumanReadableFormatter(logging.Formatter):
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
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        return (
            f"{color}{timestamp} {record.levelname:8s}{self.RESET} "
            f"{record.name}: {record.getMessage()}"
        )


def setup_production_logging() -> None:
    """Configure production logging with rotation and structured output."""
    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    if LOG_JSON_FORMAT:
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()

    # ── Console handler ──────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ── Application log file (rotating) ──────────────────
    app_log = LOG_DIR / "app.log"
    app_handler = logging.handlers.RotatingFileHandler(
        app_log,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    # ── Error log file (errors only) ─────────────────────
    error_log = LOG_DIR / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # ── Access log (requests) ────────────────────────────
    access_log = LOG_DIR / "access.log"
    access_handler = logging.handlers.RotatingFileHandler(
        access_log,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(formatter)

    # Attach to uvicorn access logger
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addHandler(access_handler)

    # ── Silence noisy loggers ────────────────────────────
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    logging.info(
        "Production logging configured: level=%s json=%s dir=%s",
        LOG_LEVEL, LOG_JSON_FORMAT, LOG_DIR
    )


def get_log_stats() -> dict:
    """Get logging statistics."""
    stats = {}
    for name in ["app.log", "error.log", "access.log"]:
        path = LOG_DIR / name
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            stats[name] = {
                "size_mb": round(size_mb, 2),
                "path": str(path),
            }
        else:
            stats[name] = {"size_mb": 0, "path": str(path)}

    return {
        "log_dir": str(LOG_DIR),
        "level": LOG_LEVEL,
        "json_format": LOG_JSON_FORMAT,
        "files": stats,
    }
