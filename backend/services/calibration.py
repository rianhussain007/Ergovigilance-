"""Posture-risk calibration — how much bend/strain counts as risk.

The published RULA (McAtamney & Corlett, 1993) and REBA (Hignett &
McAtamney, 2000) breakpoints are deliberately strict: any trunk flexion
above 0° scores 2, any wrist deviation above ~5° scores 2, upper arms
past 20° score 2, neck past 10° scores 2. On a 2D webcam feed those
bands sit exactly on top of pose-estimation jitter (±5-10°) and
perfectly normal work envelopes (typing, assembly, light reach), so the
live system flashed yellow/red on the slightest movement.

This module adds a calibration layer so the operator decides how much
bend/strain is acceptable before a joint starts scoring. It drives the
authoritative RULA/REBA gate (``standard_assessment``), the per-feature
segment colors (``risk_breakdown``) and the issue rules
(``detect_posture_issues``).

Two named presets plus a full JSON override via ``RISK_CALIBRATION``::

    RISK_CALIBRATION=standard  -> published breakpoints (strict)
    RISK_CALIBRATION=relaxed   -> widened neutral bands (default)
    RISK_CALIBRATION='{"trunk_neutral_max": 15, "neck_neutral_max": 20, ...}'
                              -> custom (merged over RELAXED)

Two deliberate exclusions keep existing contracts intact:

- ``risk_from_features`` / ``RISK_THRESHOLDS`` (the legacy gate and its
  tuned cutoffs) are NOT calibrated — the REBA-tuning regression tests
  pin their agreement/kappa/no-missed-HIGH properties, and the tuned set
  already absorbed the two worst over-alarmers (weight_shift, symmetry).
- ``reba_from_keypoints`` (the REBA scorer used to LABEL the training
  dataset) defaults to STANDARD so calibration-time labels keep the
  published methodology; only the live gate passes a relaxed profile.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Mapping, Tuple

# feature -> (MEDIUM cutoff, HIGH cutoff) for segment colors + issues.
# alignment_deviation is intentionally absent: risk_breakdown() and the
# issue rules each keep their own documented handling of it.
_STANDARD_FEATURE_CUTOFFS: Mapping[str, Tuple[float, float]] = {
    "neck_flexion": (10.0, 30.0),
    "trunk_flexion": (20.0, 60.0),
    "shoulder_elev": (30.0, 60.0),
    "left_shoulder_elev": (30.0, 60.0),
    "right_shoulder_elev": (30.0, 60.0),
    "shoulder_symmetry": (9.0, 18.0),
    "knee_angle": (150.0, 100.0),  # inverted: lower = riskier
    "forward_head_posture": (10.0, 20.0),
    "head_tilt_angle": (10.0, 20.0),
    "wrist_deviation_angle": (5.0, 15.0),
    "stance_stability": (0.7, 0.5),  # inverted: lower = riskier
    "weight_shift_offset": (12.5, 25.0),
}

# Relaxed: widen only the jitter-prone posture features. shoulder_symmetry
# and weight_shift_offset keep their REBA-tuned cutoffs (already loosened);
# alignment_deviation is untouched (handled by each consumer).
_RELAXED_FEATURE_CUTOFFS: Mapping[str, Tuple[float, float]] = {
    "neck_flexion": (15.0, 35.0),
    "trunk_flexion": (30.0, 70.0),
    "shoulder_elev": (35.0, 60.0),
    "left_shoulder_elev": (35.0, 60.0),
    "right_shoulder_elev": (35.0, 60.0),
    "shoulder_symmetry": (9.0, 18.0),
    "knee_angle": (140.0, 95.0),
    "forward_head_posture": (15.0, 28.0),
    "head_tilt_angle": (15.0, 28.0),
    "wrist_deviation_angle": (10.0, 25.0),
    "stance_stability": (0.6, 0.45),
    "weight_shift_offset": (15.0, 30.0),
}


@dataclass(frozen=True)
class PostureCalibration:
    """Angle breakpoints that decide when a joint starts scoring risk.

    Every field is a degrees/ratio threshold; values between breakpoints
    keep the same monotonic escalation the published methods use, so a
    genuinely severe posture always out-scores a mild one regardless of
    the profile.
    """

    name: str = "relaxed"

    # Trunk flexion (deg): <= trunk_neutral_max -> 1, <= trunk_medium_max
    # -> 2, <= trunk_high_max -> 3, above -> 4.
    trunk_neutral_max: float = 10.0
    trunk_medium_max: float = 30.0
    trunk_high_max: float = 60.0

    # Neck flexion (deg): <= neck_neutral_max -> 1, <= neck_high_max -> 2,
    # above -> 3; head tilt beyond neck_side_bend_max adds +1.
    neck_neutral_max: float = 15.0
    neck_high_max: float = 30.0
    neck_side_bend_max: float = 25.0

    # Upper-arm angle from vertical (deg): neutral / medium / high bands.
    upper_arm_neutral_max: float = 30.0
    upper_arm_medium_max: float = 60.0
    upper_arm_high_max: float = 110.0
    # Shoulder elevation (deg) beyond which +1 is added (raised shoulder).
    shoulder_elev_deg: float = 40.0

    # Lower-arm / elbow flexion (deg) that counts as neutral range.
    elbow_neutral_min: float = 50.0
    elbow_neutral_max: float = 120.0

    # Wrist deviation (deg): neutral / medium bands.
    wrist_neutral_max: float = 10.0
    wrist_medium_max: float = 25.0

    # Knee flexion for REBA legs (deg): beyond medium -> +1, high -> +2.
    knee_medium_max: float = 40.0
    knee_high_max: float = 75.0

    # RULA legs: stance_stability below this counts as unsupported.
    stance_stability_neutral: float = 0.45

    # Per-feature (MEDIUM, HIGH) cutoffs for segment colors + issues.
    feature_cutoffs: Mapping[str, Tuple[float, float]] = field(
        default_factory=lambda: dict(_RELAXED_FEATURE_CUTOFFS)
    )


STANDARD = PostureCalibration(
    name="standard",
    trunk_neutral_max=0.0,
    trunk_medium_max=20.0,
    trunk_high_max=60.0,
    neck_neutral_max=10.0,
    neck_high_max=20.0,
    neck_side_bend_max=20.0,
    upper_arm_neutral_max=20.0,
    upper_arm_medium_max=45.0,
    upper_arm_high_max=90.0,
    shoulder_elev_deg=30.0,
    elbow_neutral_min=60.0,
    elbow_neutral_max=100.0,
    wrist_neutral_max=5.0,
    wrist_medium_max=15.0,
    knee_medium_max=30.0,
    knee_high_max=60.0,
    stance_stability_neutral=0.5,
    feature_cutoffs=_STANDARD_FEATURE_CUTOFFS,
)

RELAXED = PostureCalibration()  # defaults above


@lru_cache(maxsize=8)
def load_calibration(raw: str | None = None) -> PostureCalibration:
    """Resolve the calibration profile from ``raw`` or ``RISK_CALIBRATION``.

    ``"standard"`` / ``"relaxed"`` select a named preset; a JSON object
    (e.g. ``'{"trunk_neutral_max": 15}'``) is merged over RELAXED for
    fine-grained operator control; anything else falls back to RELAXED.
    Cached so per-frame calls never re-parse.
    """
    value = (raw if raw is not None else os.getenv("RISK_CALIBRATION", "")).strip()
    if not value:
        return RELAXED
    low = value.lower()
    if low == "standard":
        return STANDARD
    if low == "relaxed":
        return RELAXED
    try:
        data = json.loads(value)
    except (ValueError, TypeError):
        return RELAXED
    if not isinstance(data, dict):
        return RELAXED
    kwargs: dict = {}
    for key, val in data.items():
        if key in RELAXED.__dataclass_fields__ and key != "feature_cutoffs":
            try:
                kwargs[key] = float(val)
            except (TypeError, ValueError):
                continue
    cutoffs = dict(RELAXED.feature_cutoffs)
    raw_cutoffs = data.get("feature_cutoffs")
    if isinstance(raw_cutoffs, dict):
        for key, pair in raw_cutoffs.items():
            try:
                cutoffs[str(key)] = (float(pair[0]), float(pair[1]))
            except (TypeError, ValueError, IndexError):
                continue
    kwargs["feature_cutoffs"] = cutoffs
    return replace(RELAXED, name="custom", **kwargs)
