"""Runtime Integration — Context Intelligence Engine in Live Pipeline.

Verifies: pipeline integration, ContextSnapshot creation, frame numbering,
engine reset, performance impact, API contract unchanged.

Run: python scripts/test_runtime_integration.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from backend.context.engine import ContextIntelligenceEngine, ContextSnapshot
from backend.core.types import LiveState, ProcessedFrame
from backend.services.features import FEATURE_COLUMNS, risk_breakdown
from backend.services.issue_detection import detect_posture_issues
from backend.services.task_recognition import TaskRecognition


# ── Test Helpers ───────────────────────────────────────────────────

def _healthy() -> dict[str, float]:
    return {
        "neck_flexion": 5.0,
        "trunk_flexion": 8.0,
        "left_shoulder_elev": 12.0,
        "right_shoulder_elev": 14.0,
        "shoulder_symmetry": 2.0,
        "alignment_deviation": 3.0,
        "knee_angle": 165.0,
    }


def _poor() -> dict[str, float]:
    return {
        "neck_flexion": 35.0,
        "trunk_flexion": 45.0,
        "left_shoulder_elev": 55.0,
        "right_shoulder_elev": 50.0,
        "shoulder_symmetry": 14.0,
        "alignment_deviation": 18.0,
        "knee_angle": 120.0,
    }


def _simulate_frame(features, session_duration, delta, task_name="Assembly Work"):
    """Simulate what the live pipeline does: features -> issues -> context engine."""
    issues = detect_posture_issues(features)
    engine = ContextIntelligenceEngine(session_id="test-runtime")
    snapshot = engine.evaluate(
        features=features,
        issues=issues,
        task_name=task_name,
        task_confidence=85.0,
        session_duration_seconds=session_duration,
        camera_confidence=92.0,
        delta_seconds=delta,
    )
    return snapshot, issues


# ── Pipeline Integration ──────────────────────────────────────────

def test_context_snapshot_in_live_state():
    """LiveState.context_snapshot should accept ContextSnapshot."""
    state = LiveState()
    assert state.context_snapshot is None

    snap = ContextSnapshot(session_id="test", frame_number=1, final_risk=45.0)
    state.context_snapshot = snap
    assert state.context_snapshot is not None
    assert state.context_snapshot.session_id == "test"
    assert state.context_snapshot.frame_number == 1
    assert state.context_snapshot.final_risk == 45.0
    print("  PASS: LiveState accepts ContextSnapshot")


def test_context_snapshot_optional_default():
    """LiveState should have context_snapshot=None by default."""
    state = LiveState()
    assert state.context_snapshot is None
    # All existing fields should still work
    state.risk_level = "HIGH"
    state.features = _healthy()
    state.person_detected = True
    assert state.risk_level == "HIGH"
    assert state.features == _healthy()
    assert state.person_detected is True
    print("  PASS: context_snapshot is optional (None default)")


def test_live_state_backward_compatible():
    """LiveState should remain backward compatible — no fields removed."""
    state = LiveState(
        session_active=True,
        session_id="SESH-TEST",
        features=_healthy(),
        risk_level="LOW",
        risk_score=10.0,
        confidence=95.0,
        person_detected=True,
        task_name="Assembly Work",
        task_confidence=85.0,
    )
    assert state.session_active is True
    assert state.session_id == "SESH-TEST"
    assert state.features == _healthy()
    assert state.risk_level == "LOW"
    assert state.context_snapshot is None
    print("  PASS: LiveState backward compatible")


# ── ContextSnapshot Creation Per Frame ────────────────────────────

def test_snapshot_created_every_frame():
    """Each simulated frame should produce a valid ContextSnapshot."""
    engine = ContextIntelligenceEngine(session_id="per-frame-test")
    snapshots = []

    for i in range(10):
        features = _poor() if i % 2 == 0 else _healthy()
        issues = detect_posture_issues(features)
        snap = engine.evaluate(
            features=features,
            issues=issues,
            task_name="Assembly Work",
            task_confidence=85.0,
            session_duration_seconds=float(i * 30),
            camera_confidence=92.0,
            delta_seconds=0.033,
        )
        snapshots.append(snap)

    for i, snap in enumerate(snapshots):
        assert isinstance(snap, ContextSnapshot), f"Frame {i}: not a ContextSnapshot"
        assert snap.frame_number == i + 1
        assert snap.session_id == "per-frame-test"
        assert 0.0 <= snap.final_risk <= 100.0
        assert snap.risk_level in ("LOW", "MEDIUM", "HIGH")
        assert snap.safety_state in ("SAFE", "OBSERVE", "WARNING", "CRITICAL", "RECOVERY")
        assert snap.captured_at != ""
    print(f"  PASS: {len(snapshots)} snapshots created with correct fields")


def test_snapshot_frame_numbering_increments():
    """Frame numbers should increment sequentially across evaluate calls."""
    engine = ContextIntelligenceEngine(session_id="frame-incr-test")
    numbers = []
    for i in range(20):
        snap = engine.evaluate(
            features=_healthy(), issues=[],
            task_name="Neutral Standing", task_confidence=95.0,
            session_duration_seconds=float(i), camera_confidence=95.0,
            delta_seconds=0.033,
        )
        numbers.append(snap.frame_number)

    expected = list(range(1, 21))
    assert numbers == expected, f"Expected {expected}, got {numbers}"
    print("  PASS: frame numbering increments correctly")


def test_snapshot_frame_numbering_resets():
    """Frame counter should reset on engine.reset()."""
    engine = ContextIntelligenceEngine(session_id="frame-reset-test")
    for _ in range(15):
        engine.evaluate(
            features=_healthy(), issues=[],
            task_name="Neutral Standing", task_confidence=95.0,
            session_duration_seconds=10.0, camera_confidence=95.0,
            delta_seconds=0.033,
        )
    assert engine.frame_counter == 15

    engine.reset()
    assert engine.frame_counter == 0

    snap = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert snap.frame_number == 1
    print("  PASS: frame numbering resets on engine.reset()")


# ── Session Lifecycle ─────────────────────────────────────────────

def test_session_id_propagates_to_snapshot():
    """Engine session_id should appear in every snapshot."""
    engine = ContextIntelligenceEngine(session_id="SESH-2026-001", worker_id="W-42")
    for _ in range(5):
        snap = engine.evaluate(
            features=_healthy(), issues=[],
            task_name="Neutral Standing", task_confidence=95.0,
            session_duration_seconds=10.0, camera_confidence=95.0,
            delta_seconds=0.033,
        )
        assert snap.session_id == "SESH-2026-001"
        assert snap.worker_id == "W-42"
    print("  PASS: session_id and worker_id propagate to snapshots")


def test_engine_reset_full_cycle():
    """Full session lifecycle: start -> process frames -> reset -> new session."""
    engine = ContextIntelligenceEngine(session_id="session-1")

    # Session 1: 50 frames
    for i in range(50):
        engine.evaluate(
            features=_poor(), issues=[],
            task_name="Assembly Work", task_confidence=85.0,
            session_duration_seconds=float(i * 30),
            camera_confidence=90.0, delta_seconds=1.0,
        )
    assert engine.frame_counter == 50
    assert engine.fatigue.state.score > 0

    # Reset for session 2
    engine.reset()
    assert engine.frame_counter == 0
    assert engine.fatigue.state.score == 0.0

    # Session 2: 10 frames with healthy posture
    for i in range(10):
        snap = engine.evaluate(
            features=_healthy(), issues=[],
            task_name="Neutral Standing", task_confidence=95.0,
            session_duration_seconds=float(i),
            camera_confidence=95.0, delta_seconds=0.033,
        )
    assert engine.frame_counter == 10
    assert snap.risk_level == "LOW"
    print("  PASS: full session lifecycle (start -> process -> reset -> new)")


# ── Feature-to-Snapshot Flow ──────────────────────────────────────

def test_poor_features_high_risk_snapshot():
    """Poor features should produce high-risk snapshot."""
    issues = detect_posture_issues(_poor())
    engine = ContextIntelligenceEngine()
    snap = engine.evaluate(
        features=_poor(), issues=issues,
        task_name="Assembly Work", task_confidence=85.0,
        session_duration_seconds=600.0, camera_confidence=92.0,
        delta_seconds=0.033,
    )
    assert snap.base_risk >= 70.0, f"Expected high base_risk, got {snap.base_risk}"
    assert snap.risk_level == "HIGH"
    assert len(snap.active_rules) > 0
    assert len(snap.reason) > 0
    print(f"  PASS: poor features -> base_risk={snap.base_risk:.0f}, level={snap.risk_level}")


def test_healthy_features_low_risk_snapshot():
    """Healthy features should produce low-risk snapshot."""
    engine = ContextIntelligenceEngine()
    snap = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert snap.base_risk == 0.0, f"Expected 0 base_risk, got {snap.base_risk}"
    assert snap.final_risk < 5.0, f"Expected low final_risk, got {snap.final_risk}"
    assert snap.risk_level == "LOW"
    assert snap.safety_state == "SAFE"
    print(f"  PASS: healthy features -> base_risk=0, final={snap.final_risk:.1f}, level=LOW")


# ── Performance ───────────────────────────────────────────────────

def test_context_engine_overhead():
    """Context engine should add < 5ms overhead per frame."""
    engine = ContextIntelligenceEngine(session_id="perf-test")
    features = _poor()
    issues = detect_posture_issues(features)

    # Warmup
    for _ in range(5):
        engine.evaluate(
            features=features, issues=issues,
            task_name="Assembly Work", task_confidence=85.0,
            session_duration_seconds=60.0, camera_confidence=90.0,
            delta_seconds=0.033,
        )

    # Measure
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        engine.evaluate(
            features=features, issues=issues,
            task_name="Assembly Work", task_confidence=85.0,
            session_duration_seconds=60.0, camera_confidence=90.0,
            delta_seconds=0.033,
        )
    elapsed_ms = (time.perf_counter() - start) / iterations * 1000

    assert elapsed_ms < 5.0, f"Context engine too slow: {elapsed_ms:.2f}ms per frame"
    print(f"  PASS: context engine overhead = {elapsed_ms:.2f}ms/frame (limit: 5ms)")


def test_full_pipeline_simulated_performance():
    """Full simulated pipeline (features -> issues -> task -> context) < 10ms."""
    tr = TaskRecognition()
    features = _poor()
    issues = detect_posture_issues(features)
    engine = ContextIntelligenceEngine(session_id="pipeline-perf")

    # Warmup
    for _ in range(3):
        engine.evaluate(
            features=features, issues=issues,
            task_name="Assembly Work", task_confidence=85.0,
            session_duration_seconds=60.0, camera_confidence=90.0,
            delta_seconds=0.033,
        )

    iterations = 50
    start = time.perf_counter()
    for _ in range(iterations):
        new_issues = detect_posture_issues(features)
        snap = engine.evaluate(
            features=features, issues=new_issues,
            task_name="Assembly Work", task_confidence=85.0,
            session_duration_seconds=60.0, camera_confidence=90.0,
            delta_seconds=0.033,
        )
    elapsed_ms = (time.perf_counter() - start) / iterations * 1000

    assert elapsed_ms < 10.0, f"Pipeline too slow: {elapsed_ms:.2f}ms per frame"
    assert isinstance(snap, ContextSnapshot)
    print(f"  PASS: full simulated pipeline = {elapsed_ms:.2f}ms/frame (limit: 10ms)")


# ── API Contract: No Changes ─────────────────────────────────────

def test_api_dashboard_schema_unchanged():
    """DashboardResponse schema should not include context_snapshot."""
    from app.schemas.api import DashboardResponse

    # Build a minimal valid DashboardResponse
    dr = DashboardResponse(
        session={"id": "test", "workerName": "Test", "workerId": "W-1",
                 "startTime": "", "currentTime": "", "duration": 0,
                 "framesAnalyzed": 0, "cameraStatus": "disconnected"},
        liveStatus={"riskLevel": "low", "riskScore": 0, "confidence": 0,
                    "currentTask": "Unknown", "workerStatus": "idle"},
        ergonomicFeatures=[],
        issues=[],
        recommendations={"worker": "", "supervisor": ""},
        sessionAnalytics={"sessionDuration": "0m 0s", "framesAnalyzed": 0,
                          "highestRisk": "LOW", "mostFrequentIssue": "None",
                          "averageNeck": 0, "averageTrunk": 0, "averageKnee": 0},
        riskHistory=[],
        trendAnalysis={"trend": "stable", "averageRisk": 0, "sessionsAnalyzed": 0,
                       "improving": 0, "stable": 1, "deteriorating": 0},
    )
    d = dr.model_dump()
    assert "context_snapshot" not in d, "context_snapshot should NOT be in DashboardResponse"
    assert "contextSnapshot" not in d, "contextSnapshot should NOT be in DashboardResponse"
    print("  PASS: DashboardResponse schema unchanged (no context fields)")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  RUNTIME INTEGRATION — TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        # Pipeline Integration
        test_context_snapshot_in_live_state,
        test_context_snapshot_optional_default,
        test_live_state_backward_compatible,
        # ContextSnapshot Creation Per Frame
        test_snapshot_created_every_frame,
        test_snapshot_frame_numbering_increments,
        test_snapshot_frame_numbering_resets,
        # Session Lifecycle
        test_session_id_propagates_to_snapshot,
        test_engine_reset_full_cycle,
        # Feature-to-Snapshot Flow
        test_poor_features_high_risk_snapshot,
        test_healthy_features_low_risk_snapshot,
        # Performance
        test_context_engine_overhead,
        test_full_pipeline_simulated_performance,
        # API Contract
        test_api_dashboard_schema_unchanged,
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
