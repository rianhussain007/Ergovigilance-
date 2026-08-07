"""Alert rule definitions for the Alert Engine.

Each rule is a frozen dataclass describing when to trigger an alert.
Rules are evaluated by the AlertEngine against ContextSnapshot data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.alerts.models import AlertSeverity


@dataclass(frozen=True)
class AlertRule:
    """Defines when an alert should be triggered.

    Attributes:
        name: Unique rule identifier.
        severity: Alert severity when triggered.
        title_template: Template for the alert title.
        message_template: Template for the alert message.
        requires_ack: Whether the alert requires manual acknowledgment.
        cooldown_frames: Minimum frames between repeated alerts of this rule.
        escalation_threshold: Consecutive HIGH frames before escalating to CRITICAL.
    """
    name: str = ""
    severity: AlertSeverity = AlertSeverity.HIGH
    title_template: str = ""
    message_template: str = ""
    requires_ack: bool = False
    cooldown_frames: int = 30
    escalation_threshold: int = 10


# ── Default Rules ─────────────────────────────────────────────────

RULE_HIGH_RISK = AlertRule(
    name="high_risk",
    severity=AlertSeverity.HIGH,
    title_template="High Risk Posture Detected",
    message_template="Worker posture risk is HIGH (final_risk={final_risk:.0f}). Immediate attention recommended.",
    requires_ack=True,
    cooldown_frames=30,
)

RULE_CRITICAL_RISK = AlertRule(
    name="critical_risk",
    severity=AlertSeverity.CRITICAL,
    title_template="Critical Risk Posture — Escalated",
    message_template="Worker posture risk has been HIGH for {consecutive_high} consecutive frames. Escalated to CRITICAL.",
    requires_ack=True,
    cooldown_frames=30,
    escalation_threshold=10,
)

RULE_RECOVERY = AlertRule(
    name="recovery",
    severity=AlertSeverity.LOW,
    title_template="Posture Recovered",
    message_template="Worker posture has returned to safe levels (final_risk={final_risk:.0f}). Alert resolved.",
    requires_ack=False,
    cooldown_frames=0,
)

RULE_RAPID_MOVEMENT = AlertRule(
    name="rapid_movement",
    severity=AlertSeverity.WARNING,
    title_template="Rapid Repetitive Movement Detected",
    message_template="Rapid movement: {velocity:.1f} deg/s during {risk_level} posture.",
    requires_ack=False,
    cooldown_frames=90,
)

DEFAULT_RULES = [RULE_HIGH_RISK, RULE_CRITICAL_RISK, RULE_RECOVERY, RULE_RAPID_MOVEMENT]
