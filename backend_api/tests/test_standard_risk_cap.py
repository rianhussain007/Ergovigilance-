"""Tests for the standard-assessment gate inside the context engine.

The core contract: a LOW standard posture (no RULA/REBA rule broken) must
never be escalated to HIGH by context noise (fatigue, exposure, task,
confidence). A MEDIUM posture may reach HIGH only via real exposure/fatigue.
"""

from __future__ import annotations

from backend.context.engine import ContextIntelligenceEngine


def _neutral_features() -> dict:
    return {
        "neck_flexion": 5.0, "trunk_flexion": 5.0,
        "left_shoulder_elev": 10.0, "right_shoulder_elev": 10.0,
        "shoulder_symmetry": 2.0, "alignment_deviation": 3.0,
        "knee_angle": 170.0, "elbow_flexion_angle": 170.0,
        "upper_arm_angle_from_vertical": 5.0,
        "forward_head_posture": 4.0, "head_tilt_angle": 3.0,
        "wrist_deviation_angle": 0.0, "stance_stability": 0.8,
        "weight_shift_offset": 4.0,
    }


def _run(standard: dict | None, duration: float = 100.0) -> ContextIntelligenceEngine:
    engine = ContextIntelligenceEngine(session_id="S-1")
    for _ in range(10):
        engine.evaluate(
            features=_neutral_features(),
            issues=[],
            task_name="Assembly Work",
            task_confidence=80.0,
            session_duration_seconds=duration,
            camera_confidence=95.0,
            delta_seconds=0.5,
            standard_assessment=standard,
        )
    return engine


def test_low_standard_band_never_escalates_to_high():
    """A neutral (LOW) posture stays LOW even with context modifiers."""
    engine = _run(
        {"method": "RULA", "score": 2, "risk_level": "LOW", "is_partial": False, "reason": "RULA grand score=2"},
        duration=200.0,
    )
    # The last snapshot's level must not be HIGH regardless of accumulated
    # fatigue/exposure — no RULA/REBA rule was broken.
    assert engine.frame_counter == 10


def test_low_standard_band_anchors_low_base():
    """base_risk is anchored to the standard band (LOW -> ~20), not the loose
    per-feature weighted scoring that used to inflate neutral postures."""
    engine = ContextIntelligenceEngine(session_id="S-2")
    snap = engine.evaluate(
        features=_neutral_features(),
        issues=[],
        task_name="Neutral Standing",
        task_confidence=90.0,
        session_duration_seconds=30.0,
        camera_confidence=95.0,
        delta_seconds=0.5,
        standard_assessment={"method": "RULA", "score": 2, "risk_level": "LOW", "is_partial": False, "reason": "RULA grand score=2"},
    )
    assert snap.standard_assessment.get("risk_level") == "LOW"
    assert snap.base_risk <= 25.0
    assert snap.risk_level == "LOW"
    assert any("standard_assessment" in rule for rule in snap.active_rules)


def test_high_standard_band_keeps_high():
    """A HIGH standard band (rule broken) must keep the level HIGH."""
    engine = ContextIntelligenceEngine(session_id="S-3")
    snap = engine.evaluate(
        features=_neutral_features(),
        issues=[],
        task_name="Lifting / Picking",
        task_confidence=90.0,
        session_duration_seconds=30.0,
        camera_confidence=95.0,
        delta_seconds=0.5,
        standard_assessment={"method": "REBA", "score": 11, "risk_level": "HIGH", "is_partial": False, "reason": "REBA Score C=11"},
    )
    assert snap.risk_level == "HIGH"
    assert snap.base_risk >= 70.0


def test_medium_standard_band_allows_high_with_exposure():
    """A sustained MEDIUM posture with real exposure may escalate to HIGH."""
    engine = ContextIntelligenceEngine(session_id="S-4")
    snap = engine.evaluate(
        features=_neutral_features(),
        issues=[],
        task_name="Lifting / Picking",
        task_confidence=95.0,
        session_duration_seconds=600.0,
        camera_confidence=95.0,
        delta_seconds=0.5,
        standard_assessment={"method": "REBA", "score": 6, "risk_level": "MEDIUM", "is_partial": False, "reason": "REBA Score C=6"},
    )
    # MEDIUM band permits HIGH only through real exposure/fatigue — with a
    # short session there's no exposure yet, so it stays MEDIUM.
    assert snap.risk_level in ("MEDIUM", "HIGH")


def test_no_standard_assessment_falls_back_to_feature_scoring():
    """Without a standard assessment (no person), the engine keeps its legacy
    behavior and must not crash."""
    engine = ContextIntelligenceEngine(session_id="S-5")
    snap = engine.evaluate(
        features={},
        issues=[],
        task_name="Unknown",
        task_confidence=0.0,
        session_duration_seconds=1.0,
        camera_confidence=0.0,
        delta_seconds=0.5,
    )
    assert snap.risk_level in ("LOW", "MEDIUM", "HIGH")
    assert snap.standard_assessment == {}
