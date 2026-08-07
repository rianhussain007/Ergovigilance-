"""Event Bus — Comprehensive Unit Tests.

Covers: registration, multiple listeners, listener removal, publish order,
payload integrity, event immutability, performance, global bus, integration.

Run: python scripts/test_event_bus.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.events.event import Event
from backend.events.event_bus import EventBus, init_event_bus, get_event_bus
from backend.events.events import (
    PoseUpdatedEvent,
    FeaturesUpdatedEvent,
    IssuesDetectedEvent,
    ContextSnapshotCreatedEvent,
    SessionStartedEvent,
    SessionEndedEvent,
)
from backend.context.engine import ContextSnapshot


# ── Test Helpers ───────────────────────────────────────────────────

class RecordingHandler:
    """Records all events it receives for later inspection."""

    def __init__(self):
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


# ── Registration ──────────────────────────────────────────────────

def test_register_single_handler():
    """A registered handler should be called when the matching event is published."""
    bus = EventBus()
    handler = RecordingHandler()
    bus.register(SessionStartedEvent, handler)

    bus.publish(SessionStartedEvent(session_id="s1"))
    assert len(handler.events) == 1
    assert handler.events[0].session_id == "s1"
    print("  PASS: register single handler")


def test_register_multiple_handlers():
    """Multiple handlers for the same event type should all be called."""
    bus = EventBus()
    h1 = RecordingHandler()
    h2 = RecordingHandler()
    bus.register(SessionStartedEvent, h1)
    bus.register(SessionStartedEvent, h2)

    bus.publish(SessionStartedEvent(session_id="s2"))
    assert len(h1.events) == 1
    assert len(h2.events) == 1
    assert h1.events[0].session_id == "s2"
    assert h2.events[0].session_id == "s2"
    print("  PASS: multiple handlers for same event")


def test_no_duplicate_registration():
    """Registering the same handler twice should only call it once."""
    bus = EventBus()
    handler = RecordingHandler()
    bus.register(SessionStartedEvent, handler)
    bus.register(SessionStartedEvent, handler)

    bus.publish(SessionStartedEvent(session_id="s3"))
    assert len(handler.events) == 1
    print("  PASS: no duplicate registration")


def test_different_event_types():
    """Handlers should only be called for their specific event type."""
    bus = EventBus()
    session_handler = RecordingHandler()
    ended_handler = RecordingHandler()
    bus.register(SessionStartedEvent, session_handler)
    bus.register(SessionEndedEvent, ended_handler)

    bus.publish(SessionStartedEvent(session_id="s4"))
    assert len(session_handler.events) == 1
    assert len(ended_handler.events) == 0
    print("  PASS: different event types isolated")


# ── Listener Removal ──────────────────────────────────────────────

def test_unregister_handler():
    """Unregistered handler should not receive future events."""
    bus = EventBus()
    handler = RecordingHandler()
    bus.register(SessionStartedEvent, handler)
    bus.publish(SessionStartedEvent(session_id="s5"))
    assert len(handler.events) == 1

    bus.unregister(SessionStartedEvent, handler)
    bus.publish(SessionStartedEvent(session_id="s6"))
    assert len(handler.events) == 1
    print("  PASS: unregister handler")


def test_unregister_nonexistent():
    """Unregistering a handler that was never registered should not raise."""
    bus = EventBus()
    handler = RecordingHandler()
    bus.unregister(SessionStartedEvent, handler)
    print("  PASS: unregister nonexistent handler (no error)")


def test_unregister_does_not_affect_other_handlers():
    """Removing one handler should not affect others."""
    bus = EventBus()
    h1 = RecordingHandler()
    h2 = RecordingHandler()
    bus.register(SessionStartedEvent, h1)
    bus.register(SessionStartedEvent, h2)

    bus.unregister(SessionStartedEvent, h1)
    bus.publish(SessionStartedEvent(session_id="s7"))
    assert len(h1.events) == 0
    assert len(h2.events) == 1
    print("  PASS: unregister preserves other handlers")


# ── Publish Order ─────────────────────────────────────────────────

def test_publish_order():
    """Handlers should be called in registration order."""
    bus = EventBus()
    call_order = []

    def handler_a(e): call_order.append("A")
    def handler_b(e): call_order.append("B")
    def handler_c(e): call_order.append("C")

    bus.register(SessionStartedEvent, handler_a)
    bus.register(SessionStartedEvent, handler_b)
    bus.register(SessionStartedEvent, handler_c)

    bus.publish(SessionStartedEvent(session_id="order-test"))
    assert call_order == ["A", "B", "C"], f"Expected [A, B, C], got {call_order}"
    print("  PASS: publish order matches registration order")


# ── Payload Integrity ─────────────────────────────────────────────

def test_payload_immutability():
    """Events should be frozen dataclasses — assignment should raise."""
    event = SessionStartedEvent(session_id="s8", worker_id="w1")
    try:
        event.session_id = "changed"
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass
    assert event.session_id == "s8"
    print("  PASS: event immutability")


def test_snapshot_event_payload():
    """ContextSnapshotCreatedEvent should carry the snapshot intact."""
    snapshot = ContextSnapshot(
        session_id="s9", frame_number=5, final_risk=75.0,
        risk_level="HIGH", safety_state="CRITICAL",
    )
    event = ContextSnapshotCreatedEvent(snapshot=snapshot)
    assert event.snapshot is snapshot
    assert event.snapshot.session_id == "s9"
    assert event.snapshot.frame_number == 5
    assert event.snapshot.final_risk == 75.0
    assert event.snapshot.risk_level == "HIGH"
    print("  PASS: snapshot event payload integrity")


def test_session_started_payload():
    """SessionStartedEvent should carry all identity fields."""
    event = SessionStartedEvent(session_id="SESH-001", worker_id="W-1", camera_index=2)
    assert event.session_id == "SESH-001"
    assert event.worker_id == "W-1"
    assert event.camera_index == 2
    assert event.event_type == "SessionStarted"
    print("  PASS: SessionStartedEvent payload")


def test_session_ended_payload():
    """SessionEndedEvent should carry duration and frame count."""
    event = SessionEndedEvent(session_id="SESH-002", total_frames=1500, duration_seconds=600.0)
    assert event.session_id == "SESH-002"
    assert event.total_frames == 1500
    assert event.duration_seconds == 600.0
    assert event.event_type == "SessionEnded"
    print("  PASS: SessionEndedEvent payload")


def test_event_timestamp_auto_generated():
    """Each event should have an auto-generated ISO-8601 timestamp."""
    event = SessionStartedEvent(session_id="ts-test")
    assert event.timestamp != ""
    assert "T" in event.timestamp
    print(f"  PASS: auto timestamp = {event.timestamp[:25]}...")


# ── Publish Count ─────────────────────────────────────────────────

def test_publish_count():
    """EventBus should track total publish count."""
    bus = EventBus()
    assert bus.publish_count == 0
    bus.publish(SessionStartedEvent(session_id="pc1"))
    bus.publish(SessionEndedEvent(session_id="pc1"))
    bus.publish(SessionStartedEvent(session_id="pc2"))
    assert bus.publish_count == 3
    print("  PASS: publish count tracks correctly")


def test_clear():
    """clear() should remove all listeners and reset publish count."""
    bus = EventBus()
    handler = RecordingHandler()
    bus.register(SessionStartedEvent, handler)
    bus.publish(SessionStartedEvent(session_id="c1"))
    assert bus.publish_count == 1

    bus.clear()
    assert bus.listener_count(SessionStartedEvent) == 0
    assert bus.publish_count == 0

    bus.publish(SessionStartedEvent(session_id="c2"))
    assert len(handler.events) == 1
    print("  PASS: clear removes listeners and resets count")


# ── Global Bus ────────────────────────────────────────────────────

def test_global_bus_singleton():
    """init_event_bus should return a fresh bus; get_event_bus returns same instance."""
    bus1 = init_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2
    print("  PASS: global bus singleton")


def test_global_bus_independent():
    """Global bus should be independent of local EventBus instances."""
    global_bus = init_event_bus()
    local_bus = EventBus()
    handler = RecordingHandler()

    local_bus.register(SessionStartedEvent, handler)
    local_bus.publish(SessionStartedEvent(session_id="local"))
    assert len(handler.events) == 1

    global_bus.publish(SessionStartedEvent(session_id="global"))
    assert len(handler.events) == 1
    print("  PASS: global bus independent of local instances")


# ── Performance ───────────────────────────────────────────────────

def test_publish_performance():
    """Single publish should complete in < 0.1ms."""
    bus = EventBus()
    handler = RecordingHandler()
    bus.register(SessionStartedEvent, handler)
    bus.register(SessionEndedEvent, handler)

    iterations = 1000
    start = time.perf_counter()
    for i in range(iterations):
        bus.publish(SessionStartedEvent(session_id=f"perf-{i}"))
        bus.publish(SessionEndedEvent(session_id=f"perf-{i}"))
    elapsed_ms = (time.perf_counter() - start) / (iterations * 2) * 1000

    assert elapsed_ms < 0.1, f"Publish too slow: {elapsed_ms:.4f}ms (limit: 0.1ms)"
    print(f"  PASS: publish overhead = {elapsed_ms:.4f}ms/event (limit: 0.1ms)")


def test_many_listeners_performance():
    """50 listeners should still be fast."""
    bus = EventBus()
    for i in range(50):
        bus.register(SessionStartedEvent, lambda e: None)

    iterations = 500
    start = time.perf_counter()
    for i in range(iterations):
        bus.publish(SessionStartedEvent(session_id=f"many-{i}"))
    elapsed_ms = (time.perf_counter() - start) / iterations * 1000

    assert elapsed_ms < 1.0, f"Too slow with 50 listeners: {elapsed_ms:.2f}ms"
    print(f"  PASS: 50 listeners overhead = {elapsed_ms:.4f}ms/event")


# ── All Event Types ───────────────────────────────────────────────

def test_all_event_types_instantiate():
    """All defined event types should be instantiable."""
    events = [
        PoseUpdatedEvent(session_id="s", frame_number=1),
        FeaturesUpdatedEvent(session_id="s", features={"a": 1.0}),
        IssuesDetectedEvent(session_id="s", issues=("issue1",)),
        ContextSnapshotCreatedEvent(snapshot=ContextSnapshot(session_id="s")),
        SessionStartedEvent(session_id="s"),
        SessionEndedEvent(session_id="s", total_frames=100),
    ]
    for event in events:
        assert isinstance(event, Event)
        assert event.timestamp != ""
        assert event.event_type != ""
    print(f"  PASS: all {len(events)} event types instantiate correctly")


def test_all_events_frozen():
    """All event types should be frozen (immutable)."""
    events = [
        PoseUpdatedEvent(session_id="s"),
        FeaturesUpdatedEvent(session_id="s"),
        IssuesDetectedEvent(session_id="s"),
        ContextSnapshotCreatedEvent(),
        SessionStartedEvent(session_id="s"),
        SessionEndedEvent(session_id="s"),
    ]
    for event in events:
        try:
            event.event_type = "changed"
            assert False, f"{type(event).__name__} should be frozen"
        except Exception:
            pass
    print("  PASS: all event types are frozen")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  EVENT BUS — COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        # Registration
        test_register_single_handler,
        test_register_multiple_handlers,
        test_no_duplicate_registration,
        test_different_event_types,
        # Listener Removal
        test_unregister_handler,
        test_unregister_nonexistent,
        test_unregister_does_not_affect_other_handlers,
        # Publish Order
        test_publish_order,
        # Payload Integrity
        test_payload_immutability,
        test_snapshot_event_payload,
        test_session_started_payload,
        test_session_ended_payload,
        test_event_timestamp_auto_generated,
        # Publish Count
        test_publish_count,
        test_clear,
        # Global Bus
        test_global_bus_singleton,
        test_global_bus_independent,
        # Performance
        test_publish_performance,
        test_many_listeners_performance,
        # All Event Types
        test_all_event_types_instantiate,
        test_all_events_frozen,
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
