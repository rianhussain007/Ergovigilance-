"""Context Intelligence Engine — the reasoning core of ErgoVigilance.

Combines biomechanical features with temporal, task, fatigue, and exposure
context to produce a context-adjusted risk assessment as a ContextSnapshot.

100% deterministic. Rule-based. No ML.
"""

from __future__ import annotations

import json
import os
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.context.exposure import ExposureTracker
from backend.context.fatigue import FatigueModel
from backend.context.temporal_risk import TemporalRiskTracker, TemporalRiskPattern
from backend.core.constants import RISK_ORDER
from backend.services.features import FEATURE_DEPENDENCIES


# ── Feature Scoring Rules ──────────────────────────────────────────

_FEATURE_RULES: dict[str, tuple[float, float, bool]] = {
    "neck_flexion":         (10.0, 30.0, False),
    "trunk_flexion":        (20.0, 60.0, False),
    "left_shoulder_elev":   (30.0, 60.0, False),
    "right_shoulder_elev":  (30.0, 60.0, False),
    "shoulder_symmetry":    (5.0, 15.0, False),
    "alignment_deviation":  (20.0, 50.0, False),
    "knee_angle":           (150.0, 100.0, True),
    # Phase-A additions (2026-08)
    "forward_head_posture": (10.0, 20.0, False),
    "head_tilt_angle":      (10.0, 20.0, False),
    "wrist_deviation_angle": (5.0, 15.0, False),
    "stance_stability":     (0.7, 0.5, True),
    "weight_shift_offset":  (8.0, 15.0, False),
}

# ── Task-Conditional Feature Rules ─────────────────────────────────
# When a task is classified with sufficient confidence, feature scoring
# uses task-specific (MEDIUM, HIGH, inverted) tuples instead of the
# one-size-fits-all _FEATURE_RULES above.  Only features relevant to
# the task are overridden — everything else falls through to the default.

def _task_feature_rules(task_label: str | None, task_confidence: float) -> dict[str, tuple[float, float, bool]]:
    """Return feature rules adjusted for the detected task.

    Below 50% confidence, or for unknown/Neutral Standing tasks, the
    baseline _FEATURE_RULES are used unchanged.
    """
    from backend.services.features import task_thresholds
    if not task_label or task_label not in task_thresholds or task_confidence < 50.0:
        return dict(_FEATURE_RULES)
    tt = task_thresholds[task_label]
    rules = dict(_FEATURE_RULES)
    for feature, (med, high) in tt.items():
        # Look up inversion flag from the baseline rules
        inv = rules.get(feature, (0, 0, False))[2]
        rules[feature] = (med, high, inv)
    return rules


# ── Task Modifiers ─────────────────────────────────────────────────

_TASK_MODIFIERS: dict[str, float] = {
    "Neutral Standing": 0,
    "Walking / Moving": 2,
    "Inspection": 3,
    "Seated Work": 4,
    "Assembly Work": 5,
    "Reaching": 8,
    "Lifting / Picking": 12,
}


# ── Confidence Thresholds ──────────────────────────────────────────

_CONFIDENCE_HIGH = 90.0
_CONFIDENCE_MEDIUM = 70.0
_CONFIDENCE_LOW = 50.0


# ── Snapshot Dataclass ─────────────────────────────────────────────

@dataclass(frozen=True)
class ContextSnapshot:
    """Immutable snapshot of one analyzed frame.

    Designed for:
    - Database storage (all fields are JSON-serializable)
    - Audit trail (timestamps, frame numbers, active rules)
    - API responses (clean serialization)
    - Analytics (structured reason and rule traces)
    """

    # Identity
    session_id: str = ""
    frame_number: int = 0
    captured_at: str = ""
    worker_id: str = ""

    # Risk assessment
    base_risk: float = 0.0
    context_modifier: float = 0.0
    fatigue_score: float = 0.0
    exposure_score: float = 0.0
    confidence_modifier: float = 0.0
    final_risk: float = 0.0
    risk_level: str = "LOW"
    safety_state: str = "SAFE"

    # Raw signals
    movement_velocity: float = 0.0

    # Tracking quality
    unavailable_features: tuple[str, ...] = ()
    approximate_features: tuple[str, ...] = ()
    lower_body_confidence: float = 0.0

    # Authoritative standard-method assessment (RULA vs REBA by body
    # visibility): {"method", "score", "risk_level", "is_partial", "reason"}.
    standard_assessment: dict = field(default_factory=dict)

    # Task classification (from the deterministic HistGradientBoosting model)
    task_label: str = "Unknown"
    task_confidence: float = 0.0

    # Explainability
    reason: str = ""
    active_rules: tuple[str, ...] = ()
    feature_scores: dict[str, float] = field(default_factory=dict)

    # Confidence band — human-readable trust signal derived from camera
    # confidence, feature completeness, and dwell stability.  One of:
    #   "high"   (camera >= 90%, all features available, stable dwell)
    #   "medium" (camera >= 70% OR some features unavailable)
    #   "low"    (camera < 70% OR many features unavailable)
    confidence_band: str = "medium"

    # Temporal risk patterns (sustained risk, trajectory, prediction)
    temporal_risk: dict = field(default_factory=dict)

    # Ollama-generated plain-language explanation (populated post-scoring,
    # never in the critical path — a slow or failed LLM call never blocks
    # or corrupts the actual risk computation).
    ai_explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "session_id": self.session_id,
            "frame_number": self.frame_number,
            "captured_at": self.captured_at,
            "worker_id": self.worker_id,
            "base_risk": self.base_risk,
            "context_modifier": self.context_modifier,
            "fatigue_score": self.fatigue_score,
            "exposure_score": self.exposure_score,
            "confidence_modifier": self.confidence_modifier,
            "final_risk": self.final_risk,
            "risk_level": self.risk_level,
            "safety_state": self.safety_state,
            "movement_velocity": self.movement_velocity,
            "task_label": self.task_label,
            "task_confidence": self.task_confidence,
            "reason": self.reason,
            "active_rules": list(self.active_rules),
            "feature_scores": dict(self.feature_scores),
            "approximate_features": list(self.approximate_features),
            "standard_assessment": dict(self.standard_assessment),
            "confidence_band": self.confidence_band,
            "temporal_risk": self.temporal_risk,
            "ai_explanation": self.ai_explanation,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextSnapshot:
        """Deserialize from a dictionary."""
        return cls(
            session_id=data.get("session_id", ""),
            frame_number=data.get("frame_number", 0),
            captured_at=data.get("captured_at", ""),
            worker_id=data.get("worker_id", ""),
            base_risk=data.get("base_risk", 0.0),
            context_modifier=data.get("context_modifier", 0.0),
            fatigue_score=data.get("fatigue_score", 0.0),
            exposure_score=data.get("exposure_score", 0.0),
            confidence_modifier=data.get("confidence_modifier", 0.0),
            final_risk=data.get("final_risk", 0.0),
            risk_level=data.get("risk_level", "LOW"),
            safety_state=data.get("safety_state", "SAFE"),
            movement_velocity=data.get("movement_velocity", 0.0),
            reason=data.get("reason", ""),
            task_label=data.get("task_label", "Unknown"),
            task_confidence=data.get("task_confidence", 0.0),
            active_rules=tuple(data.get("active_rules", [])),
            feature_scores=data.get("feature_scores", {}),
            approximate_features=tuple(data.get("approximate_features", [])),
            standard_assessment=data.get("standard_assessment", {}),
            confidence_band=data.get("confidence_band", "medium"),
            temporal_risk=data.get("temporal_risk", {}),
            ai_explanation=data.get("ai_explanation", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> ContextSnapshot:
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(json_str))


# Backward-compatible alias
ContextResult = ContextSnapshot


# ── Engine ─────────────────────────────────────────────────────────

class ContextIntelligenceEngine:
    """Rule-based context-aware risk assessment engine.

    Usage::

        engine = ContextIntelligenceEngine()
        snapshot = engine.evaluate(
            features={"neck_flexion": 25.0, ...},
            issues=[...],
            task_name="Assembly Work",
            task_confidence=85.0,
            session_duration_seconds=1200.0,
            camera_confidence=92.0,
            delta_seconds=0.033,
        )
    """

    def __init__(self, session_id: str = "", worker_id: str = "") -> None:
        self._exposure = ExposureTracker()
        self._fatigue = FatigueModel()
        self._temporal_risk = TemporalRiskTracker()
        self._previous_state = "SAFE"
        self._state_since: float = 0.0
        self._session_id = session_id
        self._worker_id = worker_id
        self._frame_counter: int = 0
        # Risk-level dwell: the displayed level only changes once a strict
        # majority of the last N frames agree, so pose-estimation jitter or a
        # single post-smoothing spike can no longer flicker the badge or fire
        # an alert. While the window is still filling (warm-up), the raw level
        # is committed immediately so session start isn't delayed.
        try:
            self._level_dwell = max(1, int(os.environ.get("ERGOVIGILANCE_LEVEL_DWELL", "10") or "10"))
        except (TypeError, ValueError):
            self._level_dwell = 10
        self._level_history: deque[str] = deque(maxlen=self._level_dwell)
        self._last_committed_level: str = "LOW"

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def frame_counter(self) -> int:
        return self._frame_counter

    @property
    def exposure(self) -> ExposureTracker:
        return self._exposure

    @property
    def fatigue(self) -> FatigueModel:
        return self._fatigue

    def evaluate(
        self,
        features: dict[str, float],
        issues: list[dict],
        task_name: str,
        task_confidence: float,
        session_duration_seconds: float,
        camera_confidence: float,
        delta_seconds: float,
        captured_at: str = "",
        unavailable_features: list[str] | None = None,
        approximate_features: list[str] | None = None,
        lower_body_confidence: float = 0.0,
        standard_assessment: dict | None = None,
        joint_uncertainty: dict | None = None,
    ) -> ContextSnapshot:
        """Run the full context intelligence evaluation for one frame.

        Args:
            features: 7 ergonomic feature values.
            issues: Detected posture issues (from detect_posture_issues).
            task_name: Current task classification.
            task_confidence: Task recognition confidence (0-100).
            session_duration_seconds: Total session time.
            camera_confidence: MediaPipe landmark confidence (0-100).
            delta_seconds: Time since last frame.
            captured_at: ISO-8601 timestamp. Auto-generated if empty.

        Returns:
            ContextSnapshot with all risk assessments and explanations.
        """
        self._frame_counter += 1
        if not captured_at:
            captured_at = datetime.now(timezone.utc).isoformat()

        active_rules: list[str] = []

        # ── Step 0: Capture raw signals (passthrough, no risk impact) ──
        movement_velocity = features.get("movement_velocity", 0.0)

        # ── Step 1: Compute base risk from features ────────────────
        unavailable_set = set(unavailable_features or ())
        nan_features = {name for name in features if features.get(name, 0) != features.get(name, 0)}
        all_unavailable = unavailable_set | nan_features

        # The standard-method assessment (RULA/REBA) is the authoritative
        # posture-risk gate: risk fires only when a published rule is broken.
        # Its band anchors base_risk and the final level is capped so context
        # noise (confidence, minor fatigue) can never manufacture HIGH from a
        # LOW posture.
        std = standard_assessment or {}
        std_band = std.get("risk_level")
        std_valid = std_band in ("LOW", "MEDIUM", "HIGH")
        if std_valid:
            active_rules.append(
                f"standard_assessment: {std.get('method', '?')} score={std.get('score')} -> {std_band} ({std.get('reason', '')})"
            )

        feature_scores = {}
        active_feature_rules = _task_feature_rules(task_name, task_confidence)
        for feature, (med, high, inverted) in active_feature_rules.items():
            value = features.get(feature, 0.0)
            if feature in all_unavailable:
                feature_scores[feature] = float("nan")
            else:
                # Uncertainty-aware scoring: when the framing model estimates
                # per-joint angle uncertainty (sigma, degrees), the score near
                # a boundary is softened — P(rule violated) instead of a hard
                # cutoff — so pose jitter can no longer flip a feature between
                # 0 and 100. With no estimate (sigma 0) behavior is unchanged.
                sigma = 0.0
                if joint_uncertainty:
                    sigma = float(joint_uncertainty.get(feature, 0.0) or 0.0)
                score = self._score_feature(value, med, high, inverted, sigma)
                # Coerce to a plain python float — numpy scalars (from smoothed
                # or numpy-sourced feature values) break JSON serialization
                # downstream (pydantic cannot serialize numpy.float32/64).
                feature_scores[feature] = float(score)

        # Only features exceeding their own medium threshold contribute.
        # Among those, use a weighted combination: highest contributes fully,
        # each subsequent contributes with geometrically decaying weight.
        # Scale by the fraction of ALL features (not just visible ones) that
        # corroborate — the denominator is fixed at TOTAL_FEATURES so that
        # unavailable features don't artificially inflate the ratio.
        # Approximate features (computed via fallback, e.g. hip-free neck_flexion)
        # count at 0.5 toward n_exceeding — they are real data but less precise
        # (head-vs-image-vertical instead of head-vs-actual-trunk).
        approx_set = set(approximate_features or ())
        exceeding_items: list[tuple[float, bool]] = []
        for fname, score in feature_scores.items():
            if score == score and score > 0:
                exceeding_items.append((score, fname in approx_set))
        exceeding_items.sort(key=lambda x: x[0], reverse=True)
        if std_valid:
            # Anchor base risk to the standard band. A published rule was (or
            # was not) broken — that is the signal, not loose per-feature
            # cutoffs. Unavailable features are already accounted for by the
            # method choice (RULA for partial body), so no soft floor applies.
            _BAND_BASE = {"LOW": 20.0, "MEDIUM": 50.0, "HIGH": 80.0}
            base_risk = _BAND_BASE[std_band]
            active_rules.append(f"base_risk: anchored to standard {std_band} band (base={base_risk:.0f})")
        else:
            if exceeding_items:
                n_exceeding_effective = sum(0.5 if approx else 1.0 for _, approx in exceeding_items)
                weights = [1.0 / (2 ** i) for i in range(len(exceeding_items))]
                weighted_sum = sum(s * w for (s, _), w in zip(exceeding_items, weights))
                base_risk = min(100.0, weighted_sum * (n_exceeding_effective / len(active_feature_rules)))
            else:
                base_risk = 0.0

            if base_risk > 0:
                available_features = {f: s for f, s in feature_scores.items() if s == s}
                worst_feature = max(available_features, key=available_features.get)
                active_rules.append(f"base_risk: worst={worst_feature}={features.get(worst_feature, 0):.1f} score={feature_scores[worst_feature]:.0f}")
                if len(exceeding_items) > 1:
                    active_rules.append(f"weighted: {n_exceeding_effective:.1f}/{len(active_feature_rules)} effective exceed (base={base_risk:.1f})")

            # ── Step 1a: Assess what's available — no soft floor ────
            # Legacy behavior manufactured MEDIUM (soft floor 20-40) whenever
            # features couldn't be computed, so a worker half out of frame
            # was scored as elevated even when every visible feature was in
            # range. Per operator guidance we now assess only what IS
            # available: unavailable features simply don't contribute, and
            # the standard RULA/REBA gate already handles partial-body
            # visibility by scoring the visible half (RULA for top-half).
            if len(all_unavailable) > 0:
                active_rules.append(
                    f"unavailable_features: {len(all_unavailable)} excluded from scoring "
                    "(assessing available features only, no soft floor)"
                )

        # ── Step 2: Duration penalty ───────────────────────────────
        self._exposure.update(features, delta_seconds)
        duration_penalty = self._exposure.duration_penalty()
        exposure_score = self._exposure.exposure_score()

        if duration_penalty > 5:
            active_rules.append(f"duration_penalty: {duration_penalty:.1f} (exposure={self._exposure.current_exposure.total_high_risk_seconds:.0f}s)")

        # ── Step 3: Task modifier ──────────────────────────────────
        task_modifier = _TASK_MODIFIERS.get(task_name, 0)
        if task_modifier > 0 and task_confidence < 100:
            task_modifier = task_modifier * (task_confidence / 100.0)
        if task_modifier > 0:
            active_rules.append(f"task_modifier: {task_name}=+{task_modifier:.1f} (confidence={task_confidence:.0f}%)")

        # Log which threshold table is active for this frame
        from backend.services.features import task_thresholds as _tt
        if task_name in _tt and task_confidence >= 50.0:
            active_rules.append(f"task_thresholds: using {task_name} table (conf={task_confidence:.0f}%)")
        else:
            active_rules.append(f"task_thresholds: using baseline (task={task_name}, conf={task_confidence:.0f}%)")

        # ── Step 4: Fatigue modifier ───────────────────────────────
        self._fatigue.update(
            session_duration_seconds=session_duration_seconds,
            high_risk_seconds=self._exposure.current_exposure.total_high_risk_seconds,
            task_name=task_name,
            delta_seconds=delta_seconds,
        )
        fatigue_modifier = self._fatigue.fatigue_modifier()
        fatigue_score = self._fatigue.state.score

        if fatigue_modifier > 4:
            active_rules.append(f"fatigue_modifier: {fatigue_modifier:.1f} (level={self._fatigue.state.level})")

        # ── Step 5: Confidence modifier ────────────────────────────
        confidence_modifier = self._confidence_modifier(camera_confidence)

        if confidence_modifier < -2:
            active_rules.append(f"confidence_modifier: {confidence_modifier:.1f} (camera={camera_confidence:.0f}%)")

        # ── Step 6: Combine all modifiers ──────────────────────────
        context_modifier = duration_penalty + task_modifier + fatigue_modifier

        final_risk = max(0.0, min(100.0,
            base_risk + context_modifier + confidence_modifier
        ))

        # ── Step 7: Determine risk level ───────────────────────────
        risk_level = self._risk_level_from_score(final_risk)

        # Cap the level by the standard-method band so context noise can never
        # manufacture HIGH from a LOW posture: a neutral pose (RULA 1-2 /
        # REBA 1-3) is not "high risk" no matter how long the session runs or
        # how tired the model thinks the worker is. A MEDIUM posture may
        # escalate to HIGH only with real exposure/fatigue (sustained medium
        # posture all shift IS high risk per ergonomics); HIGH stays HIGH.
        if std_valid:
            _LEVEL_CAP = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "HIGH"}
            cap = _LEVEL_CAP[std_band]
            if RISK_ORDER[risk_level] > RISK_ORDER[cap]:
                risk_level = cap
                active_rules.append(f"standard_cap: {std_band} posture capped level at {cap}")

        # ── Step 7b: Level dwell (temporal hysteresis) ─────────────
        # Require a strict majority of the dwell window to change the level;
        # otherwise hold the last committed level. final_risk stays raw so
        # the gauge responds instantly — only the discrete level is smoothed.
        raw_level = risk_level
        risk_level = self._dwell_level(risk_level)
        if risk_level != raw_level:
            active_rules.append(
                f"level_dwell: held {risk_level} (window {len(self._level_history)}/{self._level_dwell}, raw {raw_level})"
            )

        # ── Step 8: Determine safety state ─────────────────────────
        safety_state = self._determine_state(final_risk, risk_level)

        # ── Step 9: Build confidence band ─────────────────────────
        # Derives a human-readable trust signal from camera quality,
        # feature completeness, and dwell stability.  This is what the
        # UI shows as "System Confidence: High / Medium / Low".
        n_unavailable = len(all_unavailable)
        n_total = len(active_feature_rules)
        feature_completeness = 1.0 - (n_unavailable / n_total) if n_total > 0 else 0.0
        dwell_stability = len(self._level_history) / max(self._level_dwell, 1)
        if camera_confidence >= 90 and feature_completeness >= 0.8 and dwell_stability >= 0.5:
            confidence_band = "high"
        elif camera_confidence >= 70 and feature_completeness >= 0.5:
            confidence_band = "medium"
        else:
            confidence_band = "low"
        active_rules.append(f"confidence_band: {confidence_band} (camera={camera_confidence:.0f}%, features={feature_completeness:.0%}, dwell={dwell_stability:.0%})")

        # ── Step 10: Build explanation ─────────────────────────────
        reason = self._build_reason(
            base_risk, context_modifier, fatigue_modifier,
            duration_penalty, task_modifier, confidence_modifier,
            final_risk, active_rules,
        )

        # ── Step 11: Temporal risk patterns ────────────────────────
        temporal_pattern = self._temporal_risk.update(final_risk, delta_seconds)
        temporal_risk = temporal_pattern.to_dict()
        
        if temporal_pattern.sustained_risk_seconds > 10:
            active_rules.append(f"temporal: elevated risk for {temporal_pattern.sustained_risk_seconds:.0f}s")
        if temporal_pattern.sustained_high_seconds > 5:
            active_rules.append(f"temporal: HIGH risk sustained for {temporal_pattern.sustained_high_seconds:.0f}s")
        if temporal_pattern.is_burst:
            active_rules.append(f"temporal: sudden spike (+{temporal_pattern.burst_magnitude:.1f} risk/sec)")
        if temporal_pattern.trajectory == "worsening" and temporal_pattern.trajectory_confidence > 60:
            active_rules.append(f"temporal: risk worsening (slope={temporal_pattern.trajectory_slope:.2f}, conf={temporal_pattern.trajectory_confidence:.0f}%)")

        return ContextSnapshot(
            session_id=self._session_id,
            frame_number=self._frame_counter,
            captured_at=captured_at,
            worker_id=self._worker_id,
            base_risk=base_risk,
            context_modifier=context_modifier,
            fatigue_score=fatigue_score,
            exposure_score=exposure_score,
            confidence_modifier=confidence_modifier,
            final_risk=final_risk,
            risk_level=risk_level,
            safety_state=safety_state,
            movement_velocity=movement_velocity,
            unavailable_features=tuple(unavailable_features or ()),
            approximate_features=tuple(approximate_features or ()),
            lower_body_confidence=lower_body_confidence,
            task_label=task_name,
            task_confidence=task_confidence,
            reason=reason,
            active_rules=tuple(active_rules),
            feature_scores=feature_scores,
            standard_assessment=dict(std) if std_valid else {},
            confidence_band=confidence_band,
            temporal_risk=temporal_risk,
        )

    def reset(self) -> None:
        """Reset all internal state (e.g., on session restart)."""
        self._exposure.reset()
        self._fatigue.reset()
        self._temporal_risk.reset()
        self._previous_state = "SAFE"
        self._state_since = 0.0
        self._frame_counter = 0
        self._level_history.clear()
        self._last_committed_level = "LOW"

    def _dwell_level(self, level: str) -> str:
        """Temporal hysteresis on the discrete risk level.

        Appends the raw level to a rolling window. While the window is still
        filling (warm-up) the raw level is committed immediately. Once full,
        the level only changes when a strict majority of the window agrees;
        otherwise the last committed level is held — a one-frame spike can
        never flip the displayed level or trigger an alert.
        """
        self._level_history.append(level)
        hist = list(self._level_history)
        if len(hist) < self._level_dwell:
            self._last_committed_level = level
            return level
        winner, count = Counter(hist).most_common(1)[0]
        if count * 2 > len(hist):  # strict majority
            self._last_committed_level = winner
            return winner
        return self._last_committed_level

    # ── Private Helpers ────────────────────────────────────────────

    @staticmethod
    def _score_feature(value: float, medium: float, high: float, inverted: bool,
                       sigma: float = 0.0) -> float:
        """Score a single feature on a 0-100 scale.

        With ``sigma > 0`` the score becomes uncertainty-aware: it is the
        expected value of the hard score over a Gaussian angle distribution
        centered on ``value`` with std ``sigma`` — i.e. P(rule violated)
        rather than a hard cutoff. At the exact boundary a deterministic
        scorer would snap 0->100 (boundary-flip sensitivity); the soft
        version lands at ~25 (medium) / ~75 (high), so a jittering angle
        near a threshold produces a smooth gradient instead of a flip.
        With ``sigma == 0`` (no uncertainty estimate) the original hard
        interpolation is used, keeping legacy callers byte-identical.
        """
        if sigma is None or sigma <= 0:
            sigma = 0.0
            if inverted:
                # Lower value = higher risk (e.g., knee_angle)
                if value <= high:
                    return 100.0
                if value >= medium:
                    return 0.0
                return (medium - value) / (medium - high) * 100.0
            else:
                # Higher value = higher risk (e.g., neck_flexion)
                if value >= high:
                    return 100.0
                if value <= medium:
                    return 0.0
                return (value - medium) / (high - medium) * 100.0

        from math import erf

        def _phi(x: float) -> float:
            """Standard normal CDF (approximation is unnecessary — math.erf)."""
            return 0.5 * (1.0 + erf(x / 1.4142135623730951))

        if inverted:
            # Risk when the true value is BELOW the threshold.
            p_med = _phi((medium - value) / sigma)   # P(true < medium)
            p_high = _phi((high - value) / sigma)    # P(true < high)
        else:
            # Risk when the true value is ABOVE the threshold.
            p_med = 1.0 - _phi((medium - value) / sigma)
            p_high = 1.0 - _phi((high - value) / sigma)
        # Expected score = 100 * P(high) + 50 * P(medium-only).
        return 50.0 * p_med + 50.0 * p_high

    @staticmethod
    def _confidence_modifier(camera_confidence: float) -> float:
        """Compute confidence modifier based on camera confidence."""
        if camera_confidence >= _CONFIDENCE_HIGH:
            return 0.0
        if camera_confidence >= _CONFIDENCE_MEDIUM:
            return -1.5
        if camera_confidence >= _CONFIDENCE_LOW:
            return -4.0
        return -6.0

    @staticmethod
    def _risk_level_from_score(score: float) -> str:
        """Convert a 0-100 risk score to a risk level string."""
        if score >= 70:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    def _determine_state(self, final_risk: float, risk_level: str) -> str:
        """Determine safety state with hysteresis logic."""
        if risk_level == "HIGH" and self._previous_state != "CRITICAL":
            self._previous_state = "CRITICAL"
        elif risk_level == "MEDIUM" and self._previous_state == "CRITICAL":
            self._previous_state = "OBSERVE"
        elif risk_level == "MEDIUM" and self._previous_state == "SAFE":
            self._previous_state = "OBSERVE"
        elif risk_level == "LOW" and self._previous_state in ("OBSERVE",):
            self._previous_state = "SAFE"
        elif risk_level == "LOW" and self._previous_state == "CRITICAL":
            self._previous_state = "RECOVERY"
        elif risk_level == "LOW" and self._previous_state == "RECOVERY":
            self._previous_state = "SAFE"

        return self._previous_state

    @staticmethod
    def _build_reason(
        base_risk: float,
        context_modifier: float,
        fatigue_modifier: float,
        duration_penalty: float,
        task_modifier: float,
        confidence_modifier: float,
        final_risk: float,
        active_rules: list[str],
    ) -> str:
        """Build a human-readable explanation of the risk assessment."""
        parts = []
        parts.append(f"Base risk: {base_risk:.0f}")
        if context_modifier != 0:
            parts.append(f"Context modifier: +{context_modifier:.1f}")
        if fatigue_modifier > 0:
            parts.append(f"Fatigue: +{fatigue_modifier:.1f}")
        if duration_penalty > 0:
            parts.append(f"Duration: +{duration_penalty:.1f}")
        if task_modifier > 0:
            parts.append(f"Task: +{task_modifier}")
        if confidence_modifier < 0:
            parts.append(f"Confidence: {confidence_modifier:.1f}")
        parts.append(f"Final: {final_risk:.0f}")
        return " | ".join(parts)


def generate_ai_explanation(snapshot: ContextSnapshot) -> str:
    """Generate a plain-language explanation from a completed risk assessment.

    This function calls Ollama **after** scoring is complete — it is never
    in the critical path.  A slow or failed LLM response returns an empty
    string rather than blocking or corrupting the monitoring pipeline.

    The prompt includes only structured, already-computed results: the
    classified task, risk level, key features, and which thresholds were
    applied.  Ollama narrates the result; it does not compute it.
    """
    import os
    import logging
    import requests as _requests

    logger = logging.getLogger(__name__)

    ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

    # Build a structured prompt from the already-computed snapshot
    features_of_interest = []
    for fname in ["neck_flexion", "trunk_flexion", "left_shoulder_elev",
                  "right_shoulder_elev", "knee_angle", "wrist_deviation_angle"]:
        val = snapshot.feature_scores.get(fname)
        if val is not None and val == val:  # not NaN
            features_of_interest.append(f"{fname}={val:.1f}")

    std = snapshot.standard_assessment
    std_info = f"{std.get('method', '?')} score={std.get('score', '?')} -> {std.get('risk_level', '?')}" if std else "N/A"

    prompt = (
        f"You are an ergonomic risk assistant. Given these ALREADY-COMPUTED results, "
        f"write ONE concise sentence (max 25 words) explaining the risk to a safety manager. "
        f"Do NOT compute or classify anything — just narrate what is shown.\n\n"
        f"Task: {snapshot.task_label} (confidence {snapshot.task_confidence:.0f}%)\n"
        f"Risk level: {snapshot.risk_level} (score {snapshot.final_risk:.0f}/100)\n"
        f"Standard assessment: {std_info}\n"
        f"Key features: {', '.join(features_of_interest)}\n"
        f"Thresholds used: {snapshot.task_label if snapshot.task_label in ('Lifting / Picking', 'Assembly Work', 'Reaching', 'Inspection', 'Walking / Moving', 'Seated Work') else 'baseline'}\n\n"
        f"Explanation:"
    )

    try:
        resp = _requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.3, "num_predict": 60}},
            timeout=5.0,
        )
        if resp.ok:
            data = resp.json()
            return data.get("response", "").strip()
    except Exception:
        logger.debug("Ollama explanation failed — returning empty", exc_info=True)

    return ""
