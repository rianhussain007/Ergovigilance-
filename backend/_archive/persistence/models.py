"""Session persistence models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SessionRecord:
    """Complete record of a monitoring session.

    Contains all data produced during a session: metadata,
    context snapshots, alerts, recommendations, and statistics.
    Designed for JSON serialization and future SQL migration.
    """

    session_id: str
    started_at: str
    ended_at: str
    worker_id: str

    statistics: dict[str, Any] = field(default_factory=dict)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "worker_id": self.worker_id,
            "statistics": self.statistics,
            "snapshots": self.snapshots,
            "alerts": self.alerts,
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionRecord:
        """Deserialize from dictionary."""
        return cls(
            session_id=data.get("session_id", ""),
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at", ""),
            worker_id=data.get("worker_id", ""),
            statistics=data.get("statistics", {}),
            snapshots=data.get("snapshots", []),
            alerts=data.get("alerts", []),
            recommendations=data.get("recommendations", []),
        )
