"""Recommendation catalog — templates for different situations.

Each template defines a recommendation that can be triggered
based on context, alerts, or history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.recommendations.models import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationTarget,
)


@dataclass(frozen=True)
class RecommendationTemplate:
    """Template for generating recommendations.

    Attributes:
        id_prefix: Prefix for generated recommendation IDs.
        title: Recommendation title.
        description: Detailed description (supports format placeholders).
        category: Recommendation category.
        base_priority: Base priority level.
        target: Who the recommendation is for.
        estimated_benefit: Expected benefit text.
        trigger_rule: Which rule triggered this recommendation.
    """
    id_prefix: str = ""
    title: str = ""
    description: str = ""
    category: RecommendationCategory = RecommendationCategory.POSTURE
    base_priority: RecommendationPriority = RecommendationPriority.LOW
    target: RecommendationTarget = RecommendationTarget.WORKER
    estimated_benefit: str = ""
    trigger_rule: str = ""


# ── Posture Templates ─────────────────────────────────────────────

TEMPLATE_NECK_POSTURE = RecommendationTemplate(
    id_prefix="REC-NECK",
    title="Adjust Neck Posture",
    description="Neck flexion is elevated ({value:.0f} degrees). Lower your chin and keep your head aligned with your spine.",
    category=RecommendationCategory.POSTURE,
    base_priority=RecommendationPriority.HIGH,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced neck strain, lower risk of cervical injury",
    trigger_rule="neck_flexion_high",
)

TEMPLATE_TRUNK_POSTURE = RecommendationTemplate(
    id_prefix="REC-TRUNK",
    title="Correct Trunk Flexion",
    description="Trunk flexion is excessive ({value:.0f} degrees). Straighten your back and bend at the knees when lifting.",
    category=RecommendationCategory.POSTURE,
    base_priority=RecommendationPriority.HIGH,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced lower back load, decreased disc pressure",
    trigger_rule="trunk_flexion_high",
)

TEMPLATE_SHOULDER_IMBALANCE = RecommendationTemplate(
    id_prefix="REC-SHOULDER",
    title="Balance Shoulder Elevation",
    description="Shoulder symmetry deviation is {value:.0f} degrees. Ensure both shoulders are at similar heights.",
    category=RecommendationCategory.POSTURE,
    base_priority=RecommendationPriority.MEDIUM,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced muscle imbalance, decreased shoulder injury risk",
    trigger_rule="shoulder_symmetry_high",
)

TEMPLATE_ALIGNMENT = RecommendationTemplate(
    id_prefix="REC-ALIGN",
    title="Improve Body Alignment",
    description="Alignment deviation is {value:.0f} percent. Center your body over your base of support.",
    category=RecommendationCategory.POSTURE,
    base_priority=RecommendationPriority.MEDIUM,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Improved balance, reduced fall risk",
    trigger_rule="alignment_deviation_high",
)

TEMPLATE_KNEE_ANGLE = RecommendationTemplate(
    id_prefix="REC-KNEE",
    title="Adjust Knee Position",
    description="Knee angle is {value:.0f} degrees. Maintain a slight bend to reduce joint stress.",
    category=RecommendationCategory.POSTURE,
    base_priority=RecommendationPriority.MEDIUM,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced knee joint load, decreased patellar stress",
    trigger_rule="knee_angle_low",
)

# ── Break Templates ───────────────────────────────────────────────

TEMPLATE_FATIGUE_BREAK = RecommendationTemplate(
    id_prefix="REC-BREAK-F",
    title="Take a Micro-Break",
    description="Fatigue level is elevated ({fatigue:.0f}/100). Take a 2-5 minute break to stretch and rest.",
    category=RecommendationCategory.BREAK,
    base_priority=RecommendationPriority.HIGH,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced fatigue, improved focus and productivity",
    trigger_rule="fatigue_high",
)

TEMPLATE_EXPOSURE_BREAK = RecommendationTemplate(
    id_prefix="REC-BREAK-E",
    title="Reduce Exposure Duration",
    description="High-risk exposure has been {exposure:.0f}/100. Switch tasks or take a break.",
    category=RecommendationCategory.BREAK,
    base_priority=RecommendationPriority.HIGH,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced cumulative risk exposure, injury prevention",
    trigger_rule="exposure_high",
)

TEMPLATE_DURATION_BREAK = RecommendationTemplate(
    id_prefix="REC-BREAK-D",
    title="Extended Work Period Detected",
    description="You have been working for {duration:.0f} minutes without a break. Take a rest break.",
    category=RecommendationCategory.BREAK,
    base_priority=RecommendationPriority.MEDIUM,
    target=RecommendationTarget.WORKER,
    estimated_benefit="Reduced cumulative fatigue, maintained alertness",
    trigger_rule="duration_long",
)

# ── Workstation Templates ─────────────────────────────────────────

TEMPLATE_WORKSTATION_REVIEW = RecommendationTemplate(
    id_prefix="REC-WS",
    title="Review Workstation Setup",
    description="Persistent posture issues detected. Review monitor height, chair position, and desk ergonomics.",
    category=RecommendationCategory.WORKSTATION,
    base_priority=RecommendationPriority.MEDIUM,
    target=RecommendationTarget.BOTH,
    estimated_benefit="Long-term posture improvement, reduced chronic injury risk",
    trigger_rule="persistent_issues",
)

# ── Training Templates ────────────────────────────────────────────

TEMPLATE_POSTURE_TRAINING = RecommendationTemplate(
    id_prefix="REC-TRAIN",
    title="Ergonomic Training Recommended",
    description="Repeated posture deviations detected. Consider ergonomic awareness training.",
    category=RecommendationCategory.TRAINING,
    base_priority=RecommendationPriority.MEDIUM,
    target=RecommendationTarget.SUPERVISOR,
    estimated_benefit="Improved workplace ergonomics, reduced injury rates",
    trigger_rule="repeated_issues",
)

# ── Supervisor Templates ──────────────────────────────────────────

TEMPLATE_SUPERVISOR_INTERVENTION = RecommendationTemplate(
    id_prefix="REC-SUPER",
    title="Supervisor Intervention Required",
    description="Critical risk level sustained. Supervisor should review worker posture and task assignment.",
    category=RecommendationCategory.SUPERVISOR_ACTION,
    base_priority=RecommendationPriority.CRITICAL,
    target=RecommendationTarget.SUPERVISOR,
    estimated_benefit="Immediate risk reduction, injury prevention",
    trigger_rule="critical_risk",
)

# ── Medical Templates ─────────────────────────────────────────────

TEMPLATE_MEDICAL_REVIEW = RecommendationTemplate(
    id_prefix="REC-MED",
    title="Medical Review Recommended",
    description="Persistent high-risk posture detected over multiple sessions. Recommend medical evaluation.",
    category=RecommendationCategory.MEDICAL_REVIEW,
    base_priority=RecommendationPriority.HIGH,
    target=RecommendationTarget.SUPERVISOR,
    estimated_benefit="Early detection of musculoskeletal disorders",
    trigger_rule="persistent_high_risk",
)


# ── Catalog ───────────────────────────────────────────────────────

DEFAULT_CATALOG = [
    TEMPLATE_NECK_POSTURE,
    TEMPLATE_TRUNK_POSTURE,
    TEMPLATE_SHOULDER_IMBALANCE,
    TEMPLATE_ALIGNMENT,
    TEMPLATE_KNEE_ANGLE,
    TEMPLATE_FATIGUE_BREAK,
    TEMPLATE_EXPOSURE_BREAK,
    TEMPLATE_DURATION_BREAK,
    TEMPLATE_WORKSTATION_REVIEW,
    TEMPLATE_POSTURE_TRAINING,
    TEMPLATE_SUPERVISOR_INTERVENTION,
    TEMPLATE_MEDICAL_REVIEW,
]
