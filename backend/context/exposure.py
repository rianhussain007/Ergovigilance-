"""Exposure Tracker — cumulative risk exposure over time.

Tracks how long each risk factor has been above its medium threshold.
Used by the Context Intelligence Engine to compute duration penalties.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Feature thresholds above which exposure is counted (medium threshold).
_EXPOSURE_THRESHOLDS = {
    "neck_flexion": 10.0,
    "trunk_flexion": 20.0,
    "left_shoulder_elev": 30.0,
    "right_shoulder_elev": 30.0,
    "shoulder_symmetry": 5.0,
    "alignment_deviation": 10.0,
    "knee_angle": 150.0,  # inverted: below 150 is risky
}

# Features where LOWER value means higher risk.
_INVERTED_FEATURES = {"knee_angle"}


@dataclass
class ExposureVector:
    """Cumulative exposure to each risk factor."""
    neck_flexion_seconds: float = 0.0
    trunk_flexion_seconds: float = 0.0
    shoulder_elevation_seconds: float = 0.0
    knee_angle_seconds: float = 0.0
    alignment_seconds: float = 0.0
    total_high_risk_seconds: float = 0.0
    peak_neck_flexion: float = 0.0
    peak_trunk_flexion: float = 0.0


class ExposureTracker:
    """Tracks cumulative exposure to ergonomic risk factors.

    Call update() once per frame with the current features and delta time.
    Read the exposure vector at any time via current_exposure.
    """

    def __init__(self) -> None:
        self._exposure = ExposureVector()
        self._high_risk_seconds: float = 0.0

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

        # Track peaks
        if neck > self._exposure.peak_neck_flexion:
            self._exposure.peak_neck_flexion = neck
        if trunk > self._exposure.peak_trunk_flexion:
            self._exposure.peak_trunk_flexion = trunk

        # Accumulate exposure for each feature above its threshold
        if neck > _EXPOSURE_THRESHOLDS["neck_flexion"]:
            self._exposure.neck_flexion_seconds += delta_seconds
        if trunk > _EXPOSURE_THRESHOLDS["trunk_flexion"]:
            self._exposure.trunk_flexion_seconds += delta_seconds
        if left_shoulder > _EXPOSURE_THRESHOLDS["left_shoulder_elev"] or \
           right_shoulder > _EXPOSURE_THRESHOLDS["right_shoulder_elev"] or \
           shoulder_sym > _EXPOSURE_THRESHOLDS["shoulder_symmetry"]:
            self._exposure.shoulder_elevation_seconds += delta_seconds
        if knee < _EXPOSURE_THRESHOLDS["knee_angle"]:
            self._exposure.knee_angle_seconds += delta_seconds
        if alignment > _EXPOSURE_THRESHOLDS["alignment_deviation"]:
            self._exposure.alignment_seconds += delta_seconds

        # Track total time with ANY high-risk feature
        has_high_risk = (
            neck > 30.0 or trunk > 60.0 or
            left_shoulder > 60.0 or right_shoulder > 60.0 or
            shoulder_sym > 15.0 or alignment > 25.0 or
            knee < 100.0
        )
        if has_high_risk:
            self._exposure.total_high_risk_seconds += delta_seconds
            self._high_risk_seconds += delta_seconds

    def reset(self) -> None:
        """Reset all exposure counters (e.g., on session restart)."""
        self._exposure = ExposureVector()
        self._high_risk_seconds = 0.0

    def duration_penalty(self) -> float:
        """Compute the duration penalty (0-30) based on cumulative high-risk exposure.

        Returns:
            Penalty score from 0 (no exposure) to 30 (5+ minutes of high risk).
        """
        seconds = self._exposure.total_high_risk_seconds
        return min(seconds / 10.0, 30.0)

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
            self._exposure.alignment_seconds * 1.1
        )
        # Normalize: 300 seconds of weighted exposure = score 100
        return min(total / 300.0 * 100.0, 100.0)
