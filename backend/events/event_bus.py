"""Synchronous EventBus for internal backend communication.

Lightweight pub/sub system. No async. No external libraries.
Listeners are called in registration order during publish().
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from backend.events.event import Event


class EventBus:
    """Synchronous event bus for backend-to-backend communication.

    Usage::

        bus = EventBus()
        bus.register(MyEvent, my_handler)
        bus.publish(MyEvent(data="hello"))
        bus.unregister(MyEvent, my_handler)
    """

    def __init__(self) -> None:
        self._listeners: dict[type[Event], list[Callable[[Event], None]]] = defaultdict(list)
        self._publish_count: int = 0

    @property
    def publish_count(self) -> int:
        return self._publish_count

    def register(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The event class to listen for.
            handler: Callable invoked when the event is published.
        """
        if handler not in self._listeners[event_type]:
            self._listeners[event_type].append(handler)

    def unregister(self, event_type: type[Event], handler: Callable[[Event], None]) -> None:
        """Remove a handler for a specific event type.

        Args:
            event_type: The event class to stop listening for.
            handler: The handler to remove.
        """
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        """Publish an event to all registered listeners.

        Listeners are called synchronously in registration order.

        Args:
            event: The event instance to publish.
        """
        self._publish_count += 1
        event_type = type(event)
        for handler in self._listeners.get(event_type, []):
            handler(event)

    def clear(self) -> None:
        """Remove all registered listeners."""
        self._listeners.clear()
        self._publish_count = 0

    def listener_count(self, event_type: type[Event]) -> int:
        """Return the number of listeners for a given event type."""
        return len(self._listeners.get(event_type, []))


# Global singleton — initialized during app startup
_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global EventBus instance."""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = EventBus()
    return _bus_instance


def init_event_bus() -> EventBus:
    """Initialize a fresh global EventBus instance."""
    global _bus_instance
    _bus_instance = EventBus()
    return _bus_instance
