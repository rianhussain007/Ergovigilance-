"""Immutable audit logging for SOC2 compliance.

Provides append-only, tamper-evident audit logs with:
- HMAC-SHA256 chain integrity (each entry hashes the previous)
- Structured JSON format for machine parsing
- File-based storage with automatic rotation
- Query API for compliance exports

Configurable via environment:
- AUDIT_LOG_DIR: directory for audit logs (default ./audit_logs)
- AUDIT_LOG_MAX_SIZE_MB: max size per log file (default 50)
- AUDIT_LOG_RETENTION_DAYS: days to keep logs (default 365)
- AUDIT_HMAC_KEY: explicit chain key (optional — see below)
- AUDIT_HMAC_KEY_FILE: where an unset key is auto-provisioned
  (default: next to AUTH_DB_PATH, else backend_api/data/audit_hmac.key)

Chain key resolution (P0-8): explicit AUDIT_HMAC_KEY wins; otherwise the key
is loaded from / generated into the key file so verification survives
restarts. With DEBUG=false an unwritable key file refuses service instead of
silently degrading to an ephemeral key.

Usage:
    from app.core.audit_log import audit_logger
    audit_logger.log("user_login", user_id=1, email="admin@example.com")
    entries = audit_logger.query(event_type="user_login", since_hours=24)
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_DIR = Path(os.getenv("AUDIT_LOG_DIR", "./audit_logs"))
AUDIT_LOG_MAX_SIZE_MB = int(os.getenv("AUDIT_LOG_MAX_SIZE_MB", "50"))
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "365"))


def _default_key_file() -> Path:
    """Key file location: beside the auth DB (persistent volume in containers)."""
    from app.core.config import settings

    if settings.AUTH_DB_PATH:
        return Path(settings.AUTH_DB_PATH).with_name("audit_hmac.key")
    return Path(__file__).resolve().parents[2] / "data" / "audit_hmac.key"


def _resolve_hmac_key() -> str:
    """Resolve the chain key: env > key file > auto-provision (dev) / fail closed.

    Stateless — every call re-reads env/file so tests and ops can rotate the
    key source; ``_hmac_key`` caches the result for the hot path.
    """
    env_key = os.getenv("AUDIT_HMAC_KEY", "").strip()
    if env_key:
        return env_key
    key_file = Path(os.getenv("AUDIT_HMAC_KEY_FILE") or _default_key_file())
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        key = secrets.token_hex(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="utf-8")
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        logger.warning(
            "Audit HMAC key generated and persisted to %s — back it up: "
            "without it, existing audit chains cannot be verified.",
            key_file,
        )
        return key
    except OSError as exc:
        if os.getenv("DEBUG", "false").lower() == "true":
            logger.warning(
                "Audit HMAC key file %s unusable (%s) — falling back to an "
                "ephemeral per-process key (chain breaks across restarts). "
                "Set AUDIT_HMAC_KEY to make it stable.",
                key_file,
                exc,
            )
            return secrets.token_hex(32)
        raise RuntimeError(
            f"AUDIT_HMAC_KEY is not set and the key file {key_file} could not "
            f"be read or written ({exc}). Set AUDIT_HMAC_KEY (>=32 chars) or "
            "fix the permissions — refusing to run with an unverifiable audit chain."
        ) from exc


_HMAC_KEY_CACHE: Optional[str] = None


def _hmac_key() -> str:
    """Cached chain key (resolved once per process)."""
    global _HMAC_KEY_CACHE
    if _HMAC_KEY_CACHE is None:
        _HMAC_KEY_CACHE = _resolve_hmac_key()
    return _HMAC_KEY_CACHE


def destroy_hmac_key() -> bool:
    """Destroy the provisioned key file (erasure procedure step 3).

    Removes the key file so existing chains become unverifiable, then
    clears the in-process cache: the next audited event re-resolves (env
    key if set, else a freshly provisioned key = rotation). An
    env-supplied key has no file to destroy — returns False and leaves
    the running process untouched. Never raises for a missing file.
    """
    global _HMAC_KEY_CACHE
    if os.getenv("AUDIT_HMAC_KEY", "").strip():
        return False
    key_file = Path(os.getenv("AUDIT_HMAC_KEY_FILE") or _default_key_file())
    try:
        key_file.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("Could not destroy audit HMAC key file %s: %s", key_file, exc)
        return False
    _HMAC_KEY_CACHE = None
    return True


def ensure_hmac_key() -> str:
    """Fail-fast entry point for app startup (raises RuntimeError when unusable)."""
    return _hmac_key()


def _hmac_chain(previous_hash: str, entry_data: str) -> str:
    """Generate HMAC-SHA256 hash linking this entry to the previous one."""
    message = f"{previous_hash}:{entry_data}".encode("utf-8")
    return hmac.new(_hmac_key().encode("utf-8"), message, hashlib.sha256).hexdigest()


class AuditLogger:
    """Append-only, tamper-evident audit logger."""

    def __init__(self, log_dir: Path = AUDIT_LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file = None
        self._previous_hash = "0" * 64  # Genesis hash

    def _get_log_file(self) -> Path:
        """Get current log file, rotating if needed."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{today}.jsonl"

        # Rotate if too large
        if log_file.exists() and log_file.stat().st_size > AUDIT_LOG_MAX_SIZE_MB * 1024 * 1024:
            counter = 1
            while True:
                rotated = self.log_dir / f"audit_{today}_{counter}.jsonl"
                if not rotated.exists():
                    log_file.rename(rotated)
                    break
                counter += 1

        return log_file

    def _load_previous_hash(self, log_file: Path) -> str:
        """Load the hash of the last entry in the file."""
        if not log_file.exists():
            return "0" * 64

        last_hash = "0" * 64
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            last_hash = entry.get("_hash", last_hash)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error("Failed to load previous hash: %s", e)

        return last_hash

    def log(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "info",
    ) -> dict:
        """Append an audit log entry with chain integrity."""
        log_file = self._get_log_file()
        self._previous_hash = self._load_previous_hash(log_file)

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "email": email,
            "role": role,
            "ip_address": ip_address,
            "details": details or {},
        }

        # Create chain hash
        entry_data = json.dumps(entry, sort_keys=True, default=str)
        chain_hash = _hmac_chain(self._previous_hash, entry_data)
        entry["_hash"] = chain_hash
        entry["_prev_hash"] = self._previous_hash

        # Append to file
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            self._previous_hash = chain_hash
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)

        return entry

    def query(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[int] = None,
        since_hours: Optional[int] = None,
        severity: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Query audit log entries with optional filters."""
        cutoff = time.time() - (since_hours * 3600) if since_hours else 0
        results = []

        for log_file in sorted(self.log_dir.glob("audit_*.jsonl"), reverse=True):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Apply filters
                        if event_type and entry.get("event_type") != event_type:
                            continue
                        if user_id and entry.get("user_id") != user_id:
                            continue
                        if severity and entry.get("severity") != severity:
                            continue
                        if cutoff:
                            try:
                                entry_time = datetime.fromisoformat(
                                    entry["timestamp"].replace("Z", "+00:00")
                                ).timestamp()
                                if entry_time < cutoff:
                                    continue
                            except (KeyError, ValueError):
                                continue

                        results.append(entry)

                        if len(results) >= limit:
                            return results
            except Exception as e:
                logger.error("Error reading audit log %s: %s", log_file, e)

        return results

    def verify_integrity(self, log_file: Optional[Path] = None) -> dict:
        """Verify the integrity of an audit log file by checking the hash chain."""
        if log_file is None:
            log_file = self._get_log_file()

        if not log_file.exists():
            return {"valid": True, "entries": 0, "message": "No log file"}

        entries = 0
        broken = 0
        prev_hash = "0" * 64

        with open(log_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    broken += 1
                    continue

                entries += 1

                # Verify chain link
                if entry.get("_prev_hash") != prev_hash:
                    broken += 1
                    logger.warning(
                        "Chain break at line %d: expected prev=%s, got=%s",
                        line_num, prev_hash, entry.get("_prev_hash")
                    )

                # Verify hash
                entry_data = json.dumps(
                    {k: v for k, v in entry.items() if k not in ("_hash", "_prev_hash")},
                    sort_keys=True, default=str
                )
                expected_hash = _hmac_chain(prev_hash, entry_data)
                if entry.get("_hash") != expected_hash:
                    broken += 1
                    logger.warning("Hash mismatch at line %d", line_num)

                prev_hash = entry.get("_hash", prev_hash)

        return {
            "valid": broken == 0,
            "entries": entries,
            "broken_chains": broken,
            "file": str(log_file),
        }

    def cleanup_old_logs(self, max_age_days: Optional[int] = None) -> int:
        """Delete rotated audit log files older than the retention period.

        ``max_age_days`` overrides ``AUDIT_LOG_RETENTION_DAYS`` for this call
        (the retention service passes the admin-tunable policy value).
        0 — from either source — disables cleanup, matching the platform-wide
        convention that 0 means "keep everything".
        """
        days = AUDIT_LOG_RETENTION_DAYS if max_age_days is None else int(max_age_days)
        if days <= 0:
            return 0
        cutoff = time.time() - (days * 86400)
        deleted = 0

        for log_file in self.log_dir.glob("audit_*.jsonl"):
            if log_file.stat().st_mtime < cutoff:
                try:
                    log_file.unlink()
                    deleted += 1
                    logger.info("Deleted old audit log: %s", log_file.name)
                except Exception as e:
                    logger.error("Failed to delete audit log %s: %s", log_file, e)

        return deleted

    def export_json(self, entries: list[dict]) -> str:
        """Export audit entries as formatted JSON for compliance."""
        return json.dumps(entries, indent=2, default=str)

    def export_csv(self, entries: list[dict]) -> str:
        """Export audit entries as CSV for compliance."""
        if not entries:
            return ""

        headers = ["timestamp", "event_type", "severity", "user_id", "email", "role", "ip_address", "details"]
        lines = [",".join(headers)]

        for entry in entries:
            row = [
                entry.get("timestamp", ""),
                entry.get("event_type", ""),
                entry.get("severity", ""),
                str(entry.get("user_id", "")),
                entry.get("email", ""),
                entry.get("role", ""),
                entry.get("ip_address", ""),
                json.dumps(entry.get("details", {}), default=str),
            ]
            lines.append(",".join(f'"{c}"' for c in row))

        return "\n".join(lines)


# Singleton instance
audit_logger = AuditLogger()
