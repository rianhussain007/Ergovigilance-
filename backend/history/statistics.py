"""Statistics computation for snapshot history.

Pure functions that compute statistics from a list of ContextSnapshots.
No state. No side effects.
"""

from __future__ import annotations

from backend.context.engine import ContextSnapshot
from backend.history.models import HistoryStats, RiskDistribution


def compute_statistics(snapshots: list[ContextSnapshot]) -> HistoryStats:
    """Compute statistics from a list of snapshots.

    Args:
        snapshots: List of ContextSnapshot in chronological order.

    Returns:
        HistoryStats with all computed metrics.
    """
    if not snapshots:
        return HistoryStats()

    n = len(snapshots)

    # Risk metrics
    risks = [s.final_risk for s in snapshots]
    avg_risk = sum(risks) / n
    max_risk = max(risks)
    min_risk = min(risks)

    # Fatigue metrics
    fatigues = [s.fatigue_score for s in snapshots]
    avg_fatigue = sum(fatigues) / n
    max_fatigue = max(fatigues)

    # Exposure metrics
    exposures = [s.exposure_score for s in snapshots]
    avg_exposure = sum(exposures) / n
    max_exposure = max(exposures)

    # Risk distribution
    low = sum(1 for s in snapshots if s.risk_level == "LOW")
    medium = sum(1 for s in snapshots if s.risk_level == "MEDIUM")
    high = sum(1 for s in snapshots if s.risk_level == "HIGH")

    # Session duration (difference between first and last captured_at)
    duration = 0.0
    if n >= 2:
        try:
            from datetime import datetime
            first = datetime.fromisoformat(snapshots[0].captured_at.replace("Z", "+00:00"))
            last = datetime.fromisoformat(snapshots[-1].captured_at.replace("Z", "+00:00"))
            duration = (last - first).total_seconds()
        except (ValueError, TypeError):
            duration = 0.0

    return HistoryStats(
        frames_stored=n,
        session_duration_seconds=duration,
        average_risk=avg_risk,
        maximum_risk=max_risk,
        minimum_risk=min_risk,
        average_fatigue=avg_fatigue,
        maximum_fatigue=max_fatigue,
        average_exposure=avg_exposure,
        maximum_exposure=max_exposure,
        risk_distribution=RiskDistribution(low=low, medium=medium, high=high),
    )
