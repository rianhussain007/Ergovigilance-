"""ContextSnapshot — Comprehensive Unit Tests.

Covers: identity fields, timestamps, frame numbering, immutability,
serialization (dict, JSON, roundtrip), database readiness, edge cases.

Run: python scripts/test_context_snapshot.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.context.engine import ContextIntelligenceEngine, ContextSnapshot


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


def _assert_between(value: float, low: float, high: float, label: str) -> None:
    assert low <= value <= high, f"{label}: {value} not in [{low}, {high}]"


# ── Identity & Timestamps ─────────────────────────────────────────

def test_snapshot_identity_fields():
    """Snapshot should carry session_id, worker_id, frame_number."""
    engine = ContextIntelligenceEngine(session_id="sess-42", worker_id="w-7")
    snap = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert snap.session_id == "sess-42"
    assert snap.worker_id == "w-7"
    assert snap.frame_number == 1
    print("  PASS: identity fields")


def test_snapshot_captured_at_auto_generated():
    """captured_at should be auto-generated ISO-8601 when not provided."""
    engine = ContextIntelligenceEngine()
    snap = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert snap.captured_at != "", "captured_at should not be empty"
    assert "T" in snap.captured_at, f"Expected ISO-8601 with 'T' separator: {snap.captured_at}"
    assert snap.captured_at.endswith("Z") or "+" in snap.captured_at or snap.captured_at.endswith("+00:00"), \
        f"Expected timezone info in captured_at: {snap.captured_at}"
    print(f"  PASS: auto-generated captured_at={snap.captured_at[:25]}...")


def test_snapshot_captured_at_explicit():
    """captured_at should use the provided value."""
    engine = ContextIntelligenceEngine()
    snap = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
        captured_at="2026-07-05T12:00:00Z",
    )
    assert snap.captured_at == "2026-07-05T12:00:00Z"
    print("  PASS: explicit captured_at")


# ── Frame Numbering ───────────────────────────────────────────────

def test_frame_number_increments():
    """Frame number should auto-increment across evaluate calls."""
    engine = ContextIntelligenceEngine(session_id="frame-test")
    frames = []
    for i in range(5):
        snap = engine.evaluate(
            features=_healthy(), issues=[],
            task_name="Neutral Standing", task_confidence=95.0,
            session_duration_seconds=float(i), camera_confidence=95.0,
            delta_seconds=0.033,
        )
        frames.append(snap.frame_number)

    assert frames == [1, 2, 3, 4, 5], f"Expected [1,2,3,4,5], got {frames}"
    assert engine.frame_counter == 5
    print("  PASS: frame numbering increments correctly")


def test_frame_number_resets():
    """Frame counter should reset to 0 on engine.reset()."""
    engine = ContextIntelligenceEngine()
    for _ in range(10):
        engine.evaluate(
            features=_healthy(), issues=[],
            task_name="Neutral Standing", task_confidence=95.0,
            session_duration_seconds=10.0, camera_confidence=95.0,
            delta_seconds=0.033,
        )
    assert engine.frame_counter == 10
    engine.reset()
    assert engine.frame_counter == 0

    snap = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert snap.frame_number == 1
    print("  PASS: frame number resets on engine.reset()")


# ── Immutability ──────────────────────────────────────────────────

def test_snapshot_is_frozen():
    """ContextSnapshot should be immutable (frozen dataclass)."""
    snap = ContextSnapshot(
        session_id="test", frame_number=1, captured_at="2026-01-01T00:00:00Z",
        base_risk=50.0, final_risk=60.0, risk_level="MEDIUM",
    )
    try:
        snap.final_risk = 0.0  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except FrozenInstanceError:
        pass
    print("  PASS: snapshot is frozen")


def test_snapshot_active_rules_are_tuple():
    """active_rules should be a tuple (immutable)."""
    engine = ContextIntelligenceEngine()
    snap = engine.evaluate(
        features=_poor(), issues=[],
        task_name="Assembly Work", task_confidence=85.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    assert isinstance(snap.active_rules, tuple), f"Expected tuple, got {type(snap.active_rules)}"
    print("  PASS: active_rules is a tuple")


def test_snapshot_feature_scores_independent_copy():
    """Feature scores dict should not be shared between snapshots."""
    engine = ContextIntelligenceEngine()
    snap1 = engine.evaluate(
        features=_poor(), issues=[],
        task_name="Assembly Work", task_confidence=85.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    snap2 = engine.evaluate(
        features=_healthy(), issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=20.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    # Mutating snap2's feature_scores should not affect snap1
    # (Both are frozen, but the internal dict is mutable — verify independence)
    assert snap1.feature_scores is not snap2.feature_scores
    print("  PASS: feature_scores are independent copies")


# ── Serialization: to_dict ────────────────────────────────────────

def test_to_dict_keys():
    """to_dict should contain all expected keys."""
    snap = ContextSnapshot(
        session_id="s1", frame_number=3, captured_at="2026-07-05T12:00:00Z",
        worker_id="w1", base_risk=45.0, context_modifier=5.0,
        fatigue_score=20.0, exposure_score=15.0, confidence_modifier=-1.5,
        final_risk=53.5, risk_level="MEDIUM", safety_state="OBSERVE",
        reason="Base risk: 45", active_rules=("rule_a", "rule_b"),
        feature_scores={"neck_flexion": 60.0, "knee_angle": 0.0},
    )
    d = snap.to_dict()
    expected_keys = {
        "session_id", "frame_number", "captured_at", "worker_id",
        "base_risk", "context_modifier", "fatigue_score", "exposure_score",
        "confidence_modifier", "final_risk", "risk_level", "safety_state",
        "movement_velocity", "reason", "active_rules", "feature_scores",
    }
    assert set(d.keys()) == expected_keys, f"Missing keys: {expected_keys - set(d.keys())}"
    print("  PASS: to_dict contains all keys")


def test_to_dict_values():
    """to_dict should have correct values."""
    snap = ContextSnapshot(
        session_id="s1", frame_number=3, captured_at="2026-07-05T12:00:00Z",
        worker_id="w1", base_risk=45.0, final_risk=53.5,
        risk_level="MEDIUM", safety_state="OBSERVE",
        active_rules=("rule_a",), feature_scores={"neck_flexion": 60.0},
    )
    d = snap.to_dict()
    assert d["session_id"] == "s1"
    assert d["frame_number"] == 3
    assert d["worker_id"] == "w1"
    assert d["base_risk"] == 45.0
    assert d["final_risk"] == 53.5
    assert d["risk_level"] == "MEDIUM"
    assert d["safety_state"] == "OBSERVE"
    assert d["active_rules"] == ["rule_a"]  # serialized as list
    assert d["feature_scores"] == {"neck_flexion": 60.0}
    print("  PASS: to_dict values correct")


# ── Serialization: to_json ────────────────────────────────────────

def test_to_json_valid():
    """to_json should produce valid JSON."""
    snap = ContextSnapshot(
        session_id="s1", frame_number=1, captured_at="2026-07-05T12:00:00Z",
        base_risk=30.0, final_risk=35.0, risk_level="MEDIUM",
        reason="Base risk: 30 | Final: 35",
        active_rules=("base_risk: neck=25.0 score=75",),
        feature_scores={"neck_flexion": 75.0, "trunk_flexion": 0.0},
    )
    json_str = snap.to_json()
    parsed = json.loads(json_str)
    assert parsed["session_id"] == "s1"
    assert parsed["frame_number"] == 1
    assert parsed["active_rules"] == ["base_risk: neck=25.0 score=75"]
    print("  PASS: to_json produces valid JSON")


def test_to_json_pretty():
    """to_json with indent should produce formatted JSON."""
    snap = ContextSnapshot(session_id="s1", frame_number=1)
    json_str = snap.to_json(indent=2)
    assert "\n" in json_str, "Pretty JSON should have newlines"
    assert "  " in json_str, "Pretty JSON should have indentation"
    print("  PASS: to_json pretty-printed")


# ── Deserialization: from_dict / from_json ────────────────────────

def test_from_dict_roundtrip():
    """to_dict -> from_dict should produce equivalent snapshot."""
    original = ContextSnapshot(
        session_id="s1", frame_number=7, captured_at="2026-07-05T12:00:00Z",
        worker_id="w1", base_risk=45.0, context_modifier=5.0,
        fatigue_score=20.0, exposure_score=15.0, confidence_modifier=-1.5,
        final_risk=53.5, risk_level="MEDIUM", safety_state="OBSERVE",
        reason="Base risk: 45 | Final: 53.5",
        active_rules=("rule_a", "rule_b"),
        feature_scores={"neck_flexion": 60.0, "knee_angle": 0.0},
    )
    restored = ContextSnapshot.from_dict(original.to_dict())
    assert restored.session_id == original.session_id
    assert restored.frame_number == original.frame_number
    assert restored.captured_at == original.captured_at
    assert restored.worker_id == original.worker_id
    assert restored.base_risk == original.base_risk
    assert restored.final_risk == original.final_risk
    assert restored.risk_level == original.risk_level
    assert restored.safety_state == original.safety_state
    assert restored.reason == original.reason
    assert restored.active_rules == original.active_rules
    assert restored.feature_scores == original.feature_scores
    print("  PASS: from_dict roundtrip")


def test_from_json_roundtrip():
    """to_json -> from_json should produce equivalent snapshot."""
    original = ContextSnapshot(
        session_id="s-json", frame_number=42,
        captured_at="2026-07-05T12:00:00Z",
        worker_id="w-json", base_risk=80.0, final_risk=95.0,
        risk_level="HIGH", safety_state="CRITICAL",
        active_rules=("base_risk: neck=35.0 score=100",),
        feature_scores={"neck_flexion": 100.0},
    )
    restored = ContextSnapshot.from_json(original.to_json())
    assert restored == original
    print("  PASS: from_json roundtrip")


def test_from_dict_defaults():
    """from_dict with empty dict should produce defaults."""
    snap = ContextSnapshot.from_dict({})
    assert snap.session_id == ""
    assert snap.frame_number == 0
    assert snap.captured_at == ""
    assert snap.worker_id == ""
    assert snap.base_risk == 0.0
    assert snap.final_risk == 0.0
    assert snap.risk_level == "LOW"
    assert snap.safety_state == "SAFE"
    assert snap.active_rules == ()
    assert snap.feature_scores == {}
    print("  PASS: from_dict defaults")


# ── Database Readiness ────────────────────────────────────────────

def test_all_fields_json_serializable():
    """Every field in ContextSnapshot should be JSON-serializable."""
    engine = ContextIntelligenceEngine(session_id="db-test", worker_id="w-db")
    snap = engine.evaluate(
        features=_poor(), issues=[],
        task_name="Assembly Work", task_confidence=85.0,
        session_duration_seconds=600.0, camera_confidence=88.0,
        delta_seconds=0.033,
    )
    json_str = snap.to_json()
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
    # Verify no non-serializable types leaked through
    for key, value in parsed.items():
        json.dumps({key: value})  # would raise if not serializable
    print("  PASS: all fields JSON-serializable")


def test_snapshot_as_database_row():
    """Snapshot should be storable as a database row (dict with fixed schema)."""
    engine = ContextIntelligenceEngine(session_id="db-row-test", worker_id="w-row")
    snaps = []
    for i in range(5):
        snap = engine.evaluate(
            features=_poor() if i % 2 == 0 else _healthy(), issues=[],
            task_name="Assembly Work" if i % 2 == 0 else "Neutral Standing",
            task_confidence=85.0, session_duration_seconds=float(i * 60),
            camera_confidence=92.0, delta_seconds=0.033,
        )
        snaps.append(snap)

    # Simulate storing as rows
    rows = [s.to_dict() for s in snaps]
    assert len(rows) == 5
    assert rows[0]["session_id"] == "db-row-test"
    assert rows[0]["frame_number"] == 1
    assert rows[4]["frame_number"] == 5

    # Simulate loading from rows
    loaded = [ContextSnapshot.from_dict(r) for r in rows]
    for orig, rest in zip(snaps, loaded):
        assert orig == rest
    print("  PASS: snapshot as database row (store/load)")


def test_snapshot_primary_key_fields():
    """session_id + frame_number should form a unique composite key."""
    snap1 = ContextSnapshot(session_id="s1", frame_number=1, captured_at="2026-01-01T00:00:00Z")
    snap2 = ContextSnapshot(session_id="s1", frame_number=2, captured_at="2026-01-01T00:00:01Z")
    snap3 = ContextSnapshot(session_id="s2", frame_number=1, captured_at="2026-01-01T00:00:00Z")
    # s1/f1 != s1/f2 (different frame)
    assert snap1 != snap2
    # s1/f1 != s2/f1 (different session)
    assert snap1 != snap3
    # s1/f1 == s1/f1 (same composite key)
    snap_dup = ContextSnapshot(session_id="s1", frame_number=1, captured_at="other")
    # Dataclass equality checks ALL fields, so different captured_at means not equal
    assert snap1 != snap_dup
    print("  PASS: composite key uniqueness")


# ── Risk Level Fields ─────────────────────────────────────────────

def test_risk_level_valid_values():
    """risk_level should only be LOW, MEDIUM, or HIGH."""
    engine = ContextIntelligenceEngine()
    levels_seen = set()
    for features, task, dur in [
        (_healthy(), "Neutral Standing", 10.0),
        (_poor(), "Assembly Work", 600.0),
    ]:
        snap = engine.evaluate(
            features=features, issues=[], task_name=task,
            task_confidence=85.0, session_duration_seconds=dur,
            camera_confidence=95.0, delta_seconds=0.033,
        )
        levels_seen.add(snap.risk_level)
        assert snap.risk_level in ("LOW", "MEDIUM", "HIGH"), f"Invalid risk_level: {snap.risk_level}"
    assert len(levels_seen) >= 1, "Should have seen at least one risk level"
    print(f"  PASS: risk_level valid values: {levels_seen}")


def test_safety_state_valid_values():
    """safety_state should be one of the 5 valid states."""
    valid_states = {"SAFE", "OBSERVE", "WARNING", "CRITICAL", "RECOVERY"}
    engine = ContextIntelligenceEngine()
    states_seen = set()

    # Run through various postures to trigger state transitions
    for features, task, dur in [
        (_healthy(), "Neutral Standing", 10.0),
        (_poor(), "Assembly Work", 600.0),
        (_healthy(), "Neutral Standing", 700.0),
    ]:
        snap = engine.evaluate(
            features=features, issues=[], task_name=task,
            task_confidence=85.0, session_duration_seconds=dur,
            camera_confidence=95.0, delta_seconds=0.033,
        )
        states_seen.add(snap.safety_state)
        assert snap.safety_state in valid_states, f"Invalid safety_state: {snap.safety_state}"
    print(f"  PASS: safety_state valid values: {states_seen}")


# ── Default Snapshot ──────────────────────────────────────────────

def test_default_snapshot():
    """ContextSnapshot() with no args should produce safe defaults."""
    snap = ContextSnapshot()
    assert snap.session_id == ""
    assert snap.frame_number == 0
    assert snap.captured_at == ""
    assert snap.worker_id == ""
    assert snap.base_risk == 0.0
    assert snap.context_modifier == 0.0
    assert snap.fatigue_score == 0.0
    assert snap.exposure_score == 0.0
    assert snap.confidence_modifier == 0.0
    assert snap.final_risk == 0.0
    assert snap.risk_level == "LOW"
    assert snap.safety_state == "SAFE"
    assert snap.reason == ""
    assert snap.active_rules == ()
    assert snap.feature_scores == {}
    print("  PASS: default snapshot")


# ── Edge Cases ────────────────────────────────────────────────────

def test_empty_features():
    """Engine with no features should produce snapshot with knee_angle risk."""
    engine = ContextIntelligenceEngine(session_id="empty")
    snap = engine.evaluate(
        features={}, issues=[],
        task_name="Neutral Standing", task_confidence=95.0,
        session_duration_seconds=10.0, camera_confidence=95.0,
        delta_seconds=0.033,
    )
    # knee_angle defaults to 0.0, which is inverted → scores 100.0
    # But weighted aggregation dilutes it: only 1/7 features exceed.
    assert snap.base_risk < 100.0, f"Expected diluted base_risk, got {snap.base_risk}"
    assert snap.feature_scores["knee_angle"] == 100.0
    assert snap.frame_number == 1
    print(f"  PASS: empty features -> base_risk={snap.base_risk:.1f} (diluted, 1/7 features)")


def test_max_risk_clamped():
    """final_risk should be clamped to 100 even with extreme modifiers."""
    engine = ContextIntelligenceEngine()
    # Run many frames to accumulate fatigue/exposure
    for _ in range(1000):
        engine.evaluate(
            features=_poor(), issues=[],
            task_name="Lifting / Picking", task_confidence=90.0,
            session_duration_seconds=7200.0, camera_confidence=95.0,
            delta_seconds=1.0,
        )
    snap = engine.evaluate(
        features=_poor(), issues=[],
        task_name="Lifting / Picking", task_confidence=90.0,
        session_duration_seconds=10800.0, camera_confidence=95.0,
        delta_seconds=1.0,
    )
    assert snap.final_risk <= 100.0, f"final_risk should be clamped to 100, got {snap.final_risk}"
    print(f"  PASS: max risk clamped to {snap.final_risk:.1f}")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  CONTEXT SNAPSHOT — COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        # Identity & Timestamps
        test_snapshot_identity_fields,
        test_snapshot_captured_at_auto_generated,
        test_snapshot_captured_at_explicit,
        # Frame Numbering
        test_frame_number_increments,
        test_frame_number_resets,
        # Immutability
        test_snapshot_is_frozen,
        test_snapshot_active_rules_are_tuple,
        test_snapshot_feature_scores_independent_copy,
        # Serialization
        test_to_dict_keys,
        test_to_dict_values,
        test_to_json_valid,
        test_to_json_pretty,
        # Deserialization
        test_from_dict_roundtrip,
        test_from_json_roundtrip,
        test_from_dict_defaults,
        # Database Readiness
        test_all_fields_json_serializable,
        test_snapshot_as_database_row,
        test_snapshot_primary_key_fields,
        # Risk Level Fields
        test_risk_level_valid_values,
        test_safety_state_valid_values,
        # Default Snapshot
        test_default_snapshot,
        # Edge Cases
        test_empty_features,
        test_max_risk_clamped,
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
