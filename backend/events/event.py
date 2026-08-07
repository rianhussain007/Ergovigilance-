"""Base event class for the internal event system.

All events are frozen dataclasses with an auto-generated timestamp.
Events are immutable — once created, their fields cannot be modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Event:
    """Base class for all internal events.

    Attributes:
        timestamp: ISO-8601 timestamp of when the event was created.
        event_type: Human-readable event type name (auto-set by subclass).
    """
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = ""
