"""Alert Engine V2 — Comprehensive Unit Tests.

Covers: high risk alerts, cooldown, escalation, recovery, duplicate suppression,
acknowledgment, resolution, history, performance, integration with EventBus.

Run: python scripts/test_alert_engine.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.alerts.engine import AlertEngine
from backend.alerts.models import Alert, AlertSeverity, AlertState
from backend.alerts.rules import AlertRule, RULE_HIGH_RISK, RULE_CRITICAL_RISK, RULE_RECOVERY
from backend.context.engine import ContextSnapshot
from backend.events.event_bus import EventBus
from backend.events.events import ContextSnapshotCreatedEvent


# ── Test Helpers ───────────────────────────────────────────────────

def _snapshot(session_id="test", frame_number=1, risk_level="LOW", final_risk=0.0):
    """Create a ContextSnapshot for testing."""
    return ContextSnapshot(
        session_id=session_id,
        frame_number=frame_number,
        captured_at="2026-07-05T12:00:00Z",
        risk_level=risk_level,
        final_risk=final_risk,
        base_risk=final_risk,
    )


def _publish_snapshot(bus, session_id="test", frame_number=1, risk_level="LOW", final_risk=0.0):
    """Publish a ContextSnapshotCreatedEvent."""
    snap = _snapshot(session_id, frame_number, risk_level, final_risk)
    bus.publish(ContextSnapshotCreatedEvent(snapshot=snap))
    return snap


# ── High Risk Alerts ──────────────────────────────────────────────

def test_high_risk_creates_alert():
    """HIGH risk snapshot should create an active HIGH alert."""
    bus = EventBus()
    engine = AlertEngine(bus)
    _publish_snapshot(bus, risk_level="HIGH", final_risk=80.0)

    alerts = engine.get_active_alerts()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.severity == AlertSeverity.HIGH
    assert alert.state == AlertState.ACTIVE
    assert alert.title == "High Risk Posture Detected"
    assert alert.trigger_rule == "high_risk"
    assert alert.requires_ack is True
    assert alert.session_id == "test"
    print(f"  PASS: HIGH risk -> alert created (id={alert.id})")


def test_low_risk_no_alert():
    """LOW risk snapshot should not create any alerts."""
    bus = EventBus()
    engine = AlertEngine(bus)
    _publish_snapshot(bus, risk_level="LOW", final_risk=5.0)

    alerts = engine.get_active_alerts()
    assert len(alerts) == 0
    print("  PASS: LOW risk -> no alert")


def test_medium_risk_no_alert():
    """MEDIUM risk snapshot should not create any alerts (only HIGH triggers)."""
    bus = EventBus()
    engine = AlertEngine(bus)
    _publish_snapshot(bus, risk_level="MEDIUM", final_risk=45.0)

    alerts = engine.get_active_alerts()
    assert len(alerts) == 0
    print("  PASS: MEDIUM risk -> no alert")


# ── Cooldown ──────────────────────────────────────────────────────

def test_cooldown_suppresses_duplicates():
    """Second HIGH alert within cooldown should be suppressed."""
    bus = EventBus()
    cooldown_rule = AlertRule(
        name="high_risk", severity=AlertSeverity.HIGH,
        title_template="High Risk Posture Detected",
        message_template="Worker posture risk is HIGH (final_risk={final_risk:.0f}).",
        requires_ack=True, cooldown_frames=5, escalation_threshold=10,
    )
    engine = AlertEngine(bus, rules=[cooldown_rule, RULE_CRITICAL_RISK, RULE_RECOVERY])

    _publish_snapshot(bus, frame_number=1, risk_level="HIGH", final_risk=80.0)
    assert len(engine.get_active_alerts()) == 1

    # Frames 2-5 should be suppressed (cooldown=5, decremented each frame)
    for i in range(2, 6):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=85.0)
    assert len(engine.get_active_alerts()) == 1

    # Frame 6: cooldown expires, new alert fires
    _publish_snapshot(bus, frame_number=6, risk_level="HIGH", final_risk=80.0)
    assert len(engine.get_active_alerts()) == 2
    print("  PASS: cooldown suppresses duplicates")


def test_cooldown_resets_after_expiry():
    """Cooldown should allow new alert after it expires."""
    bus = EventBus()
    cooldown_rule = AlertRule(
        name="high_risk", severity=AlertSeverity.HIGH,
        title_template="High Risk Posture Detected",
        message_template="Worker posture risk is HIGH (final_risk={final_risk:.0f}).",
        requires_ack=True, cooldown_frames=3, escalation_threshold=10,
    )
    engine = AlertEngine(bus, rules=[cooldown_rule, RULE_CRITICAL_RISK, RULE_RECOVERY])

    _publish_snapshot(bus, frame_number=1, risk_level="HIGH", final_risk=80.0)
    assert len(engine.get_active_alerts()) == 1
    history_before = len(engine.history)

    # Frames 2-3: cooldown active, suppressed
    for i in range(2, 4):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)
    assert len(engine.get_active_alerts()) == 1

    # Frame 4: cooldown expired, new alert fires
    _publish_snapshot(bus, frame_number=4, risk_level="HIGH", final_risk=80.0)
    assert len(engine.get_active_alerts()) == 2
    assert len(engine.history) > history_before
    print("  PASS: cooldown resets after expiry")


# ── Escalation ────────────────────────────────────────────────────

def test_escalation_to_critical():
    """Repeated HIGH frames should escalate to CRITICAL."""
    bus = EventBus()
    critical_rule = AlertRule(
        name="critical_risk", severity=AlertSeverity.CRITICAL,
        title_template="Critical Risk Posture -- Escalated",
        message_template="Worker posture risk has been HIGH for {consecutive_high} frames.",
        requires_ack=True, cooldown_frames=10, escalation_threshold=3,
    )
    engine = AlertEngine(bus, rules=[RULE_HIGH_RISK, critical_rule, RULE_RECOVERY])

    # Fire HIGH alert
    _publish_snapshot(bus, frame_number=1, risk_level="HIGH", final_risk=85.0)
    assert len(engine.get_active_alerts()) == 1

    # Consecutive HIGH frames (after cooldown on high_risk)
    for i in range(2, 15):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=85.0)

    # Should have both HIGH and CRITICAL alerts
    alerts = engine.get_active_alerts()
    severities = {a.severity for a in alerts}
    assert AlertSeverity.HIGH in severities
    assert AlertSeverity.CRITICAL in severities
    print(f"  PASS: escalation to CRITICAL (active alerts: {len(alerts)})")


def test_consecutive_high_counter():
    """Consecutive HIGH counter should reset on non-HIGH frame."""
    bus = EventBus()
    engine = AlertEngine(bus)

    for i in range(5):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)
    assert engine.consecutive_high == 5

    _publish_snapshot(bus, frame_number=6, risk_level="LOW", final_risk=5.0)
    assert engine.consecutive_high == 0
    print("  PASS: consecutive HIGH counter resets on LOW")


# ── Recovery ──────────────────────────────────────────────────────

def test_recovery_resolves_high_alerts():
    """LOW risk after HIGH should resolve active HIGH alerts."""
    bus = EventBus()
    engine = AlertEngine(bus)

    # Create HIGH alert
    _publish_snapshot(bus, frame_number=1, risk_level="HIGH", final_risk=85.0)
    assert len(engine.get_active_alerts()) == 1

    # Recovery to LOW
    _publish_snapshot(bus, frame_number=2, risk_level="LOW", final_risk=5.0)
    active = engine.get_active_alerts()
    assert len(active) == 0

    # Check history has resolved HIGH alert
    resolved_high = [a for a in engine.history
                     if a.state == AlertState.RESOLVED and a.trigger_rule == "high_risk"]
    assert len(resolved_high) >= 1
    print("  PASS: recovery resolves HIGH alerts")


def test_recovery_no_high_alerts():
    """Recovery should not fire if there were no HIGH alerts."""
    bus = EventBus()
    engine = AlertEngine(bus)

    _publish_snapshot(bus, frame_number=1, risk_level="LOW", final_risk=5.0)
    resolved = [a for a in engine.history if a.trigger_rule == "recovery"]
    assert len(resolved) == 0
    print("  PASS: recovery requires prior HIGH alerts")


# ── Duplicate Suppression ─────────────────────────────────────────

def test_duplicate_suppression():
    """Multiple HIGH frames should only create one alert until cooldown expires."""
    bus = EventBus()
    cooldown_rule = AlertRule(
        name="high_risk", severity=AlertSeverity.HIGH,
        title_template="High Risk Posture Detected",
        message_template="Worker posture risk is HIGH (final_risk={final_risk:.0f}).",
        requires_ack=True, cooldown_frames=5, escalation_threshold=10,
    )
    critical_rule = AlertRule(
        name="critical_risk", severity=AlertSeverity.CRITICAL,
        title_template="Critical Risk Posture -- Escalated",
        message_template="Worker posture risk has been HIGH for {consecutive_high} frames.",
        requires_ack=True, cooldown_frames=10, escalation_threshold=10,
    )
    engine = AlertEngine(bus, rules=[cooldown_rule, critical_rule, RULE_RECOVERY])

    for i in range(20):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)

    high_alerts = [a for a in engine.history if a.trigger_rule == "high_risk"]
    # Should have multiple but not 20 (due to cooldown)
    assert len(high_alerts) < 20
    print(f"  PASS: duplicate suppression ({len(high_alerts)} HIGH alerts from 20 frames)")


# ── Acknowledgment ────────────────────────────────────────────────

def test_acknowledge_alert():
    """Acknowledging an alert should update its state."""
    bus = EventBus()
    engine = AlertEngine(bus)

    _publish_snapshot(bus, risk_level="HIGH", final_risk=80.0)
    alert = engine.get_active_alerts()[0]
    result = engine.acknowledge(alert.id)
    assert result is True

    updated = engine.get_alert_by_id(alert.id)
    assert updated.state == AlertState.ACKNOWLEDGED
    print("  PASS: acknowledge alert")


def test_acknowledge_nonexistent():
    """Acknowledging nonexistent alert should return False."""
    bus = EventBus()
    engine = AlertEngine(bus)
    result = engine.acknowledge("ALT-FAKE")
    assert result is False
    print("  PASS: acknowledge nonexistent -> False")


def test_acknowledge_already_acknowledged():
    """Acknowledging an already acknowledged alert should return False."""
    bus = EventBus()
    engine = AlertEngine(bus)

    _publish_snapshot(bus, risk_level="HIGH", final_risk=80.0)
    alert = engine.get_active_alerts()[0]
    engine.acknowledge(alert.id)
    result = engine.acknowledge(alert.id)
    assert result is False
    print("  PASS: acknowledge already acknowledged -> False")


# ── Resolution ────────────────────────────────────────────────────

def test_resolve_alert():
    """Resolving an alert should remove it from active and update state."""
    bus = EventBus()
    engine = AlertEngine(bus)

    _publish_snapshot(bus, risk_level="HIGH", final_risk=80.0)
    alert = engine.get_active_alerts()[0]
    result = engine.resolve(alert.id)
    assert result is True

    active = engine.get_active_alerts()
    assert len(active) == 0

    updated = engine.get_alert_by_id(alert.id)
    assert updated.state == AlertState.RESOLVED
    print("  PASS: resolve alert")


def test_resolve_nonexistent():
    """Resolving nonexistent alert should return False."""
    bus = EventBus()
    engine = AlertEngine(bus)
    result = engine.resolve("ALT-FAKE")
    assert result is False
    print("  PASS: resolve nonexistent -> False")


def test_resolve_already_resolved():
    """Resolving an already resolved alert should return False."""
    bus = EventBus()
    engine = AlertEngine(bus)

    _publish_snapshot(bus, risk_level="HIGH", final_risk=80.0)
    alert = engine.get_active_alerts()[0]
    engine.resolve(alert.id)
    result = engine.resolve(alert.id)
    assert result is False
    print("  PASS: resolve already resolved -> False")


# ── History ───────────────────────────────────────────────────────

def test_history_tracks_all_alerts():
    """History should contain all alerts ever produced."""
    bus = EventBus()
    cooldown_rule = AlertRule(
        name="high_risk", severity=AlertSeverity.HIGH,
        title_template="High Risk Posture Detected",
        message_template="Worker posture risk is HIGH (final_risk={final_risk:.0f}).",
        requires_ack=True, cooldown_frames=1, escalation_threshold=10,
    )
    critical_rule = AlertRule(
        name="critical_risk", severity=AlertSeverity.CRITICAL,
        title_template="Critical Risk Posture -- Escalated",
        message_template="Worker posture risk has been HIGH for {consecutive_high} frames.",
        requires_ack=True, cooldown_frames=1, escalation_threshold=10,
    )
    engine = AlertEngine(bus, rules=[cooldown_rule, critical_rule, RULE_RECOVERY])

    for i in range(10):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)

    # Recovery
    _publish_snapshot(bus, frame_number=10, risk_level="LOW", final_risk=5.0)

    assert len(engine.history) > 0
    assert all(isinstance(a, Alert) for a in engine.history)
    print(f"  PASS: history tracks {len(engine.history)} alerts")


# ── Reset ─────────────────────────────────────────────────────────

def test_reset_clears_state():
    """Reset should clear all engine state."""
    bus = EventBus()
    engine = AlertEngine(bus)

    for i in range(5):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)

    engine.reset()
    assert len(engine.get_active_alerts()) == 0
    assert len(engine.history) == 0
    assert engine.consecutive_high == 0
    assert engine.frame_counter == 0
    print("  PASS: reset clears all state")


# ── Immutability ──────────────────────────────────────────────────

def test_alert_immutable():
    """Alert should be a frozen dataclass."""
    alert = Alert(id="ALT-TEST", severity=AlertSeverity.HIGH)
    try:
        alert.severity = AlertSeverity.LOW
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass
    assert alert.severity == AlertSeverity.HIGH
    print("  PASS: alert is immutable")


def test_alert_to_dict():
    """Alert.to_dict() should produce a serializable dict."""
    alert = Alert(
        id="ALT-001", session_id="s1", frame_number=5,
        severity=AlertSeverity.HIGH, state=AlertState.ACTIVE,
        title="Test", message="Test message", trigger_rule="high_risk",
        confidence=0.85, requires_ack=True,
    )
    d = alert.to_dict()
    assert d["id"] == "ALT-001"
    assert d["severity"] == "HIGH"
    assert d["state"] == "ACTIVE"
    assert d["requires_ack"] is True
    print("  PASS: alert.to_dict()")


# ── EventBus Integration ──────────────────────────────────────────

def test_engine_subscribes_to_bus():
    """AlertEngine should subscribe to ContextSnapshotCreatedEvent."""
    bus = EventBus()
    assert bus.listener_count(ContextSnapshotCreatedEvent) == 0

    engine = AlertEngine(bus)
    assert bus.listener_count(ContextSnapshotCreatedEvent) == 1
    print("  PASS: engine subscribes to bus")


def test_engine_independent_of_bus():
    """Multiple AlertEngines on same bus should be independent."""
    bus = EventBus()
    e1 = AlertEngine(bus)
    e2 = AlertEngine(bus)

    _publish_snapshot(bus, risk_level="HIGH", final_risk=80.0)
    assert len(e1.get_active_alerts()) == 1
    assert len(e2.get_active_alerts()) == 1
    print("  PASS: multiple engines independent")


# ── Performance ───────────────────────────────────────────────────

def test_publish_alert_performance():
    """Alert evaluation should be fast."""
    bus = EventBus()
    engine = AlertEngine(bus)

    # Warmup
    for i in range(10):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)
    engine.reset()

    iterations = 500
    start = time.perf_counter()
    for i in range(iterations):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=80.0)
    elapsed_ms = (time.perf_counter() - start) / iterations * 1000

    assert elapsed_ms < 1.0, f"Alert engine too slow: {elapsed_ms:.2f}ms per frame"
    print(f"  PASS: alert evaluation = {elapsed_ms:.3f}ms/frame (limit: 1ms)")


# ── Full Lifecycle ────────────────────────────────────────────────

def test_full_lifecycle():
    """Full lifecycle: HIGH -> CRITICAL -> recovery -> new HIGH."""
    bus = EventBus()
    cooldown_rule = AlertRule(
        name="high_risk", severity=AlertSeverity.HIGH,
        title_template="High Risk Posture Detected",
        message_template="Worker posture risk is HIGH (final_risk={final_risk:.0f}).",
        requires_ack=True, cooldown_frames=2, escalation_threshold=10,
    )
    critical_rule = AlertRule(
        name="critical_risk", severity=AlertSeverity.CRITICAL,
        title_template="Critical Risk Posture -- Escalated",
        message_template="Worker posture risk has been HIGH for {consecutive_high} frames.",
        requires_ack=True, cooldown_frames=2, escalation_threshold=3,
    )
    engine = AlertEngine(bus, rules=[cooldown_rule, critical_rule, RULE_RECOVERY])

    # 1. Initial HIGH
    _publish_snapshot(bus, frame_number=1, risk_level="HIGH", final_risk=85.0)
    assert len(engine.get_active_alerts()) == 1

    # 2. Escalate to CRITICAL
    for i in range(2, 10):
        _publish_snapshot(bus, frame_number=i, risk_level="HIGH", final_risk=85.0)
    alerts = engine.get_active_alerts()
    severities = {a.severity for a in alerts}
    assert AlertSeverity.CRITICAL in severities

    # 3. Recovery
    _publish_snapshot(bus, frame_number=11, risk_level="LOW", final_risk=5.0)
    assert len(engine.get_active_alerts()) == 0

    # 4. New HIGH after cooldown
    for i in range(12, 16):
        _publish_snapshot(bus, frame_number=i, risk_level="LOW", final_risk=5.0)
    _publish_snapshot(bus, frame_number=16, risk_level="HIGH", final_risk=80.0)
    assert len(engine.get_active_alerts()) == 1

    print("  PASS: full lifecycle (HIGH -> CRITICAL -> recovery -> new HIGH)")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  ALERT ENGINE V2 — COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        # High Risk Alerts
        test_high_risk_creates_alert,
        test_low_risk_no_alert,
        test_medium_risk_no_alert,
        # Cooldown
        test_cooldown_suppresses_duplicates,
        test_cooldown_resets_after_expiry,
        # Escalation
        test_escalation_to_critical,
        test_consecutive_high_counter,
        # Recovery
        test_recovery_resolves_high_alerts,
        test_recovery_no_high_alerts,
        # Duplicate Suppression
        test_duplicate_suppression,
        # Acknowledgment
        test_acknowledge_alert,
        test_acknowledge_nonexistent,
        test_acknowledge_already_acknowledged,
        # Resolution
        test_resolve_alert,
        test_resolve_nonexistent,
        test_resolve_already_resolved,
        # History
        test_history_tracks_all_alerts,
        # Reset
        test_reset_clears_state,
        # Immutability
        test_alert_immutable,
        test_alert_to_dict,
        # EventBus Integration
        test_engine_subscribes_to_bus,
        test_engine_independent_of_bus,
        # Performance
        test_publish_alert_performance,
        # Full Lifecycle
        test_full_lifecycle,
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
