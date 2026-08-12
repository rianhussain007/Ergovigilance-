"""Regression tests for unknown-feature handling in risk_from_features.

The video-analysis pipeline processes arbitrary recorded videos whose framing
differs from the live feed, which exposed a latent KeyError: per-side shoulder
features (``left_shoulder_elev`` / ``right_shoulder_elev``) were looked up in
``_UNKNOWN_VALUES`` which only had the aggregated ``shoulder_elev`` key. Any
frame with those features NaN or explicitly unavailable crashed the whole
analysis job. These tests pin the fail-closed behavior.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.features import risk_from_features  # noqa: E402


def _base_features() -> dict[str, float]:
    return {
        "neck_flexion": 9.0,
        "trunk_flexion": 12.0,
        "left_shoulder_elev": 15.0,
        "right_shoulder_elev": 12.0,
        "shoulder_symmetry": 4.0,
        "knee_angle": 165.0,
        "forward_head_posture": 6.0,
        "head_tilt_angle": 5.0,
        "wrist_deviation_angle": 4.0,
        "stance_stability": 0.9,
        "weight_shift_offset": 6.0,
    }


def test_nan_side_shoulder_does_not_raise():
    """A NaN per-side shoulder feature must not raise (previously KeyError)."""
    feats = _base_features()
    feats["left_shoulder_elev"] = math.nan
    assert risk_from_features(feats) in {"LOW", "MEDIUM", "HIGH"}


def test_nan_side_shoulder_maps_to_unknown_value():
    """NaN is scored identically to the explicit unknown fallback (30.0)."""
    feats_nan = _base_features()
    feats_nan["left_shoulder_elev"] = math.nan
    feats_unknown = _base_features()
    feats_unknown["left_shoulder_elev"] = 30.0  # _UNKNOWN_VALUES["left_shoulder_elev"]
    assert risk_from_features(feats_nan) == risk_from_features(feats_unknown)


def test_unavailable_side_shoulder_does_not_raise():
    """An explicitly unavailable per-side shoulder feature must not raise."""
    feats = _base_features()
    feats["left_shoulder_elev"] = math.nan
    feats["right_shoulder_elev"] = math.nan
    risk = risk_from_features(feats, unavailable_features=["left_shoulder_elev", "right_shoulder_elev"])
    assert risk in {"LOW", "MEDIUM", "HIGH"}


def test_unexpected_feature_name_in_unavailable_does_not_raise():
    """Any future feature name listed as unavailable must fail closed, not raise."""
    feats = _base_features()
    risk = risk_from_features(feats, unavailable_features=["future_feature_x"])
    assert risk in {"LOW", "MEDIUM", "HIGH"}


def test_normal_features_still_low():
    """A clean posture frame still scores LOW (no behavior change)."""
    assert risk_from_features(_base_features()) == "LOW"


def test_impossible_trunk_flexion_does_not_score_high():
    """A corrupt pose (trunk flexion 176 deg) must not fire HIGH.

    Regression: recorded sessions with landmarks snapped to furniture produced
    physically impossible angles (trunk 176 deg, neck 130 deg) that scored
    HIGH on every frame, making "all sessions HIGH". An impossible pose is not
    an assessment - the value falls back to the unknown level which sits at
    the MEDIUM cutoff and contributes nothing.
    """
    feats = _base_features()
    feats["trunk_flexion"] = 176.0
    feats["neck_flexion"] = 0.0
    assert risk_from_features(feats) == "LOW"


def test_impossible_neck_flexion_does_not_score_high():
    feats = _base_features()
    feats["neck_flexion"] = 130.0
    feats["trunk_flexion"] = 12.0
    assert risk_from_features(feats) == "LOW"


def test_implausible_value_scores_like_unknown():
    """An impossible value must behave identically to the unknown fallback."""
    feats_imp = _base_features()
    feats_imp["trunk_flexion"] = 176.0
    feats_unk = _base_features()
    feats_unk["trunk_flexion"] = 20.0  # _UNKNOWN_VALUES["trunk_flexion"]
    assert risk_from_features(feats_imp) == risk_from_features(feats_unk)
