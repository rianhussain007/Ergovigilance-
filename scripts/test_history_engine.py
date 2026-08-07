"""Risk History Engine — Comprehensive Unit Tests.

Covers: snapshot ordering, pruning, rolling window, statistics,
memory limits, performance, EventBus integration.

Run: python scripts/test_history_engine.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.context.engine import ContextSnapshot
from backend.events.event_bus import EventBus
from backend.events.events import ContextSnapshotCreatedEvent
from backend.history.engine import HistoryEngine
from backend.history.models import HistoryStats, RiskDistribution
from backend.history.statistics import compute_statistics


# ── Test Helpers ───────────────────────────────────────────────────

def _snap(frame=1, risk_level="LOW", final_risk=0.0, fatigue=0.0, exposure=0.0, session_id="test"):
    """Create a ContextSnapshot for testing."""
    return ContextSnapshot(
        session_id=session_id,
        frame_number=frame,
        captured_at="2026-07-05T12:00:00Z",
        risk_level=risk_level,
        final_risk=final_risk,
        base_risk=final_risk,
        fatigue_score=fatigue,
        exposure_score=exposure,
    )


def _publish(bus, **kwargs):
    """Publish a ContextSnapshotCreatedEvent."""
    snap = _snap(**kwargs)
    bus.publish(ContextSnapshotCreatedEvent(snapshot=snap))
    return snap


# ── Snapshot Ordering ─────────────────────────────────────────────

def test_add_snapshot_ordering():
    """Snapshots should be stored in chronological order."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for i in range(10):
        engine.add_snapshot(_snap(frame=i))

    snapshots = engine.get_snapshots()
    assert len(snapshots) == 10
    for i, s in enumerate(snapshots):
        assert s.frame_number == i
    print("  PASS: snapshot ordering")


def test_latest_returns_most_recent():
    """latest() should return the most recently added snapshot."""
    engine = HistoryEngine(EventBus(), max_length=100)
    engine.add_snapshot(_snap(frame=1))
    engine.add_snapshot(_snap(frame=2))
    engine.add_snapshot(_snap(frame=3))

    latest = engine.latest()
    assert latest is not None
    assert latest.frame_number == 3
    print("  PASS: latest() returns most recent")


def test_latest_empty():
    """latest() should return None when history is empty."""
    engine = HistoryEngine(EventBus(), max_length=100)
    assert engine.latest() is None
    print("  PASS: latest() returns None when empty")


# ── Rolling Window ────────────────────────────────────────────────

def test_window_returns_last_n():
    """window(N) should return the last N snapshots."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for i in range(20):
        engine.add_snapshot(_snap(frame=i))

    window = engine.window(5)
    assert len(window) == 5
    assert [s.frame_number for s in window] == [15, 16, 17, 18, 19]
    print("  PASS: window() returns last N")


def test_window_larger_than_history():
    """window(N) with N > count should return all snapshots."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for i in range(5):
        engine.add_snapshot(_snap(frame=i))

    window = engine.window(10)
    assert len(window) == 5
    print("  PASS: window() larger than history")


def test_window_zero():
    """window(0) should return empty list."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for i in range(5):
        engine.add_snapshot(_snap(frame=i))

    assert engine.window(0) == []
    print("  PASS: window(0) returns empty")


def test_window_negative():
    """window(-1) should return empty list."""
    engine = HistoryEngine(EventBus(), max_length=100)
    engine.add_snapshot(_snap(frame=1))
    assert engine.window(-1) == []
    print("  PASS: window(-1) returns empty")


# ── Pruning ───────────────────────────────────────────────────────

def test_pruning_at_max_length():
    """Oldest snapshots should be pruned when max_length is reached."""
    engine = HistoryEngine(EventBus(), max_length=5)
    for i in range(10):
        engine.add_snapshot(_snap(frame=i))

    assert engine.count == 5
    snapshots = engine.get_snapshots()
    assert [s.frame_number for s in snapshots] == [5, 6, 7, 8, 9]
    print("  PASS: pruning at max_length")


def test_pruning_counter():
    """total_pruned should track how many snapshots were pruned."""
    engine = HistoryEngine(EventBus(), max_length=3)
    for i in range(8):
        engine.add_snapshot(_snap(frame=i))

    assert engine.total_pruned == 5
    assert engine.total_received == 8
    print("  PASS: pruning counter")


def test_no_pruning_under_limit():
    """No pruning should occur when under max_length."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for i in range(5):
        engine.add_snapshot(_snap(frame=i))

    assert engine.total_pruned == 0
    assert engine.count == 5
    print("  PASS: no pruning under limit")


# ── Clear ─────────────────────────────────────────────────────────

def test_clear():
    """clear() should remove all snapshots and reset counters."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for i in range(10):
        engine.add_snapshot(_snap(frame=i))

    engine.clear()
    assert engine.count == 0
    assert engine.total_received == 0
    assert engine.total_pruned == 0
    assert engine.latest() is None
    print("  PASS: clear() resets everything")


# ── Statistics ────────────────────────────────────────────────────

def test_statistics_empty():
    """Statistics on empty history should return defaults."""
    engine = HistoryEngine(EventBus(), max_length=100)
    stats = engine.get_statistics()
    assert stats.frames_stored == 0
    assert stats.average_risk == 0.0
    assert stats.maximum_risk == 0.0
    assert stats.minimum_risk == 0.0
    print("  PASS: statistics empty")


def test_statistics_risk():
    """Statistics should compute correct risk metrics."""
    engine = HistoryEngine(EventBus(), max_length=100)
    engine.add_snapshot(_snap(risk_level="LOW", final_risk=10.0))
    engine.add_snapshot(_snap(risk_level="MEDIUM", final_risk=50.0))
    engine.add_snapshot(_snap(risk_level="HIGH", final_risk=90.0))

    stats = engine.get_statistics()
    assert stats.frames_stored == 3
    assert stats.average_risk == 50.0
    assert stats.maximum_risk == 90.0
    assert stats.minimum_risk == 10.0
    print("  PASS: statistics risk")


def test_statistics_fatigue_exposure():
    """Statistics should compute fatigue and exposure metrics."""
    engine = HistoryEngine(EventBus(), max_length=100)
    engine.add_snapshot(_snap(fatigue=10.0, exposure=20.0))
    engine.add_snapshot(_snap(fatigue=30.0, exposure=40.0))

    stats = engine.get_statistics()
    assert stats.average_fatigue == 20.0
    assert stats.maximum_fatigue == 30.0
    assert stats.average_exposure == 30.0
    assert stats.maximum_exposure == 40.0
    print("  PASS: statistics fatigue/exposure")


def test_statistics_distribution():
    """Statistics should compute correct risk distribution."""
    engine = HistoryEngine(EventBus(), max_length=100)
    for _ in range(5):
        engine.add_snapshot(_snap(risk_level="LOW"))
    for _ in range(3):
        engine.add_snapshot(_snap(risk_level="MEDIUM"))
    for _ in range(2):
        engine.add_snapshot(_snap(risk_level="HIGH"))

    stats = engine.get_statistics()
    assert stats.risk_distribution.low == 5
    assert stats.risk_distribution.medium == 3
    assert stats.risk_distribution.high == 2
    assert stats.risk_distribution.total == 10
    assert stats.risk_distribution.low_pct == 50.0
    assert stats.risk_distribution.medium_pct == 30.0
    assert stats.risk_distribution.high_pct == 20.0
    print("  PASS: statistics distribution")


def test_statistics_to_dict():
    """HistoryStats.to_dict() should produce serializable dict."""
    stats = HistoryStats(
        frames_stored=100,
        average_risk=45.5,
        maximum_risk=95.0,
        minimum_risk=5.0,
        risk_distribution=RiskDistribution(low=50, medium=30, high=20),
    )
    d = stats.to_dict()
    assert d["frames_stored"] == 100
    assert d["average_risk"] == 45.5
    assert d["risk_distribution"]["low"] == 50
    assert d["risk_distribution"]["low_pct"] == 50.0
    print("  PASS: statistics to_dict()")


# ── Compute Statistics Function ───────────────────────────────────

def test_compute_statistics_empty():
    """compute_statistics([]) should return defaults."""
    stats = compute_statistics([])
    assert stats.frames_stored == 0
    print("  PASS: compute_statistics empty")


def test_compute_statistics_single():
    """compute_statistics with one snapshot should work."""
    stats = compute_statistics([_snap(risk_level="HIGH", final_risk=80.0)])
    assert stats.frames_stored == 1
    assert stats.average_risk == 80.0
    assert stats.maximum_risk == 80.0
    assert stats.minimum_risk == 80.0
    print("  PASS: compute_statistics single")


# ── Memory Limits ─────────────────────────────────────────────────

def test_memory_limit_enforced():
    """Engine should never exceed max_length."""
    engine = HistoryEngine(EventBus(), max_length=10)
    for i in range(1000):
        engine.add_snapshot(_snap(frame=i))
    assert engine.count == 10
    print("  PASS: memory limit enforced")


def test_max_length_property():
    """max_length property should return the configured value."""
    engine = HistoryEngine(EventBus(), max_length=2500)
    assert engine.max_length == 2500
    print("  PASS: max_length property")


# ── EventBus Integration ──────────────────────────────────────────

def test_engine_subscribes_to_bus():
    """HistoryEngine should subscribe to ContextSnapshotCreatedEvent."""
    bus = EventBus()
    assert bus.listener_count(ContextSnapshotCreatedEvent) == 0

    engine = HistoryEngine(bus)
    assert bus.listener_count(ContextSnapshotCreatedEvent) == 1
    print("  PASS: engine subscribes to bus")


def test_engine_receives_events():
    """HistoryEngine should record snapshots from events."""
    bus = EventBus()
    engine = HistoryEngine(bus)

    _publish(bus, frame=1, risk_level="LOW", final_risk=10.0)
    _publish(bus, frame=2, risk_level="HIGH", final_risk=85.0)

    assert engine.count == 2
    assert engine.latest().frame_number == 2
    print("  PASS: engine receives events")


def test_multiple_engines_independent():
    """Multiple HistoryEngines on same bus should be independent."""
    bus = EventBus()
    e1 = HistoryEngine(bus, max_length=5)
    e2 = HistoryEngine(bus, max_length=10)

    for i in range(20):
        _publish(bus, frame=i)

    assert e1.count == 5
    assert e2.count == 10
    print("  PASS: multiple engines independent")


# ── Performance ───────────────────────────────────────────────────

def test_add_snapshot_performance():
    """add_snapshot should be fast."""
    engine = HistoryEngine(EventBus(), max_length=5000)

    iterations = 5000
    start = time.perf_counter()
    for i in range(iterations):
        engine.add_snapshot(_snap(frame=i))
    elapsed_ms = (time.perf_counter() - start) / iterations * 1000

    assert elapsed_ms < 0.1, f"add_snapshot too slow: {elapsed_ms:.4f}ms"
    print(f"  PASS: add_snapshot = {elapsed_ms:.4f}ms (limit: 0.1ms)")


def test_statistics_performance():
    """Statistics computation should be fast for reasonable history sizes."""
    engine = HistoryEngine(EventBus(), max_length=5000)
    for i in range(1000):
        engine.add_snapshot(_snap(frame=i, risk_level="HIGH", final_risk=80.0))

    start = time.perf_counter()
    for _ in range(100):
        engine.get_statistics()
    elapsed_ms = (time.perf_counter() - start) / 100 * 1000

    assert elapsed_ms < 10.0, f"Statistics too slow: {elapsed_ms:.2f}ms"
    print(f"  PASS: statistics = {elapsed_ms:.2f}ms for 1000 frames")


def test_window_performance():
    """Window retrieval should be fast."""
    engine = HistoryEngine(EventBus(), max_length=5000)
    for i in range(5000):
        engine.add_snapshot(_snap(frame=i))

    start = time.perf_counter()
    for _ in range(100):
        engine.window(100)
    elapsed_ms = (time.perf_counter() - start) / 100 * 1000

    assert elapsed_ms < 5.0, f"Window too slow: {elapsed_ms:.2f}ms"
    print(f"  PASS: window(100) = {elapsed_ms:.3f}ms")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  RISK HISTORY ENGINE — COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        # Snapshot Ordering
        test_add_snapshot_ordering,
        test_latest_returns_most_recent,
        test_latest_empty,
        # Rolling Window
        test_window_returns_last_n,
        test_window_larger_than_history,
        test_window_zero,
        test_window_negative,
        # Pruning
        test_pruning_at_max_length,
        test_pruning_counter,
        test_no_pruning_under_limit,
        # Clear
        test_clear,
        # Statistics
        test_statistics_empty,
        test_statistics_risk,
        test_statistics_fatigue_exposure,
        test_statistics_distribution,
        test_statistics_to_dict,
        # Compute Statistics Function
        test_compute_statistics_empty,
        test_compute_statistics_single,
        # Memory Limits
        test_memory_limit_enforced,
        test_max_length_property,
        # EventBus Integration
        test_engine_subscribes_to_bus,
        test_engine_receives_events,
        test_multiple_engines_independent,
        # Performance
        test_add_snapshot_performance,
        test_statistics_performance,
        test_window_performance,
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
