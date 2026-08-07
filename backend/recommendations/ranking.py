"""Ranking algorithm for recommendations.

Computes a priority score for each recommendation based on
current context, alerts, and history. Higher score = more urgent.
"""

from __future__ import annotations

from backend.alerts.models import Alert, AlertSeverity
from backend.context.engine import ContextSnapshot
from backend.history.models import HistoryStats
from backend.recommendations.models import Recommendation, RecommendationPriority


# ── Priority Weights ──────────────────────────────────────────────

_PRIORITY_SCORES = {
    RecommendationPriority.LOW: 1,
    RecommendationPriority.MEDIUM: 2,
    RecommendationPriority.HIGH: 3,
    RecommendationPriority.CRITICAL: 4,
}

_ALERT_MULTIPLIER = {
    AlertSeverity.LOW: 1.0,
    AlertSeverity.MEDIUM: 1.5,
    AlertSeverity.HIGH: 2.0,
    AlertSeverity.CRITICAL: 3.0,
}


def compute_priority_score(
    recommendation: Recommendation,
    snapshot: ContextSnapshot,
    active_alerts: list[Alert],
    stats: HistoryStats,
) -> float:
    """Compute a priority score for a recommendation.

    Score components:
    - Base priority (1-4)
    - Risk multiplier (0.5-2.0 based on final_risk)
    - Fatigue multiplier (1.0-1.5 based on fatigue_score)
    - Exposure multiplier (1.0-1.5 based on exposure_score)
    - Alert boost (1.0-3.0 based on active alert severity)
    - Trend penalty (1.0-1.3 if risk is increasing)

    Higher score = more urgent recommendation.

    Args:
        recommendation: The recommendation to score.
        snapshot: Current context snapshot.
        active_alerts: Currently active alerts.
        stats: History statistics for trend analysis.

    Returns:
        Computed priority score.
    """
    # Base priority score
    base = _PRIORITY_SCORES.get(recommendation.priority, 1)

    # Risk multiplier: 0.5 at 0 risk, 2.0 at 100 risk
    risk_mult = 0.5 + (snapshot.final_risk / 100.0) * 1.5

    # Fatigue multiplier: 1.0 at 0 fatigue, 1.5 at 100 fatigue
    fatigue_mult = 1.0 + (snapshot.fatigue_score / 100.0) * 0.5

    # Exposure multiplier: 1.0 at 0 exposure, 1.5 at 100 exposure
    exposure_mult = 1.0 + (snapshot.exposure_score / 100.0) * 0.5

    # Alert boost: based on highest active alert severity
    alert_boost = 1.0
    if active_alerts:
        max_severity = max(active_alerts, key=lambda a: _ALERT_MULTIPLIER.get(a.severity, 1.0))
        alert_boost = _ALERT_MULTIPLIER.get(max_severity.severity, 1.0)

    # Trend penalty: 1.3 if average risk is increasing
    trend_mult = 1.0
    if stats.frames_stored > 10 and snapshot.final_risk > stats.average_risk * 1.2:
        trend_mult = 1.3

    score = base * risk_mult * fatigue_mult * exposure_mult * alert_boost * trend_mult
    return round(score, 3)


def rank_recommendations(
    recommendations: list[Recommendation],
    snapshot: ContextSnapshot,
    active_alerts: list[Alert],
    stats: HistoryStats,
) -> list[Recommendation]:
    """Rank recommendations by priority score (highest first).

    Args:
        recommendations: List of recommendations to rank.
        snapshot: Current context snapshot.
        active_alerts: Currently active alerts.
        stats: History statistics.

    Returns:
        Sorted list of recommendations (highest priority first).
    """
    scored = []
    for rec in recommendations:
        score = compute_priority_score(rec, snapshot, active_alerts, stats)
        scored.append((score, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [rec for _, rec in scored]


def determine_priority_from_score(score: float) -> RecommendationPriority:
    """Convert a numeric score to a priority level."""
    if score >= 8.0:
        return RecommendationPriority.CRITICAL
    if score >= 4.0:
        return RecommendationPriority.HIGH
    if score >= 2.0:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW
