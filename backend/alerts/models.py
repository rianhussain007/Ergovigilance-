"""Alert data models for the Alert Engine.

Immutable dataclasses representing alerts produced by the alert rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertState(str, Enum):
    """Alert lifecycle states."""
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Alert:
    """Immutable alert produced by the Alert Engine.

    Designed for:
    - In-memory processing (no persistence)
    - Future API exposure (clean fields)
    - Audit trail (rule, confidence, timestamps)
    """
    id: str = ""
    session_id: str = ""
    frame_number: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    severity: AlertSeverity = AlertSeverity.LOW
    state: AlertState = AlertState.ACTIVE
    title: str = ""
    message: str = ""
    trigger_rule: str = ""
    confidence: float = 0.0
    requires_ack: bool = False
    expires_at: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "frame_number": self.frame_number,
            "created_at": self.created_at,
            "severity": self.severity.value,
            "state": self.state.value,
            "title": self.title,
            "message": self.message,
            "trigger_rule": self.trigger_rule,
            "confidence": self.confidence,
            "requires_ack": self.requires_ack,
            "expires_at": self.expires_at,
        }
