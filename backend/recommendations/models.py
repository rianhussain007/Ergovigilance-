"""Recommendation data models.

Immutable dataclasses representing recommendations and bundles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class RecommendationCategory(str, Enum):
    """Recommendation categories."""
    POSTURE = "Posture"
    BREAK = "Break"
    WORKSTATION = "Workstation"
    TRAINING = "Training"
    SUPERVISOR_ACTION = "Supervisor Action"
    MEDICAL_REVIEW = "Medical Review"


class RecommendationTarget(str, Enum):
    """Who the recommendation is for."""
    WORKER = "Worker"
    SUPERVISOR = "Supervisor"
    BOTH = "Both"


class RecommendationPriority(str, Enum):
    """Priority levels (higher = more urgent)."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class Recommendation:
    """Immutable recommendation produced by the Recommendation Engine."""
    id: str = ""
    title: str = ""
    description: str = ""
    category: RecommendationCategory = RecommendationCategory.POSTURE
    priority: RecommendationPriority = RecommendationPriority.LOW
    target: RecommendationTarget = RecommendationTarget.WORKER
    trigger: str = ""
    confidence: float = 0.0
    estimated_benefit: str = ""
    expires_at: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "target": self.target.value,
            "trigger": self.trigger,
            "confidence": round(self.confidence, 3),
            "estimated_benefit": self.estimated_benefit,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class RecommendationBundle:
    """A collection of recommendations generated for one frame."""
    recommendations: tuple = ()
    summary: str = ""
    highest_priority: RecommendationPriority = RecommendationPriority.LOW
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "summary": self.summary,
            "highest_priority": self.highest_priority.value,
            "generated_at": self.generated_at,
        }
