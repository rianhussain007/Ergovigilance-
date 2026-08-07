"""Concrete event definitions for the ErgoVigilance event system.

Each event is a frozen dataclass carrying typed payload data.
All events inherit from Event and are immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.events.event import Event
from backend.context.engine import ContextSnapshot


# ── CV Pipeline Events ────────────────────────────────────────────

@dataclass(frozen=True)
class PoseUpdatedEvent(Event):
    """Published when PoseEngine produces a new ProcessedFrame."""
    event_type: str = "PoseUpdated"
    session_id: str = ""
    frame_number: int = 0
    confidence: float = 0.0
    person_detected: bool = False


@dataclass(frozen=True)
class FeaturesUpdatedEvent(Event):
    """Published when ergonomic features are extracted from a frame."""
    event_type: str = "FeaturesUpdated"
    session_id: str = ""
    frame_number: int = 0
    features: dict = field(default_factory=dict)
    risk_level: str = "LOW"


@dataclass(frozen=True)
class IssuesDetectedEvent(Event):
    """Published when posture issues are detected."""
    event_type: str = "IssuesDetected"
    session_id: str = ""
    frame_number: int = 0
    issues: tuple = ()
    risk_level: str = "LOW"


# ── Context Intelligence Events ───────────────────────────────────

@dataclass(frozen=True)
class ContextSnapshotCreatedEvent(Event):
    """Published when ContextIntelligenceEngine produces a snapshot."""
    event_type: str = "ContextSnapshotCreated"
    snapshot: Optional[ContextSnapshot] = None


# ── Session Lifecycle Events ──────────────────────────────────────

@dataclass(frozen=True)
class SessionStartedEvent(Event):
    """Published when a monitoring session starts."""
    event_type: str = "SessionStarted"
    session_id: str = ""
    worker_id: str = ""
    camera_index: int = 0


@dataclass(frozen=True)
class SessionEndedEvent(Event):
    """Published when a monitoring session ends."""
    event_type: str = "SessionEnded"
    session_id: str = ""
    total_frames: int = 0
    duration_seconds: float = 0.0
