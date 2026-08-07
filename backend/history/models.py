"""History statistics data models.

Immutable dataclasses representing computed statistics
from the snapshot history.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskDistribution:
    """Distribution of risk levels across stored snapshots."""
    low: int = 0
    medium: int = 0
    high: int = 0

    @property
    def total(self) -> int:
        return self.low + self.medium + self.high

    @property
    def low_pct(self) -> float:
        return (self.low / self.total * 100.0) if self.total > 0 else 0.0

    @property
    def medium_pct(self) -> float:
        return (self.medium / self.total * 100.0) if self.total > 0 else 0.0

    @property
    def high_pct(self) -> float:
        return (self.high / self.total * 100.0) if self.total > 0 else 0.0


@dataclass(frozen=True)
class HistoryStats:
    """Computed statistics from the snapshot history.

    All fields are computed on demand and cached.
    Designed for API exposure and analytics.
    """
    frames_stored: int = 0
    session_duration_seconds: float = 0.0

    average_risk: float = 0.0
    maximum_risk: float = 0.0
    minimum_risk: float = 0.0

    average_fatigue: float = 0.0
    maximum_fatigue: float = 0.0

    average_exposure: float = 0.0
    maximum_exposure: float = 0.0

    risk_distribution: RiskDistribution = field(default_factory=RiskDistribution)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "frames_stored": self.frames_stored,
            "session_duration_seconds": round(self.session_duration_seconds, 2),
            "average_risk": round(self.average_risk, 2),
            "maximum_risk": round(self.maximum_risk, 2),
            "minimum_risk": round(self.minimum_risk, 2),
            "average_fatigue": round(self.average_fatigue, 2),
            "maximum_fatigue": round(self.maximum_fatigue, 2),
            "average_exposure": round(self.average_exposure, 2),
            "maximum_exposure": round(self.maximum_exposure, 2),
            "risk_distribution": {
                "low": self.risk_distribution.low,
                "medium": self.risk_distribution.medium,
                "high": self.risk_distribution.high,
                "low_pct": round(self.risk_distribution.low_pct, 1),
                "medium_pct": round(self.risk_distribution.medium_pct, 1),
                "high_pct": round(self.risk_distribution.high_pct, 1),
            },
        }
