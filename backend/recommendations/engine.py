"""Recommendation Engine V2 — produces prioritized recommendations.

Subscribes to ContextSnapshotCreatedEvent. Uses ContextSnapshot,
AlertEngine, and HistoryEngine to generate context-aware recommendations.
Memory-only. No persistence.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from backend.alerts.engine import AlertEngine
from backend.context.engine import ContextSnapshot
from backend.events.event import Event
from backend.events.event_bus import EventBus
from backend.events.events import ContextSnapshotCreatedEvent
from backend.history.engine import HistoryEngine
from backend.recommendations.catalog import DEFAULT_CATALOG, RecommendationTemplate
from backend.recommendations.models import (
    Recommendation,
    RecommendationBundle,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationTarget,
)
from backend.recommendations.ranking import rank_recommendations, determine_priority_from_score


class RecommendationEngine:
    """Subscribes to ContextSnapshotCreatedEvent and produces recommendations.

    Uses active alerts and history statistics for context-aware recommendations.

    Usage::

        engine = RecommendationEngine(event_bus, alert_engine, history_engine)
        bundle = engine.get_latest_bundle()
    """

    def __init__(
        self,
        event_bus: EventBus,
        alert_engine: AlertEngine,
        history_engine: HistoryEngine,
        catalog: list[RecommendationTemplate] | None = None,
    ):
        self._event_bus = event_bus
        self._alert_engine = alert_engine
        self._history_engine = history_engine
        self._catalog = catalog or DEFAULT_CATALOG

        # State
        self._latest_bundle: Optional[RecommendationBundle] = None
        self._suppressed: dict[str, int] = {}  # trigger -> frames remaining
        self._frame_counter: int = 0

        # Subscribe
        self._event_bus.register(ContextSnapshotCreatedEvent, self._on_snapshot)

    @property
    def latest_bundle(self) -> Optional[RecommendationBundle]:
        return self._latest_bundle

    @property
    def frame_counter(self) -> int:
        return self._frame_counter

    def get_latest_bundle(self) -> Optional[RecommendationBundle]:
        """Return the most recently generated bundle."""
        return self._latest_bundle

    def reset(self) -> None:
        """Reset all engine state."""
        self._latest_bundle = None
        self._suppressed.clear()
        self._frame_counter = 0

    def _on_snapshot(self, event: Event) -> None:
        """Handle ContextSnapshotCreatedEvent."""
        if not isinstance(event, type(Event)):
            snapshot = getattr(event, "snapshot", None)
            if snapshot is not None:
                self._process_snapshot(snapshot)

    def _process_snapshot(self, snapshot: ContextSnapshot) -> None:
        """Generate recommendations for a snapshot."""
        self._frame_counter += 1

        # Decrement suppression timers
        for trigger in list(self._suppressed.keys()):
            if self._suppressed[trigger] > 0:
                self._suppressed[trigger] -= 1
            else:
                del self._suppressed[trigger]

        # Generate recommendations from catalog
        candidates = []
        for template in self._catalog:
            rec = self._evaluate_template(template, snapshot)
            if rec is not None:
                candidates.append(rec)

        # Add alert-based recommendations
        alert_recs = self._generate_alert_recommendations(snapshot)
        candidates.extend(alert_recs)

        # Add history-based recommendations
        history_recs = self._generate_history_recommendations(snapshot)
        candidates.extend(history_recs)

        # Rank and filter
        stats = self._history_engine.get_statistics()
        active_alerts = self._alert_engine.get_active_alerts()
        ranked = rank_recommendations(candidates, snapshot, active_alerts, stats)

        # Build bundle
        if ranked:
            highest = ranked[0].priority
            summary = f"{len(ranked)} recommendation(s). Highest: {highest.value}"
        else:
            highest = RecommendationPriority.LOW
            summary = "No recommendations at this time"

        self._latest_bundle = RecommendationBundle(
            recommendations=tuple(ranked),
            summary=summary,
            highest_priority=highest,
        )

    def _evaluate_template(
        self, template: RecommendationTemplate, snapshot: ContextSnapshot
    ) -> Optional[Recommendation]:
        """Evaluate a template against the current snapshot."""
        trigger = template.trigger_rule

        # Check suppression
        if trigger in self._suppressed:
            return None

        # Evaluate trigger conditions
        should_fire = False
        confidence = 0.0
        format_data = {}

        if trigger == "neck_flexion_high":
            val = snapshot.feature_scores.get("neck_flexion", 0.0)
            if val > 50:
                should_fire = True
                confidence = val / 100.0
                format_data["value"] = snapshot.feature_scores.get("neck_flexion", 0) * 0.3

        elif trigger == "trunk_flexion_high":
            val = snapshot.feature_scores.get("trunk_flexion", 0.0)
            if val > 50:
                should_fire = True
                confidence = val / 100.0
                format_data["value"] = snapshot.feature_scores.get("trunk_flexion", 0) * 0.6

        elif trigger == "shoulder_symmetry_high":
            val = snapshot.feature_scores.get("shoulder_symmetry", 0.0)
            if val > 50:
                should_fire = True
                confidence = val / 100.0
                format_data["value"] = snapshot.feature_scores.get("shoulder_symmetry", 0) * 0.15

        elif trigger == "alignment_deviation_high":
            val = snapshot.feature_scores.get("alignment_deviation", 0.0)
            if val > 50:
                should_fire = True
                confidence = val / 100.0
                format_data["value"] = snapshot.feature_scores.get("alignment_deviation", 0) * 0.25

        elif trigger == "knee_angle_low":
            val = snapshot.feature_scores.get("knee_angle", 0.0)
            if val > 50:
                should_fire = True
                confidence = val / 100.0
                format_data["value"] = 180 - (snapshot.feature_scores.get("knee_angle", 0) * 0.8)

        elif trigger == "fatigue_high":
            if snapshot.fatigue_score > 40:
                should_fire = True
                confidence = snapshot.fatigue_score / 100.0
                format_data["fatigue"] = snapshot.fatigue_score

        elif trigger == "exposure_high":
            if snapshot.exposure_score > 50:
                should_fire = True
                confidence = snapshot.exposure_score / 100.0
                format_data["exposure"] = snapshot.exposure_score

        elif trigger == "duration_long":
            if self._frame_counter > 100:
                should_fire = True
                confidence = min(self._frame_counter / 500.0, 1.0)
                # Use actual elapsed time from history engine, not frame_count * 33ms
                stats = self._history_engine.get_statistics()
                elapsed_min = max(stats.session_duration_seconds / 60.0, self._frame_counter * 0.033 / 60.0)
                format_data["duration"] = elapsed_min

        elif trigger == "persistent_issues":
            active = self._alert_engine.get_active_alerts()
            if len(active) >= 3:
                should_fire = True
                confidence = min(len(active) / 5.0, 1.0)

        elif trigger == "repeated_issues":
            stats = self._history_engine.get_statistics()
            if stats.frames_stored > 50 and stats.risk_distribution.high > stats.frames_stored * 0.3:
                should_fire = True
                confidence = stats.risk_distribution.high_pct / 100.0

        elif trigger == "critical_risk":
            active = self._alert_engine.get_active_alerts()
            if any(a.severity.value == "CRITICAL" for a in active):
                should_fire = True
                confidence = 1.0

        elif trigger == "persistent_high_risk":
            stats = self._history_engine.get_statistics()
            if stats.frames_stored > 100 and stats.risk_distribution.high > stats.frames_stored * 0.5:
                should_fire = True
                confidence = stats.risk_distribution.high_pct / 100.0

        if not should_fire:
            return None

        # Create recommendation
        rec_id = f"{template.id_prefix}-{uuid.uuid4().hex[:6].upper()}"
        description = template.description.format(**format_data) if format_data else template.description

        return Recommendation(
            id=rec_id,
            title=template.title,
            description=description,
            category=template.category,
            priority=template.base_priority,
            target=template.target,
            trigger=trigger,
            confidence=confidence,
            estimated_benefit=template.estimated_benefit,
        )

    def _generate_alert_recommendations(self, snapshot: ContextSnapshot) -> list[Recommendation]:
        """Generate recommendations based on active alerts."""
        recs = []
        active = self._alert_engine.get_active_alerts()

        # High alert count -> supervisor intervention
        if len(active) >= 2 and "alert_count_high" not in self._suppressed:
            recs.append(Recommendation(
                id=f"REC-ALERT-{uuid.uuid4().hex[:6].upper()}",
                title="Multiple Active Alerts",
                description=f"{len(active)} alerts are currently active. Review and address each alert.",
                category=RecommendationCategory.SUPERVISOR_ACTION,
                priority=RecommendationPriority.HIGH,
                target=RecommendationTarget.SUPERVISOR,
                trigger="alert_count_high",
                confidence=min(len(active) / 3.0, 1.0),
                estimated_benefit="Comprehensive risk mitigation",
            ))

        return recs

    def _generate_history_recommendations(self, snapshot: ContextSnapshot) -> list[Recommendation]:
        """Generate recommendations based on history trends."""
        recs = []
        stats = self._history_engine.get_statistics()

        # Increasing trend
        if stats.frames_stored > 20:
            recent = self._history_engine.window(10)
            if recent:
                recent_avg = sum(s.final_risk for s in recent) / len(recent)
                if recent_avg > stats.average_risk * 1.3 and "trend_increasing" not in self._suppressed:
                    recs.append(Recommendation(
                        id=f"REC-TREND-{uuid.uuid4().hex[:6].upper()}",
                        title="Risk Trend Increasing",
                        description=f"Recent risk ({recent_avg:.0f}) is significantly above average ({stats.average_risk:.0f}).",
                        category=RecommendationCategory.POSTURE,
                        priority=RecommendationPriority.MEDIUM,
                        target=RecommendationTarget.BOTH,
                        trigger="trend_increasing",
                        confidence=min(recent_avg / 100.0, 1.0),
                        estimated_benefit="Early intervention before risk escalates",
                    ))

        return recs

    def export(self) -> dict:
        """Export recommendation data for persistence.

        Returns a dictionary containing the latest bundle
        suitable for inclusion in a SessionRecord.
        """
        bundle = self._latest_bundle
        if bundle is None:
            return {"bundle": None, "total_generated": 0}
        return {
            "bundle": bundle.to_dict(),
            "total_generated": self._frame_counter,
        }
