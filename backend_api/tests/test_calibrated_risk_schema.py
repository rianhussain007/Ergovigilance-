"""Regression tests for the calibrated-risk advisory fields on the context
snapshot schema and the model-vs-rules agreement semantics."""

import pytest

from backend.services.risk_calibration import band_agrees
from app.schemas.api import ContextSnapshotResponse


def _base_snapshot(**overrides) -> ContextSnapshotResponse:
    values = {
        "session_id": "SESH-TEST",
        "frame_number": 1,
        "captured_at": "2026-08-08T00:00:00Z",
        "worker_id": "W-1",
        "base_risk": 20.0,
        "context_modifier": 0.0,
        "fatigue_score": 10.0,
        "exposure_score": 10.0,
        "confidence_modifier": 90.0,
        "final_risk": 20.0,
        "risk_score_normalized": 0.2,
        "risk_level": "LOW",
        "safety_state": "SAFE",
        "reason": "test",
        "active_rules": [],
        "feature_scores": {},
    }
    values.update(overrides)
    return ContextSnapshotResponse(**values)


def test_schema_accepts_calibrated_fields():
    snap = _base_snapshot(
        calibrated_band="LOW",
        calibrated_confidence=0.9,
        calibrated_agrees=True,
    )
    assert snap.calibrated_band == "LOW"
    assert snap.calibrated_confidence == 0.9
    assert snap.calibrated_agrees is True


def test_schema_defaults_to_none():
    snap = _base_snapshot()
    assert snap.calibrated_band is None
    assert snap.calibrated_confidence is None
    assert snap.calibrated_agrees is None


def test_agreement_is_case_insensitive():
    """The helper compares the model band ('LOW') with the rule-based
    risk_level ('low') case-insensitively — this is what live.py uses."""
    assert band_agrees("LOW", "low") is True
    assert band_agrees("medium", "MEDIUM") is True


def test_agreement_false_on_mismatch():
    assert band_agrees("MEDIUM", "LOW") is False
    assert band_agrees("HIGH", "LOW") is False


def test_missing_risk_level_yields_none_agreement():
    assert band_agrees("LOW", None) is None
    assert band_agrees(None, "LOW") is None
    assert band_agrees(None, None) is None
    assert band_agrees("", "LOW") is None
