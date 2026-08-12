"""Exposure Tracker — cumulative risk exposure over time.

Tracks how long each risk factor has been above its MEDIUM threshold and
how long it has been beyond its HIGH threshold. Used by the Context
Intelligence Engine to compute duration penalties.

The thresholds are read from the ACTIVE posture calibration
(``load_calibration()``), the same profile that drives the live RULA/REBA
risk gate — so a mild posture can no longer be double-penalized: a wrist
deviation of 20 deg with the relaxed profile (MEDIUM 10 / HIGH 25) accrues
wrist exposure but does NOT count as "high-risk seconds" that inflate the
duration penalty. Previously the exposure tracker used the published
strict cutoffs (wrist HIGH 15) while the live gate used the relaxed ones
(wrist HIGH 25), so the same mild posture was counted as high-risk twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.calibration import load_calibration

# Features where LOWER value means higher risk.
_INVERTED_FEATURES = {"knee_angle", "stance_stability"}

# Fallbacks only for features the calibration feature_cutoffs table omits
# (alignment_deviation is intentionally absent there; everything else is
# present in both the STANDARD and RELAXED profiles).
_ALIGNMENT_DEFAULTS = (20.0, 50.0)  # (MEDIUM, HIGH) — matches the engine rules


@dataclass
class ExposureVector:
    """Cumulative exposure to each risk factor."""
    neck_flexion_seconds: float = 0.0
    trunk_flexion_seconds: float = 0.0
    shoulder_elevation_seconds: float = 0.0
    knee_angle_seconds: float = 0.0
    alignment_seconds: float = 0.0
    forward_head_seconds: float = 0.0
    head_tilt_seconds: float = 0.0
    wrist_deviation_seconds: float = 0.0
    stance_seconds: float = 0.0
    weight_shift_seconds: float = 0.0
    total_high_risk_seconds: float = 0.0
    peak_neck_flexion: float = 0.0
    peak_trunk_flexion: float = 0.0


_FEATURES_ORDER = [
    "neck_flexion", "trunk_flexion",
    "left_shoulder_elev", "right_shoulder_elev", "shoulder_symmetry",
    "alignment_deviation", "knee_angle",
    "forward_head_posture", "head_tilt_angle",
    "wrist_deviation_angle", "stance_stability", "weight_shift_offset",
]


class ExposureTracker:
    """Tracks cumulative exposure to ergonomic risk factors.

    Call update() once per frame with the current features and delta time.
    Read the exposure vector at any time via current_exposure.
    """

    def __init__(self, calibration=None) -> None:
        self._exposure = ExposureVector()
        self._high_risk_seconds: float = 0.0
        # MEDIUM/HIGH cutoffs per feature, derived from the active posture
        # calibration (same profile as the live risk gate).
        cal = calibration if calibration is not None else load_calibration()
        cutoffs = dict(getattr(cal, "feature_cutoffs", {}) or {})
        self._medium: dict[str, float] = {}
        self._high: dict[str, float] = {}
        for feature in _FEATURES_ORDER:
            med, high = cutoffs.get(feature, _ALIGNMENT_DEFAULTS)
            self._medium[feature] = float(med)
            self._high[feature] = float(high)

    def _above_medium(self, feature: str, value: float) -> bool:
        """True when the feature exceeds its MEDIUM cutoff (inverted-aware)."""
        if feature in _INVERTED_FEATURES:
            return value < self._medium[feature]
        return value > self._medium[feature]

    def _beyond_high(self, feature: str, value: float) -> bool:
        """True when the feature exceeds its HIGH cutoff (inverted-aware)."""
        if feature in _INVERTED_FEATURES:
            return value < self._high[feature]
        return value > self._high[feature]

    @property
    def current_exposure(self) -> ExposureVector:
        return self._exposure

    def update(self, features: dict[str, float], delta_seconds: float) -> None:
        """Update exposure counters for one frame.

        Args:
            features: Current feature values.
            delta_seconds: Time since last update.
        """
        if delta_seconds <= 0:
            return

        neck = features.get("neck_flexion", 0.0)
        trunk = features.get("trunk_flexion", 0.0)
        left_shoulder = features.get("left_shoulder_elev", 0.0)
        right_shoulder = features.get("right_shoulder_elev", 0.0)
        shoulder_sym = features.get("shoulder_symmetry", 0.0)
        alignment = features.get("alignment_deviation", 0.0)
        knee = features.get("knee_angle", 180.0)
        fhp = features.get("forward_head_posture", 0.0)
        head_tilt = features.get("head_tilt_angle", 0.0)
        wrist_dev = features.get("wrist_deviation_angle", 0.0)
        stance = features.get("stance_stability", 1.0)
        weight_shift = features.get("weight_shift_offset", 0.0)

        # Track peaks
        if neck > self._exposure.peak_neck_flexion:
            self._exposure.peak_neck_flexion = neck
        if trunk > self._exposure.peak_trunk_flexion:
            self._exposure.peak_trunk_flexion = trunk

        # Accumulate exposure for each feature above its MEDIUM cutoff
        # (calibration-driven, inverted-aware).
        if self._above_medium("neck_flexion", neck):
            self._exposure.neck_flexion_seconds += delta_seconds
        if self._above_medium("trunk_flexion", trunk):
            self._exposure.trunk_flexion_seconds += delta_seconds
        if self._above_medium("left_shoulder_elev", left_shoulder) or \
           self._above_medium("right_shoulder_elev", right_shoulder) or \
           self._above_medium("shoulder_symmetry", shoulder_sym):
            self._exposure.shoulder_elevation_seconds += delta_seconds
        if self._above_medium("knee_angle", knee):
            self._exposure.knee_angle_seconds += delta_seconds
        if self._above_medium("alignment_deviation", alignment):
            self._exposure.alignment_seconds += delta_seconds
        # Phase-A exposure accumulation (NaN comparisons are False -> skipped)
        if self._above_medium("forward_head_posture", fhp):
            self._exposure.forward_head_seconds += delta_seconds
        if self._above_medium("head_tilt_angle", head_tilt):
            self._exposure.head_tilt_seconds += delta_seconds
        if self._above_medium("wrist_deviation_angle", wrist_dev):
            self._exposure.wrist_deviation_seconds += delta_seconds
        if self._above_medium("stance_stability", stance):
            self._exposure.stance_seconds += delta_seconds
        if self._above_medium("weight_shift_offset", weight_shift):
            self._exposure.weight_shift_seconds += delta_seconds

        # Track total time with ANY feature beyond its HIGH cutoff
        # (calibration-driven — same bands as the live risk gate).
        has_high_risk = (
            self._beyond_high("neck_flexion", neck)
            or self._beyond_high("trunk_flexion", trunk)
            or self._beyond_high("left_shoulder_elev", left_shoulder)
            or self._beyond_high("right_shoulder_elev", right_shoulder)
            or self._beyond_high("shoulder_symmetry", shoulder_sym)
            or self._beyond_high("alignment_deviation", alignment)
            or self._beyond_high("knee_angle", knee)
            or self._beyond_high("forward_head_posture", fhp)
            or self._beyond_high("head_tilt_angle", head_tilt)
            or self._beyond_high("wrist_deviation_angle", wrist_dev)
            or self._beyond_high("stance_stability", stance)
            or self._beyond_high("weight_shift_offset", weight_shift)
        )
        if has_high_risk:
            self._exposure.total_high_risk_seconds += delta_seconds
            self._high_risk_seconds += delta_seconds

    def reset(self) -> None:
        """Reset all exposure counters (e.g., on session restart)."""
        self._exposure = ExposureVector()
        self._high_risk_seconds = 0.0

    def duration_penalty(self) -> float:
        """Compute the duration penalty (0-30) from cumulative high-risk exposure.

        Graded exposure curve (doc §8 — posture-endurance research, not
        RULA's coarse binary ">1 minute" flag):

          < 1 min       -> 0        (grace — a momentary posture costs nothing)
          1-5 min       -> 0-8      (mild — "moderate" posture, hold < 1 min)
          5-15 min      -> 8-20     (uncomfortable — not recommended to sustain)
          15-30 min     -> 20-30    (low-back complaints onset ~15 min, rising
                                     sharply past ~30 min)
          > 30 min      -> 30       (cap)

        A MEDIUM-risk angle sustained for 8 minutes scores materially higher
        than the same angle held for 20 seconds — the mathematical version of
        the "continuous monitoring beats a point-in-time audit" pitch.

        Returns:
            Penalty score from 0 (no exposure) to 30 (30+ min sustained).
        """
        seconds = self._exposure.total_high_risk_seconds
        if seconds < 60:
            return 0.0
        if seconds < 300:      # 1-5 min: 0 -> 8
            return (seconds - 60) / 240.0 * 8.0
        if seconds < 900:      # 5-15 min: 8 -> 20
            return 8.0 + (seconds - 300) / 600.0 * 12.0
        if seconds < 1800:     # 15-30 min: 20 -> 30
            return 20.0 + (seconds - 900) / 900.0 * 10.0
        return 30.0

    def exposure_score(self) -> float:
        """Compute a normalized exposure score (0-100).

        Returns:
            Score based on total weighted exposure across all features.
        """
        total = (
            self._exposure.neck_flexion_seconds * 1.5 +
            self._exposure.trunk_flexion_seconds * 1.3 +
            self._exposure.shoulder_elevation_seconds * 1.2 +
            self._exposure.knee_angle_seconds * 1.0 +
            self._exposure.alignment_seconds * 1.1 +
            self._exposure.forward_head_seconds * 1.0 +
            self._exposure.head_tilt_seconds * 1.0 +
            self._exposure.wrist_deviation_seconds * 1.2 +
            self._exposure.stance_seconds * 1.0 +
            self._exposure.weight_shift_seconds * 1.0
        )
        # Normalize: 300 seconds of weighted exposure = score 100
        return min(total / 300.0 * 100.0, 100.0)
