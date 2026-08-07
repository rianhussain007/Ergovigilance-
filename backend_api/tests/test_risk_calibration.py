"""Unit tests for backend/services/risk_calibration.py (advisory overlay)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.services import risk_calibration

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "risk_calibration_model.pkl"


@pytest.fixture(autouse=True)
def _reset():
    risk_calibration.reset_cache()
    yield
    risk_calibration.reset_cache()


def test_predict_returns_band_when_model_present():
    if not MODEL_PATH.exists():
        pytest.skip("risk_calibration_model.pkl not present")
    feats = {
        "neck_flexion": 5.0, "trunk_flexion": 5.0,
        "left_shoulder_elev": 10.0, "right_shoulder_elev": 10.0,
        "shoulder_symmetry": 2.0, "alignment_deviation": 3.0,
        "knee_angle": 170.0, "elbow_flexion_angle": 170.0,
        "upper_arm_angle_from_vertical": 5.0,
        "forward_head_posture": 4.0, "head_tilt_angle": 3.0,
        "wrist_deviation_angle": 0.0, "stance_stability": 0.8,
        "weight_shift_offset": 4.0, "hand_reach_ratio": 1.0,
        "finger_spread_ratio": 0.4, "stance_width_ratio": 0.9,
    }
    result = risk_calibration.predict_risk_band(feats)
    assert result is not None
    assert result["band"] in {"LOW", "MEDIUM", "HIGH"}
    assert 0.0 <= result["confidence"] <= 1.0


def test_missing_model_returns_none():
    os.environ["ERGOVIGILANCE_RISK_MODEL"] = "C:/nonexistent/risk_model.pkl"
    risk_calibration.reset_cache()
    try:
        result = risk_calibration.predict_risk_band({"neck_flexion": 5.0})
    finally:
        os.environ.pop("ERGOVIGILANCE_RISK_MODEL", None)
        risk_calibration.reset_cache()
    assert result is None


def test_short_features_never_raise():
    if not MODEL_PATH.exists():
        pytest.skip("risk_calibration_model.pkl not present")
    result = risk_calibration.predict_risk_band({"neck_flexion": 5.0})
    assert result is None or result["band"] in {"LOW", "MEDIUM", "HIGH"}
