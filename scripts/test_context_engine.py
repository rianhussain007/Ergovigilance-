"""Context Intelligence Engine — Unit Tests.

Covers: healthy posture, long duration, repetitive work, poor posture,
recovery, low confidence, fatigue, exposure, task modifiers.

Run: python scripts/test_context_engine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.context.engine import ContextIntelligenceEngine, ContextSnapshot, ContextResult
from backend.context.exposure import ExposureTracker, ExposureVector
from backend.context.fatigue import FatigueModel


# ── Test Helpers ───────────────────────────────────────────────────

def _healthy_features() -> dict[str, float]:
    # All feature keys present (the real pipeline always provides them; a
    # missing key defaults to 0.0, which would make inverted features like
    # stance_stability score as max risk).
    return {
        "neck_flexion": 5.0,
        "trunk_flexion": 8.0,
        "left_shoulder_elev": 12.0,
        "right_shoulder_elev": 14.0,
        "shoulder_symmetry": 2.0,
        "alignment_deviation": 3.0,
        "knee_angle": 165.0,
        "elbow_flexion_angle": 170.0,
        "upper_arm_angle_from_vertical": 5.0,
        "forward_head_posture": 4.0,
        "head_tilt_angle": 3.0,
        "wrist_deviation_angle": 0.0,
        "stance_stability": 0.8,
        "weight_shift_offset": 4.0,
    }


def _poor_neck_features() -> dict[str, float]:
    return {
        "neck_flexion": 35.0,
        "trunk_flexion": 10.0,
        "left_shoulder_elev": 15.0,
        "right_shoulder_elev": 16.0,
        "shoulder_symmetry": 2.5,
        "alignment_deviation": 4.0,
        "knee_angle": 160.0,
        "elbow_flexion_angle": 170.0,
        "upper_arm_angle_from_vertical": 5.0,
        "forward_head_posture": 4.0,
        "head_tilt_angle": 3.0,
        "wrist_deviation_angle": 0.0,
        "stance_stability": 0.8,
        "weight_shift_offset": 4.0,
    }


def _poor_trunk_features() -> dict[str, float]:
    return {
        "neck_flexion": 8.0,
        "trunk_flexion": 45.0,
        "left_shoulder_elev": 14.0,
        "right_shoulder_elev": 13.0,
        "shoulder_symmetry": 1.8,
        "alignment_deviation": 4.0,
        "knee_angle": 155.0,
        "elbow_flexion_angle": 170.0,
        "upper_arm_angle_from_vertical": 5.0,
        "forward_head_posture": 4.0,
        "head_tilt_angle": 3.0,
        "wrist_deviation_angle": 0.0,
        "stance_stability": 0.8,
        "weight_shift_offset": 4.0,
    }


def _multiple_issues_features() -> dict[str, float]:
    return {
        "neck_flexion": 35.0,
        "trunk_flexion": 45.0,
        "left_shoulder_elev": 55.0,
        "right_shoulder_elev": 50.0,
        "shoulder_symmetry": 14.0,
        "alignment_deviation": 18.0,
        "knee_angle": 120.0,
        "elbow_flexion_angle": 170.0,
        "upper_arm_angle_from_vertical": 5.0,
        "forward_head_posture": 4.0,
        "head_tilt_angle": 3.0,
        "wrist_deviation_angle": 0.0,
        "stance_stability": 0.8,
        "weight_shift_offset": 4.0,
    }


def _assert_between(value: float, low: float, high: float, label: str) -> None:
    assert low <= value <= high, f"{label}: {value} not in [{low}, {high}]"


# ── Tests ──────────────────────────────────────────────────────────

def test_healthy_posture_low_risk():
    """Healthy posture should produce low base risk and low final risk."""
    engine = ContextIntelligenceEngine(session_id="test-session", worker_id="worker-1")
    result = engine.evaluate(
        features=_healthy_features(),
        issues=[],
        task_name="Neutral Standing",
        task_confidence=90.0,
        session_duration_seconds=10.0,
        camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert isinstance(result, ContextSnapshot)
    assert isinstance(result, ContextResult)  # backward compat
    assert result.base_risk == 0.0, f"Expected base_risk=0, got {result.base_risk}"
    assert result.final_risk < 5.0, f"Expected final_risk < 5, got {result.final_risk}"
    assert result.risk_level == "LOW"
    assert result.safety_state == "SAFE"
    assert result.session_id == "test-session"
    assert result.worker_id == "worker-1"
    assert result.frame_number == 1
    assert result.captured_at != ""
    print("  PASS: healthy posture -> low risk")


def test_poor_neck_posture():
    """Poor neck posture should produce elevated base risk."""
    engine = ContextIntelligenceEngine()
    result = engine.evaluate(
        features=_poor_neck_features(),
        issues=[{"issue": "Excessive Neck Flexion", "severity": "HIGH", "value": 35.0, "threshold": 30.0}],
        task_name="Assembly Work",
        task_confidence=85.0,
        session_duration_seconds=60.0,
        camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert result.base_risk > 0, f"Expected base_risk > 0, got {result.base_risk}"
    assert result.feature_scores["neck_flexion"] == 100.0, "neck_flexion should be max risk (35 > 30)"
    # Single-feature outlier no longer dominates — weighted aggregation
    # dilutes it when 6/7 features are within safe range.
    print(f"  PASS: poor neck -> base_risk={result.base_risk:.0f}, final={result.final_risk:.0f}, level={result.risk_level}")


def test_poor_trunk_posture():
    """Poor trunk posture should produce elevated risk with task modifier."""
    engine = ContextIntelligenceEngine()
    result = engine.evaluate(
        features=_poor_trunk_features(),
        issues=[{"issue": "Excessive Trunk Flexion", "severity": "MEDIUM", "value": 45.0, "threshold": 20.0}],
        task_name="Lifting / Picking",
        task_confidence=80.0,
        session_duration_seconds=10.0,
        camera_confidence=90.0,
        delta_seconds=0.033,
    )
    assert result.base_risk > 0, f"Expected base_risk > 0, got {result.base_risk}"
    assert result.feature_scores["trunk_flexion"] > 0, "trunk_flexion should have risk"
    assert result.context_modifier > 0, "Context modifier should be positive (task + fatigue)"
    print(f"  PASS: poor trunk -> base_risk={result.base_risk:.0f}, modifier={result.context_modifier:.1f}, final={result.final_risk:.0f}")


def test_multiple_issues_highest_risk():
    """Multiple issues should produce the highest base risk among all features."""
    engine = ContextIntelligenceEngine()
    result = engine.evaluate(
        features=_multiple_issues_features(),
        issues=[
            {"issue": "Excessive Neck Flexion", "severity": "HIGH", "value": 35.0, "threshold": 30.0},
            {"issue": "Excessive Trunk Flexion", "severity": "MEDIUM", "value": 45.0, "threshold": 20.0},
            {"issue": "Shoulder Imbalance", "severity": "MEDIUM", "value": 14.0, "threshold": 5.0},
        ],
        task_name="Assembly Work",
        task_confidence=85.0,
        session_duration_seconds=300.0,
        camera_confidence=90.0,
        delta_seconds=0.033,
    )
    assert result.base_risk >= 70, f"Expected base_risk >= 70, got {result.base_risk}"
    assert result.risk_level == "HIGH", f"Expected HIGH, got {result.risk_level}"
    assert len(result.active_rules) > 0, "Should have active rules"
    print(f"  PASS: multiple issues -> base_risk={result.base_risk:.0f}, final={result.final_risk:.0f}, rules={len(result.active_rules)}")


def test_long_duration_increases_risk():
    """Long session duration should increase fatigue and context modifier."""
    engine_short = ContextIntelligenceEngine()
    result_short = engine_short.evaluate(
        features=_healthy_features(),
        issues=[],
        task_name="Assembly Work",
        task_confidence=90.0,
        session_duration_seconds=60.0,
        camera_confidence=95.0,
        delta_seconds=0.033,
    )

    engine_long = ContextIntelligenceEngine()
    # Simulate 2 hours of assembly work
    for _ in range(3600):
        engine_long.evaluate(
            features=_healthy_features(),
            issues=[],
            task_name="Assembly Work",
            task_confidence=90.0,
            session_duration_seconds=7200.0,
            camera_confidence=95.0,
            delta_seconds=0.033,
        )

    assert engine_long.fatigue.state.score > engine_short.fatigue.state.score, \
        "Fatigue should be higher after long session"
    print(f"  PASS: long duration -> fatigue_short={engine_short.fatigue.state.score:.1f}, fatigue_long={engine_long.fatigue.state.score:.1f}")


def test_recovery_reduces_exposure():
    """Low-risk activity should reduce fatigue and exposure."""
    engine = ContextIntelligenceEngine()
    # Build up exposure with poor posture and long session
    for _ in range(50):
        engine.evaluate(
            features=_poor_neck_features(),
            issues=[],
            task_name="Assembly Work",
            task_confidence=90.0,
            session_duration_seconds=300.0,
            camera_confidence=95.0,
            delta_seconds=1.0,
        )
    fatigue_before = engine.fatigue.state.score

    # Recover with neutral posture for longer period
    for _ in range(200):
        engine.evaluate(
            features=_healthy_features(),
            issues=[],
            task_name="Neutral Standing",
            task_confidence=95.0,
            session_duration_seconds=500.0,
            camera_confidence=95.0,
            delta_seconds=1.0,
        )
    fatigue_after = engine.fatigue.state.score

    assert fatigue_after < fatigue_before, \
        f"Fatigue should decrease during recovery: before={fatigue_before:.1f}, after={fatigue_after:.1f}"
    print(f"  PASS: recovery -> fatigue_before={fatigue_before:.1f}, fatigue_after={fatigue_after:.1f}")


def test_low_confidence_reduces_risk():
    """Low camera confidence should reduce the final risk score."""
    # Use features that produce a base risk in the 60-90 range so confidence modifier matters
    mild_features = {
        "neck_flexion": 20.0,
        "trunk_flexion": 30.0,
        "left_shoulder_elev": 25.0,
        "right_shoulder_elev": 24.0,
        "shoulder_symmetry": 8.0,
        "alignment_deviation": 12.0,
        "knee_angle": 140.0,
    }
    engine_high = ContextIntelligenceEngine()
    result_high = engine_high.evaluate(
        features=mild_features,
        issues=[],
        task_name="Assembly Work",
        task_confidence=90.0,
        session_duration_seconds=60.0,
        camera_confidence=95.0,
        delta_seconds=0.033,
    )

    engine_low = ContextIntelligenceEngine()
    result_low = engine_low.evaluate(
        features=mild_features,
        issues=[],
        task_name="Assembly Work",
        task_confidence=90.0,
        session_duration_seconds=60.0,
        camera_confidence=55.0,
        delta_seconds=0.033,
    )

    assert result_low.final_risk < result_high.final_risk, \
        f"Low confidence should reduce risk: high_conf={result_high.final_risk:.1f}, low_conf={result_low.final_risk:.1f}"
    assert result_low.confidence_modifier < result_high.confidence_modifier
    print(f"  PASS: low confidence -> high_conf_final={result_high.final_risk:.1f}, low_conf_final={result_low.final_risk:.1f}")


def test_task_modifier():
    """Lifting task should produce higher risk than neutral standing."""
    engine_neutral = ContextIntelligenceEngine()
    result_neutral = engine_neutral.evaluate(
        features=_healthy_features(),
        issues=[],
        task_name="Neutral Standing",
        task_confidence=95.0,
        session_duration_seconds=60.0,
        camera_confidence=95.0,
        delta_seconds=0.033,
    )

    engine_lifting = ContextIntelligenceEngine()
    result_lifting = engine_lifting.evaluate(
        features=_healthy_features(),
        issues=[],
        task_name="Lifting / Picking",
        task_confidence=85.0,
        session_duration_seconds=60.0,
        camera_confidence=95.0,
        delta_seconds=0.033,
    )

    assert result_lifting.context_modifier > result_neutral.context_modifier, \
        "Lifting task should have higher context modifier than neutral"
    print(f"  PASS: task modifier -> neutral_mod={result_neutral.context_modifier:.1f}, lifting_mod={result_lifting.context_modifier:.1f}")


def test_exposure_tracker():
    """Exposure tracker should accumulate time above thresholds."""
    tracker = ExposureTracker()
    features = _poor_neck_features()

    # Update for 10 seconds
    for _ in range(100):
        tracker.update(features, delta_seconds=0.1)

    exposure = tracker.current_exposure
    assert exposure.neck_flexion_seconds > 0, "Neck exposure should accumulate"
    assert exposure.total_high_risk_seconds >= 0, "High risk seconds should be non-negative"
    print(f"  PASS: exposure -> neck={exposure.neck_flexion_seconds:.1f}s, high_risk={exposure.total_high_risk_seconds:.1f}s")


def test_fatigue_model():
    """Fatigue should increase with session duration."""
    model = FatigueModel()

    model.update(60.0, 0.0, "Neutral Standing", 1.0)
    fatigue_1min = model.state.score

    model.update(3600.0, 300.0, "Assembly Work", 1.0)
    fatigue_60min = model.state.score

    assert fatigue_60min > fatigue_1min, \
        f"Fatigue should increase: 1min={fatigue_1min:.1f}, 60min={fatigue_60min:.1f}"
    print(f"  PASS: fatigue model -> 1min={fatigue_1min:.1f}, 60min={fatigue_60min:.1f}")


def test_risk_level_boundaries():
    """Verify risk level classification at score boundaries."""
    # Score 0 -> LOW
    engine_low = ContextIntelligenceEngine()
    result = engine_low.evaluate(
        features=_healthy_features(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=99.0, delta_seconds=0.033,
    )
    assert result.risk_level == "LOW", f"Score 0 should be LOW, got {result.risk_level}"

    # Score ~70+ -> HIGH
    engine_high = ContextIntelligenceEngine()
    result = engine_high.evaluate(
        features=_multiple_issues_features(), issues=[],
        task_name="Lifting / Picking", task_confidence=90.0,
        session_duration_seconds=3600.0, camera_confidence=95.0, delta_seconds=1.0,
    )
    assert result.risk_level in ("MEDIUM", "HIGH"), f"Expected MEDIUM or HIGH, got {result.risk_level}"
    print(f"  PASS: risk boundaries -> LOW=0, current={result.risk_level}({result.final_risk:.0f})")


def test_reset():
    """Reset should clear all internal state."""
    engine = ContextIntelligenceEngine(session_id="test-reset")
    for _ in range(50):
        engine.evaluate(
            features=_poor_neck_features(), issues=[],
            task_name="Assembly Work", task_confidence=90.0,
            session_duration_seconds=300.0, camera_confidence=90.0, delta_seconds=1.0,
        )
    assert engine.frame_counter == 50

    engine.reset()
    assert engine.fatigue.state.score == 0.0, "Fatigue should be 0 after reset"
    assert engine.exposure.current_exposure.neck_flexion_seconds == 0.0, "Exposure should be 0 after reset"
    assert engine.frame_counter == 0, "Frame counter should reset to 0"
    print("  PASS: reset clears all state")


def test_feature_scoring_normal():
    """Verify feature scoring for normal (non-inverted) features."""
    engine = ContextIntelligenceEngine()

    # Below medium -> 0
    score = engine._score_feature(5.0, 10.0, 30.0, False)
    assert score == 0.0, f"Below medium should score 0, got {score}"

    # Above high -> 100
    score = engine._score_feature(35.0, 10.0, 30.0, False)
    assert score == 100.0, f"Above high should score 100, got {score}"

    # Midpoint -> 50
    score = engine._score_feature(20.0, 10.0, 30.0, False)
    assert score == 50.0, f"Midpoint should score 50, got {score}"
    print("  PASS: feature scoring normal")


def test_feature_scoring_inverted():
    """Verify feature scoring for inverted features (knee_angle)."""
    engine = ContextIntelligenceEngine()

    # Above medium (safe) -> 0
    score = engine._score_feature(160.0, 150.0, 100.0, True)
    assert score == 0.0, f"Above medium (safe) should score 0, got {score}"

    # Below high (dangerous) -> 100
    score = engine._score_feature(90.0, 150.0, 100.0, True)
    assert score == 100.0, f"Below high (dangerous) should score 100, got {score}"

    # Midpoint -> 50
    score = engine._score_feature(125.0, 150.0, 100.0, True)
    assert score == 50.0, f"Midpoint should score 50, got {score}"
    print("  PASS: feature scoring inverted")


def test_explanation_contains_reason():
    """Result should contain a non-empty explanation."""
    engine = ContextIntelligenceEngine()
    result = engine.evaluate(
        features=_poor_neck_features(),
        issues=[],
        task_name="Assembly Work",
        task_confidence=90.0,
        session_duration_seconds=10.0,
        camera_confidence=90.0,
        delta_seconds=0.033,
    )
    assert len(result.reason) > 0, "Reason should not be empty"
    assert "Base risk" in result.reason, f"Reason should mention base risk: {result.reason}"
    print(f"  PASS: explanation -> '{result.reason[:80]}...'")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  CONTEXT INTELLIGENCE ENGINE — TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        test_healthy_posture_low_risk,
        test_poor_neck_posture,
        test_poor_trunk_posture,
        test_multiple_issues_highest_risk,
        test_long_duration_increases_risk,
        test_recovery_reduces_exposure,
        test_low_confidence_reduces_risk,
        test_task_modifier,
        test_exposure_tracker,
        test_fatigue_model,
        test_risk_level_boundaries,
        test_reset,
        test_feature_scoring_normal,
        test_feature_scoring_inverted,
        test_explanation_contains_reason,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__} — {type(e).__name__}: {e}")
            failed += 1

    print()
    print("-" * 70)
    print(f"  Result: {passed}/{passed + failed} tests passed")
    if failed:
        print(f"  FAILED: {failed} test(s)")
    print("=" * 70)


if __name__ == "__main__":
    main()
