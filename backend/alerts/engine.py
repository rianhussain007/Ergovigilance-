"""Alert Engine — subscribes to ContextSnapshotCreatedEvent and produces alerts.

Rules-based alert generation with cooldown, escalation, duplicate
suppression, recovery resolution, and optional SQLite persistence.
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from backend.alerts.models import Alert, AlertSeverity, AlertState
from backend.alerts.rules import AlertRule, DEFAULT_RULES, RULE_HIGH_RISK, RULE_CRITICAL_RISK, RULE_RECOVERY, RULE_RAPID_MOVEMENT
from backend.context.engine import ContextSnapshot
from backend.events.event import Event
from backend.events.event_bus import EventBus
from backend.events.events import ContextSnapshotCreatedEvent

logger = logging.getLogger(__name__)

# Severity weights for priority scoring.  Higher = more urgent.
# CRITICAL alerts always float to the top; LOW recovery alerts sink.
_SEVERITY_WEIGHT: dict[AlertSeverity, float] = {
    AlertSeverity.CRITICAL: 5.0,
    AlertSeverity.HIGH: 3.0,
    AlertSeverity.WARNING: 2.0,
    AlertSeverity.MEDIUM: 1.5,
    AlertSeverity.LOW: 0.5,
}


def _compute_priority(
    severity: AlertSeverity,
    confidence: float,
    age_seconds: float,
    occurrence_count: int,
) -> float:
    """Composite priority score: severity × confidence × age × occurrence.

    Returns 0-100.  CRITICAL + long-lived + high-confidence + repeated
    alerts float to the top of the queue.  LOW recovery alerts sink.
    """
    sev = _SEVERITY_WEIGHT.get(severity, 1.0)
    # Confidence contributes 0.5-1.0 (never zero — even low-confidence
    # alerts need to be visible)
    conf_factor = 0.5 + 0.5 * max(0.0, min(1.0, confidence))
    # Age: logarithmic ramp — a 10-minute-old alert scores ~2x a fresh one
    import math
    age_factor = 1.0 + math.log1p(min(age_seconds, 3600) / 60)  # caps at ~60 min
    # Occurrence: repeat alerts from the same rule are more urgent
    occ_factor = 1.0 + 0.2 * min(occurrence_count - 1, 10)  # caps at +2.0
    raw = sev * conf_factor * age_factor * occ_factor
    return min(100.0, raw * 10)  # scale to 0-100 range


class AlertEngine:
    """Subscribes to ContextSnapshotCreatedEvent and produces alerts.

    Maintains:
    - active_alerts: Currently unresolved alerts
    - history: All alerts ever produced
    - cooldown tracking: Prevents duplicate alerts
    - consecutive_high counter: For escalation to CRITICAL

    Usage::

        engine = AlertEngine(event_bus)
        # Engine now receives events automatically via the bus.
        alerts = engine.get_active_alerts()
    """

    def __init__(self, event_bus: EventBus, rules: list[AlertRule] | None = None, db_enabled: bool = False):
        self._event_bus = event_bus
        self._rules = rules or DEFAULT_RULES
        self._db_enabled = db_enabled

        # State
        self._active_alerts: dict[str, Alert] = {}
        self._history: list[Alert] = []
        self._cooldowns: dict[str, int] = {}  # rule_name -> frames remaining
        self._consecutive_high: int = 0
        self._frame_counter: int = 0
        self._last_risk_level: str = "LOW"
        # Grouping: track occurrence count per rule for the current active set
        self._rule_occurrences: dict[str, int] = {}  # rule_name -> count

        # Rehydrate from SQLite if persistence is enabled
        if self._db_enabled:
            self._rehydrate()

        # Subscribe
        self._event_bus.register(ContextSnapshotCreatedEvent, self._on_snapshot)

    @property
    def active_alerts(self) -> list[Alert]:
        return list(self._active_alerts.values())

    @property
    def history(self) -> list[Alert]:
        return list(self._history)

    @property
    def consecutive_high(self) -> int:
        return self._consecutive_high

    @property
    def frame_counter(self) -> int:
        return self._frame_counter

    def get_active_alerts(self) -> list[Alert]:
        """Return all currently active (unresolved) alerts."""
        return self.active_alerts

    def get_active_alerts_prioritized(self) -> list[Alert]:
        """Return active alerts sorted by priority score (highest first).

        Refreshes each alert's priority_score based on its current age
        before sorting, so the list stays accurate as time passes.
        """
        now = datetime.now(timezone.utc)
        refreshed: list[Alert] = []
        for alert in self._active_alerts.values():
            try:
                created = datetime.fromisoformat(alert.created_at.replace("Z", "+00:00"))
                age_seconds = (now - created).total_seconds()
            except (ValueError, TypeError):
                age_seconds = 0.0
            new_priority = _compute_priority(
                alert.severity, alert.confidence, age_seconds, alert.occurrence_count,
            )
            if new_priority != alert.priority_score:
                updated = Alert(
                    id=alert.id, session_id=alert.session_id,
                    frame_number=alert.frame_number, created_at=alert.created_at,
                    severity=alert.severity, state=alert.state,
                    title=alert.title, message=alert.message,
                    trigger_rule=alert.trigger_rule, confidence=alert.confidence,
                    confidence_band=alert.confidence_band,
                    priority_score=new_priority,
                    group_id=alert.group_id, occurrence_count=alert.occurrence_count,
                    requires_ack=alert.requires_ack, expires_at=alert.expires_at,
                )
                self._active_alerts[alert.id] = updated
                refreshed.append(updated)
            else:
                refreshed.append(alert)
        refreshed.sort(key=lambda a: a.priority_score, reverse=True)
        return refreshed

    def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """Find an alert by its ID."""
        return self._active_alerts.get(alert_id) or next(
            (a for a in self._history if a.id == alert_id), None
        )

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an active alert. Returns True if found and updated."""
        alert = self._active_alerts.get(alert_id)
        if alert and alert.state == AlertState.ACTIVE:
            updated = Alert(
                id=alert.id,
                session_id=alert.session_id,
                frame_number=alert.frame_number,
                created_at=alert.created_at,
                severity=alert.severity,
                state=AlertState.ACKNOWLEDGED,
                title=alert.title,
                message=alert.message,
                trigger_rule=alert.trigger_rule,
                confidence=alert.confidence,
                confidence_band=alert.confidence_band,
                priority_score=alert.priority_score,
                group_id=alert.group_id,
                occurrence_count=alert.occurrence_count,
                requires_ack=alert.requires_ack,
                expires_at=alert.expires_at,
            )
            self._active_alerts[alert_id] = updated
            self._update_history(updated)
            self._persist_state_update(alert_id, "ACKNOWLEDGED")
            return True
        return False

    def resolve(self, alert_id: str) -> bool:
        """Resolve an active alert. Returns True if found and updated."""
        alert = self._active_alerts.get(alert_id)
        if alert and alert.state in (AlertState.ACTIVE, AlertState.ACKNOWLEDGED):
            updated = Alert(
                id=alert.id,
                session_id=alert.session_id,
                frame_number=alert.frame_number,
                created_at=alert.created_at,
                severity=alert.severity,
                state=AlertState.RESOLVED,
                title=alert.title,
                message=alert.message,
                trigger_rule=alert.trigger_rule,
                confidence=alert.confidence,
                confidence_band=alert.confidence_band,
                priority_score=alert.priority_score,
                group_id=alert.group_id,
                occurrence_count=alert.occurrence_count,
                requires_ack=alert.requires_ack,
                expires_at=alert.expires_at,
            )
            del self._active_alerts[alert_id]
            self._update_history(updated)
            self._persist_state_update(alert_id, "RESOLVED")
            return True
        return False

    def reset(self) -> None:
        """Reset all engine state."""
        self._active_alerts.clear()
        self._history.clear()
        self._cooldowns.clear()
        self._consecutive_high = 0
        self._frame_counter = 0
        self._last_risk_level = "LOW"
        self._rule_occurrences.clear()

    # ── Persistence ────────────────────────────────────────────────────

    def _rehydrate(self) -> None:
        """Load history alerts from SQLite on startup.

        Previously-active alerts from prior sessions are resolved so each
        session starts with a clean slate. Only history is kept for reference.
        """
        try:
            from app.core.database import load_active_alerts, load_alert_history
        except ImportError:
            try:
                from backend_api.app.core.database import load_active_alerts, load_alert_history
            except ImportError:
                logger.warning("Alert persistence: database module not available, skipping rehydration")
                return

        try:
            active_rows = load_active_alerts()
            for row in active_rows:
                alert = self._row_to_alert(row)
                self._history.append(alert)
                self._persist_state_update(alert.id, "RESOLVED")

            history_rows = load_alert_history()
            for row in history_rows:
                alert = self._row_to_alert(row)
                self._history.append(alert)

            logger.info(
                "Alert persistence: rehydrated %d history alerts from SQLite "
                "(resolved %d stale active alerts)",
                len(self._history), len(active_rows),
            )
        except Exception as exc:
            logger.error("Alert persistence: rehydration failed: %s", exc)

    def _row_to_alert(self, row: dict) -> Alert:
        """Convert a SQLite row dict back to an Alert dataclass."""
        return Alert(
            id=row["id"],
            session_id=row.get("session_id", ""),
            frame_number=row.get("frame_number", 0),
            created_at=row.get("created_at", ""),
            severity=AlertSeverity(row["severity"]),
            state=AlertState(row["state"]),
            title=row.get("title", ""),
            message=row.get("message", ""),
            trigger_rule=row.get("trigger_rule", ""),
            confidence=row.get("confidence", 0.0),
            confidence_band=row.get("confidence_band", "medium"),
            priority_score=row.get("priority_score", 0.0),
            group_id=row.get("group_id", ""),
            occurrence_count=row.get("occurrence_count", 1),
            requires_ack=bool(row.get("requires_ack", 0)),
            expires_at=row.get("expires_at", ""),
        )

    def _persist_alert(self, alert: Alert, worker_id: str = "") -> None:
        """Write a new alert to SQLite."""
        if not self._db_enabled:
            return
        try:
            try:
                from app.core.database import insert_alert
            except ImportError:
                from backend_api.app.core.database import insert_alert
            insert_alert(
                alert_id=alert.id,
                severity=alert.severity.value,
                title=alert.title,
                message=alert.message,
                trigger_rule=alert.trigger_rule,
                state=alert.state.value,
                session_id=alert.session_id,
                worker_id=worker_id,
                frame_number=alert.frame_number,
                confidence=alert.confidence,
                requires_ack=alert.requires_ack,
                created_at=alert.created_at,
            )
        except Exception as exc:
            logger.error("Alert persistence: failed to persist alert %s: %s", alert.id, exc)

    def _persist_state_update(self, alert_id: str, state: str) -> None:
        """Update an alert's state in SQLite."""
        if not self._db_enabled:
            return
        try:
            try:
                from app.core.database import update_alert_state
            except ImportError:
                from backend_api.app.core.database import update_alert_state
            update_alert_state(alert_id, state)
        except Exception as exc:
            logger.error("Alert persistence: failed to update alert %s: %s", alert_id, exc)

    def export(self) -> dict:
        """Export alert data for persistence.

        Returns a dictionary containing all alerts (active + history)
        suitable for inclusion in a SessionRecord.
        """
        active = list(self._active_alerts.values())
        history = list(self._history)
        return {
            "active_alerts": [a.to_dict() for a in active],
            "history": [a.to_dict() for a in history],
            "total_fired": len(history),
            "consecutive_high": self._consecutive_high,
        }

    def _on_snapshot(self, event: Event) -> None:
        """Handle ContextSnapshotCreatedEvent."""
        if not isinstance(event, type(Event)):
            snapshot = getattr(event, "snapshot", None)
            if snapshot is None:
                return
            self._process_snapshot(snapshot)

    def _process_snapshot(self, snapshot: ContextSnapshot) -> None:
        """Evaluate alert rules against a context snapshot."""
        self._frame_counter += 1
        risk_level = snapshot.risk_level
        final_risk = snapshot.final_risk

        # ── Decrement cooldowns ────────────────────────────────────
        for rule_name in list(self._cooldowns.keys()):
            if self._cooldowns[rule_name] > 1:
                self._cooldowns[rule_name] -= 1
            else:
                del self._cooldowns[rule_name]

        # ── Track consecutive HIGH frames ──────────────────────────
        if risk_level == "HIGH":
            self._consecutive_high += 1
        else:
            self._consecutive_high = 0

        # ── Evaluate rules ─────────────────────────────────────────
        for rule in self._rules:
            should_fire = False
            confidence = 0.0

            if rule.name == "high_risk":
                should_fire, confidence = self._eval_high_risk(rule, risk_level, final_risk)
            elif rule.name == "critical_risk":
                should_fire, confidence = self._eval_critical(rule, risk_level)
            elif rule.name == "recovery":
                should_fire, confidence = self._eval_recovery(rule, risk_level, final_risk)
            elif rule.name == "rapid_movement":
                should_fire, confidence = self._eval_rapid_movement(rule, risk_level, snapshot.movement_velocity)
            elif rule.name == "sustained_risk":
                should_fire, confidence = self._eval_sustained_risk(rule, snapshot)
            elif rule.name == "sustained_high":
                should_fire, confidence = self._eval_sustained_high(rule, snapshot)
            elif rule.name == "worsening_trajectory":
                should_fire, confidence = self._eval_worsening_trajectory(rule, snapshot)
            elif rule.name == "risk_burst":
                should_fire, confidence = self._eval_risk_burst(rule, snapshot)

            if should_fire:
                self._fire_alert(rule, snapshot, confidence)

        self._last_risk_level = risk_level

    def _eval_high_risk(self, rule: AlertRule, risk_level: str, final_risk: float) -> tuple[bool, float]:
        """Evaluate high risk rule: fire when risk_level is HIGH and not on cooldown."""
        if risk_level != "HIGH":
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(final_risk / 100.0, 1.0)
        return True, confidence

    def _eval_critical(self, rule: AlertRule, risk_level: str) -> tuple[bool, float]:
        """Evaluate critical rule: fire when consecutive HIGH frames exceed threshold."""
        if self._consecutive_high < rule.escalation_threshold:
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(self._consecutive_high / 50.0, 1.0)
        return True, confidence

    def _eval_recovery(self, rule: AlertRule, risk_level: str, final_risk: float) -> tuple[bool, float]:
        """Evaluate recovery rule: fire when risk returns to LOW and there were active HIGH alerts."""
        if risk_level != "LOW":
            return False, 0.0
        if not self._has_high_alerts():
            return False, 0.0
        confidence = 1.0 - (final_risk / 100.0)
        return True, confidence

    def _eval_rapid_movement(self, rule: AlertRule, risk_level: str, movement_velocity: float) -> tuple[bool, float]:
        """Evaluate rapid movement rule: fire when velocity > 30 deg/s and risk is MEDIUM or HIGH."""
        if movement_velocity != movement_velocity:  # NaN check
            return False, 0.0
        if movement_velocity <= 30.0:
            return False, 0.0
        if risk_level not in ("MEDIUM", "HIGH"):
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(movement_velocity / 100.0, 1.0)
        return True, confidence

    def _eval_sustained_risk(self, rule: AlertRule, snapshot) -> tuple[bool, float]:
        """Evaluate sustained risk rule: fire when elevated risk > 15 seconds."""
        temporal = snapshot.temporal_risk if hasattr(snapshot, 'temporal_risk') else {}
        sustained_seconds = temporal.get('sustained_risk_seconds', 0)
        if sustained_seconds < 15:
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(sustained_seconds / 60.0, 1.0)
        return True, confidence

    def _eval_sustained_high(self, rule: AlertRule, snapshot) -> tuple[bool, float]:
        """Evaluate sustained high rule: fire when HIGH risk > 10 seconds."""
        temporal = snapshot.temporal_risk if hasattr(snapshot, 'temporal_risk') else {}
        sustained_high = temporal.get('sustained_high_seconds', 0)
        if sustained_high < 10:
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(sustained_high / 30.0, 1.0)
        return True, confidence

    def _eval_worsening_trajectory(self, rule: AlertRule, snapshot) -> tuple[bool, float]:
        """Evaluate worsening trajectory rule: fire when risk is worsening with high confidence."""
        temporal = snapshot.temporal_risk if hasattr(snapshot, 'temporal_risk') else {}
        trajectory = temporal.get('trajectory', 'stable')
        confidence_pct = temporal.get('trajectory_confidence', 0)
        slope = temporal.get('trajectory_slope', 0)
        if trajectory != 'worsening' or confidence_pct < 60:
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(confidence_pct / 100.0, 1.0)
        return True, confidence

    def _eval_risk_burst(self, rule: AlertRule, snapshot) -> tuple[bool, float]:
        """Evaluate risk burst rule: fire when sudden spike detected."""
        temporal = snapshot.temporal_risk if hasattr(snapshot, 'temporal_risk') else {}
        is_burst = temporal.get('is_burst', False)
        burst_magnitude = temporal.get('burst_magnitude', 0)
        if not is_burst or burst_magnitude < 15:
            return False, 0.0
        if self._is_on_cooldown(rule.name):
            return False, 0.0
        confidence = min(burst_magnitude / 50.0, 1.0)
        return True, confidence

    def _is_on_cooldown(self, rule_name: str) -> bool:
        """Check if a rule is on cooldown."""
        return self._cooldowns.get(rule_name, 0) > 0

    def _has_high_alerts(self) -> bool:
        """Check if there are any active HIGH or CRITICAL alerts."""
        return any(
            a.severity in (AlertSeverity.HIGH, AlertSeverity.CRITICAL)
            for a in self._active_alerts.values()
        )

    def _resolve_high_alerts(self) -> None:
        """Resolve all active HIGH and CRITICAL alerts."""
        to_resolve = [
            aid for aid, a in self._active_alerts.items()
            if a.severity in (AlertSeverity.HIGH, AlertSeverity.CRITICAL)
        ]
        for alert_id in to_resolve:
            self.resolve(alert_id)

    def _fire_alert(self, rule: AlertRule, snapshot: ContextSnapshot, confidence: float) -> None:
        """Create and register a new alert."""
        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"

        title = rule.title_template
        # Build template variables including temporal risk data
        temporal = snapshot.temporal_risk if hasattr(snapshot, 'temporal_risk') else {}
        template_vars = {
            'final_risk': snapshot.final_risk,
            'consecutive_high': self._consecutive_high,
            'velocity': snapshot.movement_velocity,
            'risk_level': snapshot.risk_level,
            'sustained_seconds': temporal.get('sustained_risk_seconds', 0),
            'slope': temporal.get('trajectory_slope', 0),
            'current_risk': snapshot.final_risk,
            'predicted_30s': temporal.get('predicted_risk_30s', 0),
            'burst_magnitude': temporal.get('burst_magnitude', 0),
        }
        message = rule.message_template.format(**template_vars)

        # ── Priority scoring ──────────────────────────────────────
        # Track how many times this rule has fired in the current active set
        self._rule_occurrences[rule.name] = self._rule_occurrences.get(rule.name, 0) + 1
        occ_count = self._rule_occurrences[rule.name]
        group_id = f"GRP-{rule.name.upper()}"
        priority_score = _compute_priority(
            rule.severity, confidence, 0.0, occ_count,
        )

        alert = Alert(
            id=alert_id,
            session_id=snapshot.session_id,
            frame_number=snapshot.frame_number,
            created_at=snapshot.captured_at or datetime.now(timezone.utc).isoformat(),
            severity=rule.severity,
            state=AlertState.ACTIVE,
            title=title,
            message=message,
            trigger_rule=rule.name,
            confidence=confidence,
            confidence_band=snapshot.confidence_band,
            priority_score=priority_score,
            group_id=group_id,
            occurrence_count=occ_count,
            requires_ack=rule.requires_ack,
        )

        # Recovery rule: resolve all active HIGH/CRITICAL alerts
        if rule.name == "recovery":
            self._resolve_high_alerts()

        self._active_alerts[alert_id] = alert
        self._history.append(alert)

        # Persist to SQLite
        self._persist_alert(alert, snapshot.worker_id)

        if rule.cooldown_frames > 0:
            self._cooldowns[rule.name] = rule.cooldown_frames

        # Resolve recovery alerts immediately (they don't stay active)
        if rule.name == "recovery":
            self.resolve(alert_id)

    def _update_history(self, updated: Alert) -> None:
        """Update the history entry for an alert."""
        for i, a in enumerate(self._history):
            if a.id == updated.id:
                self._history[i] = updated
                return
