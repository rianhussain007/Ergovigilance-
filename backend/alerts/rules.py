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

# ── Temporal Risk Rules ─────────────────────────────────────────────

RULE_SUSTAINED_RISK = AlertRule(
    name="sustained_risk",
    severity=AlertSeverity.WARNING,
    title_template="Posture Risk Sustained",
    message_template="Elevated posture risk sustained for {sustained_seconds:.0f} seconds. Take a break or adjust position.",
    requires_ack=False,
    cooldown_frames=60,
)

RULE_SUSTAINED_HIGH = AlertRule(
    name="sustained_high",
    severity=AlertSeverity.HIGH,
    title_template="High Risk Sustained — Action Needed",
    message_template="HIGH risk sustained for {sustained_seconds:.0f} seconds. Correct posture immediately.",
    requires_ack=True,
    cooldown_frames=30,
)

RULE_WORSENING_TRAJECTORY = AlertRule(
    name="worsening_trajectory",
    severity=AlertSeverity.WARNING,
    title_template="Risk Trend Worsening",
    message_template="Posture risk is increasing ({slope:.1f} risk/sec). Current: {current_risk:.0f}/100, predicted: {predicted_30s:.0f}/100 in 30s.",
    requires_ack=False,
    cooldown_frames=120,
)

RULE_RISK_BURST = AlertRule(
    name="risk_burst",
    severity=AlertSeverity.WARNING,
    title_template="Sudden Posture Change Detected",
    message_template="Rapid posture change detected (+{burst_magnitude:.0f} risk/sec). Check for sudden movement or equipment issue.",
    requires_ack=False,
    cooldown_frames=60,
)

DEFAULT_RULES = [
    RULE_HIGH_RISK, RULE_CRITICAL_RISK, RULE_RECOVERY, RULE_RAPID_MOVEMENT,
    RULE_SUSTAINED_RISK, RULE_SUSTAINED_HIGH, RULE_WORSENING_TRAJECTORY, RULE_RISK_BURST,
]
