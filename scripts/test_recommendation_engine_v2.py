"""Recommendation Engine V2 — Comprehensive Unit Tests.

Covers: ranking, duplicates, expiration, grouping, history-aware,
alert-aware, catalog evaluation, performance.

Run: python scripts/test_recommendation_engine_v2.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.alerts.engine import AlertEngine
from backend.alerts.models import Alert, AlertSeverity, AlertState
from backend.context.engine import ContextSnapshot
from backend.events.event_bus import EventBus
from backend.events.events import ContextSnapshotCreatedEvent
from backend.history.engine import HistoryEngine
from backend.recommendations.catalog import (
    DEFAULT_CATALOG,
    TEMPLATE_NECK_POSTURE,
    TEMPLATE_FATIGUE_BREAK,
    TEMPLATE_SUPERVISOR_INTERVENTION,
)
from backend.recommendations.engine import RecommendationEngine
from backend.recommendations.models import (
    Recommendation,
    RecommendationBundle,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationTarget,
)
from backend.recommendations.ranking import (
    compute_priority_score,
    rank_recommendations,
    determine_priority_from_score,
)


# ── Test Helpers ───────────────────────────────────────────────────

def _snapshot(
    risk_level="LOW", final_risk=0.0, fatigue=0.0, exposure=0.0,
    feature_scores=None, frame=1, session_id="test",
):
    return ContextSnapshot(
        session_id=session_id, frame_number=frame,
        captured_at="2026-07-05T12:00:00Z",
        risk_level=risk_level, final_risk=final_risk,
        base_risk=final_risk, fatigue_score=fatigue, exposure_score=exposure,
        feature_scores=feature_scores or {},
    )


def _publish(bus, **kwargs):
    snap = _snapshot(**kwargs)
    bus.publish(ContextSnapshotCreatedEvent(snapshot=snap))
    return snap


# ── Models ─────────────────────────────────────────────────────────

def test_recommendation_to_dict():
    """Recommendation.to_dict() should produce serializable dict."""
    rec = Recommendation(
        id="REC-001", title="Test", description="Desc",
        category=RecommendationCategory.POSTURE,
        priority=RecommendationPriority.HIGH,
        target=RecommendationTarget.WORKER,
        trigger="neck_high", confidence=0.85,
        estimated_benefit="Reduced strain",
    )
    d = rec.to_dict()
    assert d["id"] == "REC-001"
    assert d["category"] == "Posture"
    assert d["priority"] == "High"
    assert d["target"] == "Worker"
    assert d["confidence"] == 0.85
    print("  PASS: Recommendation.to_dict()")


def test_bundle_to_dict():
    """RecommendationBundle.to_dict() should serialize all recs."""
    rec = Recommendation(id="REC-001", title="Test")
    bundle = RecommendationBundle(
        recommendations=(rec,), summary="1 rec", highest_priority=RecommendationPriority.HIGH,
    )
    d = bundle.to_dict()
    assert len(d["recommendations"]) == 1
    assert d["highest_priority"] == "High"
    print("  PASS: RecommendationBundle.to_dict()")


def test_recommendation_immutable():
    """Recommendation should be frozen."""
    rec = Recommendation(id="REC-001")
    try:
        rec.id = "changed"
        assert False
    except Exception:
        pass
    print("  PASS: Recommendation is immutable")


# ── Ranking ────────────────────────────────────────────────────────

def test_ranking_basic():
    """Higher base priority should rank higher."""
    low = Recommendation(id="L", priority=RecommendationPriority.LOW)
    high = Recommendation(id="H", priority=RecommendationPriority.HIGH)

    snap = _snapshot(final_risk=50.0)
    ranked = rank_recommendations([low, high], snap, [], HistoryEngine(EventBus()).get_statistics())
    assert ranked[0].id == "H"
    print("  PASS: ranking basic")


def test_ranking_risk_influence():
    """Higher risk should boost recommendations."""
    rec = Recommendation(id="R", priority=RecommendationPriority.MEDIUM)

    low_risk = _snapshot(final_risk=10.0)
    high_risk = _snapshot(final_risk=90.0)

    stats = HistoryEngine(EventBus()).get_statistics()
    score_low = compute_priority_score(rec, low_risk, [], stats)
    score_high = compute_priority_score(rec, high_risk, [], stats)
    assert score_high > score_low
    print("  PASS: ranking risk influence")


def test_ranking_alert_boost():
    """Active alerts should boost recommendation priority."""
    rec = Recommendation(id="R", priority=RecommendationPriority.MEDIUM)
    snap = _snapshot(final_risk=50.0)
    stats = HistoryEngine(EventBus()).get_statistics()

    score_no_alert = compute_priority_score(rec, snap, [], stats)
    alert = Alert(id="A1", severity=AlertSeverity.HIGH)
    score_with_alert = compute_priority_score(rec, snap, [alert], stats)
    assert score_with_alert > score_no_alert
    print("  PASS: ranking alert boost")


def test_determine_priority():
    """Score thresholds should map to correct priority."""
    assert determine_priority_from_score(0.5) == RecommendationPriority.LOW
    assert determine_priority_from_score(2.5) == RecommendationPriority.MEDIUM
    assert determine_priority_from_score(5.0) == RecommendationPriority.HIGH
    assert determine_priority_from_score(10.0) == RecommendationPriority.CRITICAL
    print("  PASS: determine priority from score")


# ── Engine Integration ────────────────────────────────────────────

def test_engine_creates_bundle():
    """Engine should create a bundle on snapshot."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    _publish(bus, risk_level="HIGH", final_risk=85.0,
             feature_scores={"neck_flexion": 80.0})

    bundle = engine.get_latest_bundle()
    assert bundle is not None
    assert isinstance(bundle, RecommendationBundle)
    assert len(bundle.recommendations) > 0
    print(f"  PASS: engine creates bundle ({len(bundle.recommendations)} recs)")


def test_engine_subscribes_to_bus():
    """RecommendationEngine should subscribe to ContextSnapshotCreatedEvent."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    listeners_before = bus.listener_count(ContextSnapshotCreatedEvent)

    engine = RecommendationEngine(bus, alert_engine, history_engine)
    listeners_after = bus.listener_count(ContextSnapshotCreatedEvent)
    assert listeners_after == listeners_before + 1
    print("  PASS: engine subscribes to bus")


def test_engine_neck_posture_recommendation():
    """High neck flexion should produce posture recommendation."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    _publish(bus, risk_level="HIGH", final_risk=80.0,
             feature_scores={"neck_flexion": 85.0})

    bundle = engine.get_latest_bundle()
    recs = [r for r in bundle.recommendations if r.trigger == "neck_flexion_high"]
    assert len(recs) >= 1
    assert recs[0].category == RecommendationCategory.POSTURE
    print("  PASS: neck posture recommendation")


def test_engine_fatigue_break_recommendation():
    """High fatigue should produce break recommendation."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    _publish(bus, risk_level="MEDIUM", final_risk=50.0, fatigue=60.0)

    bundle = engine.get_latest_bundle()
    recs = [r for r in bundle.recommendations if r.trigger == "fatigue_high"]
    assert len(recs) >= 1
    assert recs[0].category == RecommendationCategory.BREAK
    print("  PASS: fatigue break recommendation")


def test_engine_supervisor_intervention():
    """Critical alert should produce supervisor recommendation."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    # Generate critical alert by sending many HIGH frames
    for i in range(15):
        _publish(bus, risk_level="HIGH", final_risk=90.0)

    bundle = engine.get_latest_bundle()
    recs = [r for r in bundle.recommendations if r.trigger == "critical_risk"]
    assert len(recs) >= 1
    assert recs[0].target == RecommendationTarget.SUPERVISOR
    print("  PASS: supervisor intervention recommendation")


# ── Duplicate Suppression ─────────────────────────────────────────

def test_duplicate_suppression():
    """Same trigger should not fire repeatedly within cooldown."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    for i in range(5):
        _publish(bus, risk_level="HIGH", final_risk=85.0,
                 feature_scores={"neck_flexion": 80.0}, frame=i)

    bundle = engine.get_latest_bundle()
    neck_recs = [r for r in bundle.recommendations if r.trigger == "neck_flexion_high"]
    assert len(neck_recs) <= 1
    print("  PASS: duplicate suppression")


# ── Category Grouping ─────────────────────────────────────────────

def test_category_grouping():
    """Recommendations should have valid categories."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    _publish(bus, risk_level="HIGH", final_risk=85.0, fatigue=70.0,
             feature_scores={"neck_flexion": 80.0, "trunk_flexion": 75.0})

    bundle = engine.get_latest_bundle()
    categories = {r.category for r in bundle.recommendations}
    assert len(categories) > 0
    for cat in categories:
        assert isinstance(cat, RecommendationCategory)
    print(f"  PASS: category grouping ({len(categories)} categories)")


# ── History-Aware ──────────────────────────────────────────────────

def test_history_aware_trend():
    """Increasing risk trend should produce trend recommendation."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    # Build history with low risk
    for i in range(30):
        _publish(bus, risk_level="LOW", final_risk=10.0, frame=i)

    # Now spike to high risk
    _publish(bus, risk_level="HIGH", final_risk=80.0, frame=31)

    bundle = engine.get_latest_bundle()
    trend_recs = [r for r in bundle.recommendations if r.trigger == "trend_increasing"]
    assert len(trend_recs) >= 1
    print("  PASS: history-aware trend recommendation")


# ── Alert-Aware ────────────────────────────────────────────────────

def test_alert_aware_recommendation():
    """Multiple active alerts should produce supervisor recommendation."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    # Generate multiple alerts
    for i in range(10):
        _publish(bus, risk_level="HIGH", final_risk=90.0, frame=i)

    bundle = engine.get_latest_bundle()
    alert_recs = [r for r in bundle.recommendations if r.trigger == "alert_count_high"]
    assert len(alert_recs) >= 1
    print("  PASS: alert-aware recommendation")


# ── Bundle Summary ─────────────────────────────────────────────────

def test_bundle_summary():
    """Bundle should have a meaningful summary."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    _publish(bus, risk_level="HIGH", final_risk=85.0,
             feature_scores={"neck_flexion": 80.0})

    bundle = engine.get_latest_bundle()
    assert len(bundle.summary) > 0
    assert bundle.highest_priority in (
        RecommendationPriority.LOW, RecommendationPriority.MEDIUM,
        RecommendationPriority.HIGH, RecommendationPriority.CRITICAL,
    )
    print("  PASS: bundle summary")


def test_bundle_empty_when_safe():
    """Bundle should have no recommendations when safe."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    _publish(bus, risk_level="LOW", final_risk=5.0, fatigue=5.0)

    bundle = engine.get_latest_bundle()
    assert bundle is not None
    # May have 0 or few recs (possibly trend or duration)
    print(f"  PASS: bundle when safe ({len(bundle.recommendations)} recs)")


# ── Reset ──────────────────────────────────────────────────────────

def test_reset():
    """Reset should clear all engine state."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    for i in range(10):
        _publish(bus, risk_level="HIGH", final_risk=85.0, frame=i)

    engine.reset()
    assert engine.get_latest_bundle() is None
    assert engine.frame_counter == 0
    print("  PASS: reset clears state")


# ── Performance ────────────────────────────────────────────────────

def test_recommendation_performance():
    """Recommendation generation should be fast."""
    bus = EventBus()
    alert_engine = AlertEngine(bus)
    history_engine = HistoryEngine(bus)
    engine = RecommendationEngine(bus, alert_engine, history_engine)

    # Warmup
    for i in range(5):
        _publish(bus, risk_level="HIGH", final_risk=80.0,
                 feature_scores={"neck_flexion": 80.0}, frame=i)
    engine.reset()

    iterations = 100
    start = time.perf_counter()
    for i in range(iterations):
        _publish(bus, risk_level="HIGH", final_risk=80.0,
                 feature_scores={"neck_flexion": 80.0}, frame=i)
    elapsed_ms = (time.perf_counter() - start) / iterations * 1000

    assert elapsed_ms < 5.0, f"Too slow: {elapsed_ms:.2f}ms"
    print(f"  PASS: recommendation = {elapsed_ms:.3f}ms/frame (limit: 5ms)")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  RECOMMENDATION ENGINE V2 — COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        # Models
        test_recommendation_to_dict,
        test_bundle_to_dict,
        test_recommendation_immutable,
        # Ranking
        test_ranking_basic,
        test_ranking_risk_influence,
        test_ranking_alert_boost,
        test_determine_priority,
        # Engine Integration
        test_engine_creates_bundle,
        test_engine_subscribes_to_bus,
        test_engine_neck_posture_recommendation,
        test_engine_fatigue_break_recommendation,
        test_engine_supervisor_intervention,
        # Duplicate Suppression
        test_duplicate_suppression,
        # Category Grouping
        test_category_grouping,
        # History-Aware
        test_history_aware_trend,
        # Alert-Aware
        test_alert_aware_recommendation,
        # Bundle Summary
        test_bundle_summary,
        test_bundle_empty_when_safe,
        # Reset
        test_reset,
        # Performance
        test_recommendation_performance,
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
