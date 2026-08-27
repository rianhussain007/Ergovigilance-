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
    title_template="Unsafe Posture — Needs Attention",
    message_template="Posture risk is high ({final_risk:.0f}/100). Straighten up and take a break.",
    requires_ack=True,
    cooldown_frames=30,
)

RULE_CRITICAL_RISK = AlertRule(
    name="critical_risk",
    severity=AlertSeverity.CRITICAL,
    title_template="Stop Work — Injury Risk",
    message_template="Unsafe posture sustained for too long. Stop and correct your position now.",
    requires_ack=True,
    cooldown_frames=30,
    escalation_threshold=10,
)

RULE_RECOVERY = AlertRule(
    name="recovery",
    severity=AlertSeverity.LOW,
    title_template="Posture Improved",
    message_template="Posture back to safe levels ({final_risk:.0f}/100). Keep it up.",
    requires_ack=False,
    cooldown_frames=0,
)

RULE_RAPID_MOVEMENT = AlertRule(
    name="rapid_movement",
    severity=AlertSeverity.WARNING,
    title_template="Fast Movement Detected",
    message_template="Quick repetitive motion detected ({velocity:.1f} deg/s). Slow down to avoid strain.",
    requires_ack=False,
    cooldown_frames=90,
)

DEFAULT_RULES = [RULE_HIGH_RISK, RULE_CRITICAL_RISK, RULE_RECOVERY, RULE_RAPID_MOVEMENT]
