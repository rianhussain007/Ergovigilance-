"""Context Intelligence Engine — the reasoning core of ErgoVigilance.

Combines biomechanical features with temporal, task, fatigue, and exposure
context to produce a context-adjusted risk assessment as a ContextSnapshot.

100% deterministic. Rule-based. No ML.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.context.exposure import ExposureTracker
from backend.context.fatigue import FatigueModel
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


# ── Task Modifiers ─────────────────────────────────────────────────

_TASK_MODIFIERS: dict[str, float] = {
    "Neutral Standing": 0,
    "Assembly Work": 5,
    "Reaching": 8,
    "Lifting / Picking": 12,
    "Inspection": 3,
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

    # Explainability
    reason: str = ""
    active_rules: tuple[str, ...] = ()
    feature_scores: dict[str, float] = field(default_factory=dict)

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
            "reason": self.reason,
            "active_rules": list(self.active_rules),
            "feature_scores": dict(self.feature_scores),
            "approximate_features": list(self.approximate_features),
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
            active_rules=tuple(data.get("active_rules", [])),
            feature_scores=data.get("feature_scores", {}),
            approximate_features=tuple(data.get("approximate_features", [])),
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
        self._previous_state = "SAFE"
        self._state_since: float = 0.0
        self._session_id = session_id
        self._worker_id = worker_id
        self._frame_counter: int = 0

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

        feature_scores = {}
        for feature, (med, high, inverted) in _FEATURE_RULES.items():
            value = features.get(feature, 0.0)
            if feature in all_unavailable:
                feature_scores[feature] = float("nan")
            else:
                score = self._score_feature(value, med, high, inverted)
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
        if exceeding_items:
            n_exceeding_effective = sum(0.5 if approx else 1.0 for _, approx in exceeding_items)
            weights = [1.0 / (2 ** i) for i in range(len(exceeding_items))]
            weighted_sum = sum(s * w for (s, _), w in zip(exceeding_items, weights))
            base_risk = min(100.0, weighted_sum * (n_exceeding_effective / len(_FEATURE_RULES)))
        else:
            base_risk = 0.0

        if base_risk > 0:
            available_features = {f: s for f, s in feature_scores.items() if s == s}
            worst_feature = max(available_features, key=available_features.get)
            active_rules.append(f"base_risk: worst={worst_feature}={features.get(worst_feature, 0):.1f} score={feature_scores[worst_feature]:.0f}")
            if len(exceeding_items) > 1:
                active_rules.append(f"weighted: {n_exceeding_effective:.1f}/{len(_FEATURE_RULES)} effective exceed (base={base_risk:.1f})")

        # ── Step 1a: Apply soft floor for unavailable features ────────
        # Define soft floors:
        # 0 unavailable: no floor
        # 1 lower-body: 25.0
        # 1 upper-body: 20.0
        # ≥2: 40.0
        # Group features into lower vs upper body
        lower_body_features = {"trunk_flexion", "knee_angle", "stance_stability", "weight_shift_offset"}
        upper_body_features = {"neck_flexion", "left_shoulder_elev", "right_shoulder_elev", "shoulder_symmetry", "alignment_deviation", "forward_head_posture", "head_tilt_angle", "wrist_deviation_angle"}
        unavailable_lower = len(all_unavailable & lower_body_features)
        unavailable_upper = len(all_unavailable & upper_body_features)
        total_unavailable = len(all_unavailable)

        soft_floor = 0.0
        if total_unavailable > 0:
            if total_unavailable >= 2:
                soft_floor = 40.0
            elif unavailable_lower > 0:
                soft_floor = 25.0
            else:
                soft_floor = 20.0
            active_rules.append(f"unavailable_features: {len(all_unavailable)} (lower={unavailable_lower}, upper={unavailable_upper}) -> soft_floor={soft_floor:.1f}")

        base_risk = max(base_risk, soft_floor)

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

        # ── Step 8: Determine safety state ─────────────────────────
        safety_state = self._determine_state(final_risk, risk_level)

        # ── Step 9: Build explanation ──────────────────────────────
        reason = self._build_reason(
            base_risk, context_modifier, fatigue_modifier,
            duration_penalty, task_modifier, confidence_modifier,
            final_risk, active_rules,
        )

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
            reason=reason,
            active_rules=tuple(active_rules),
            feature_scores=feature_scores,
        )

    def reset(self) -> None:
        """Reset all internal state (e.g., on session restart)."""
        self._exposure.reset()
        self._fatigue.reset()
        self._previous_state = "SAFE"
        self._state_since = 0.0
        self._frame_counter = 0

    # ── Private Helpers ────────────────────────────────────────────

    @staticmethod
    def _score_feature(value: float, medium: float, high: float, inverted: bool) -> float:
        """Score a single feature on a 0-100 scale."""
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
