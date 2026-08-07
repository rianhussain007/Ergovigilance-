"""Risk History Engine — records every ContextSnapshot during a session.

Subscribes to ContextSnapshotCreatedEvent. Maintains rolling history
with configurable max length. Provides statistics and windowed access.

Tiered storage for long sessions:
- Recent snapshots: full resolution (last RECENT_WINDOW seconds)
- Older snapshots: downsampled to reduce memory usage
- Running statistics: always maintained for full session
"""

from __future__ import annotations

from collections import deque
from typing import Optional

from backend.context.engine import ContextSnapshot
from backend.events.event import Event
from backend.events.event_bus import EventBus
from backend.events.events import ContextSnapshotCreatedEvent
from backend.history.models import HistoryStats
from backend.history.statistics import compute_statistics


# Tiered storage configuration
RECENT_WINDOW_SECONDS = 300  # Keep full resolution for last 5 minutes
DOWNSAMPLE_FACTOR = 10  # Keep every 10th snapshot for older data


class HistoryEngine:
    """Records ContextSnapshots and provides history access and statistics.

    Subscribes to ContextSnapshotCreatedEvent via the EventBus.

    Uses tiered storage for long sessions:
    - Recent snapshots (last 5 minutes): full resolution
    - Older snapshots: downsampled to reduce memory
    - Running statistics: always maintained for full session

    Usage::

        engine = HistoryEngine(event_bus, max_length=50000)
        snapshots = engine.get_snapshots()
        stats = engine.get_statistics()
    """

    def __init__(self, event_bus: EventBus, max_length: int = 50000):
        self._event_bus = event_bus
        self._max_length = max_length
        self._snapshots: deque[ContextSnapshot] = deque(maxlen=max_length)
        self._total_received: int = 0
        self._total_pruned: int = 0
        self._downsample_counter: int = 0
        self._session_start_time: float = 0.0
        self._last_snapshot_time: float = 0.0

        # Running statistics for full session (always maintained)
        self._running_stats = {
            "risk_sum": 0.0,
            "fatigue_sum": 0.0,
            "exposure_sum": 0.0,
            "risk_max": 0.0,
            "fatigue_max": 0.0,
            "exposure_max": 0.0,
            "risk_min": 100.0,
            "frames_high_risk": 0,
            "frames_medium_risk": 0,
            "frames_low_risk": 0,
            "total_frames": 0,
        }

        # Subscribe
        self._event_bus.register(ContextSnapshotCreatedEvent, self._on_snapshot)

    @property
    def max_length(self) -> int:
        return self._max_length

    @property
    def total_received(self) -> int:
        return self._total_received

    @property
    def total_pruned(self) -> int:
        return self._total_pruned

    @property
    def count(self) -> int:
        return len(self._snapshots)

    def add_snapshot(self, snapshot: ContextSnapshot) -> None:
        """Add a snapshot to the history with tiered storage.

        Recent snapshots are kept at full resolution.
        Older snapshots are downsampled to save memory.
        Running statistics are always maintained.
        """
        import time

        self._total_received += 1
        current_time = time.time()

        # Track session start
        if self._session_start_time == 0.0:
            self._session_start_time = current_time

        # Update running statistics (always, regardless of storage tier)
        self._update_running_stats(snapshot)

        # Determine if we should store this snapshot
        session_elapsed = current_time - self._session_start_time
        should_store = False

        if session_elapsed < RECENT_WINDOW_SECONDS:
            # Recent window: store all snapshots
            should_store = True
        else:
            # Older data: downsample
            self._downsample_counter += 1
            if self._downsample_counter % DOWNSAMPLE_FACTOR == 0:
                should_store = True

        if should_store:
            if len(self._snapshots) == self._max_length:
                self._total_pruned += 1
            self._snapshots.append(snapshot)

        self._last_snapshot_time = current_time

    def _update_running_stats(self, snapshot: ContextSnapshot) -> None:
        """Update running statistics with a new snapshot."""
        risk = snapshot.final_risk
        fatigue = snapshot.fatigue_score
        exposure = snapshot.exposure_score

        self._running_stats["risk_sum"] += risk
        self._running_stats["fatigue_sum"] += fatigue
        self._running_stats["exposure_sum"] += exposure
        self._running_stats["risk_max"] = max(self._running_stats["risk_max"], risk)
        self._running_stats["fatigue_max"] = max(self._running_stats["fatigue_max"], fatigue)
        self._running_stats["exposure_max"] = max(self._running_stats["exposure_max"], exposure)
        self._running_stats["risk_min"] = min(self._running_stats["risk_min"], risk)
        self._running_stats["total_frames"] += 1

        if snapshot.risk_level == "HIGH":
            self._running_stats["frames_high_risk"] += 1
        elif snapshot.risk_level == "MEDIUM":
            self._running_stats["frames_medium_risk"] += 1
        else:
            self._running_stats["frames_low_risk"] += 1

    def get_snapshots(self) -> list[ContextSnapshot]:
        """Return all stored snapshots in chronological order."""
        return list(self._snapshots)

    def latest(self) -> Optional[ContextSnapshot]:
        """Return the most recent snapshot, or None if empty."""
        return self._snapshots[-1] if self._snapshots else None

    def window(self, last_n: int) -> list[ContextSnapshot]:
        """Return the last N snapshots in chronological order."""
        if last_n <= 0:
            return []
        n = min(last_n, len(self._snapshots))
        return list(self._snapshots)[-n:]

    def clear(self) -> None:
        """Clear all stored snapshots."""
        self._snapshots.clear()
        self._total_received = 0
        self._total_pruned = 0
        self._downsample_counter = 0
        self._session_start_time = 0.0
        self._last_snapshot_time = 0.0
        self._running_stats = {
            "risk_sum": 0.0,
            "fatigue_sum": 0.0,
            "exposure_sum": 0.0,
            "risk_max": 0.0,
            "fatigue_max": 0.0,
            "exposure_max": 0.0,
            "risk_min": 100.0,
            "frames_high_risk": 0,
            "frames_medium_risk": 0,
            "frames_low_risk": 0,
            "total_frames": 0,
        }

    def get_statistics(self) -> HistoryStats:
        """Compute and return statistics for all stored snapshots."""
        return compute_statistics(list(self._snapshots))

    def get_full_session_statistics(self) -> HistoryStats:
        """Return statistics for the full session using running counters.

        This provides accurate statistics even when snapshots are downsampled.
        """
        total = self._running_stats["total_frames"]
        if total == 0:
            return HistoryStats(
                frames_stored=len(self._snapshots),
                session_duration_seconds=0.0,
                average_risk=0.0,
                maximum_risk=0.0,
                minimum_risk=0.0,
                average_fatigue=0.0,
                average_exposure=0.0,
            )

        return HistoryStats(
            frames_stored=total,
            session_duration_seconds=self._last_snapshot_time - self._session_start_time,
            average_risk=self._running_stats["risk_sum"] / total,
            maximum_risk=self._running_stats["risk_max"],
            minimum_risk=self._running_stats["risk_min"] if self._running_stats["risk_min"] < 100 else 0.0,
            average_fatigue=self._running_stats["fatigue_sum"] / total,
            average_exposure=self._running_stats["exposure_sum"] / total,
        )

    def export(self) -> dict:
        """Export history data for persistence.

        Returns a dictionary containing recent snapshots (serialized)
        and full-session statistics suitable for inclusion in a SessionRecord.
        """
        snapshots = list(self._snapshots)
        full_stats = self.get_full_session_statistics()
        return {
            "snapshots": [s.to_dict() for s in snapshots],
            "statistics": full_stats.to_dict(),
            "total_received": self._total_received,
            "total_pruned": self._total_pruned,
            "session_statistics": {
                "total_frames": self._running_stats["total_frames"],
                "frames_high_risk": self._running_stats["frames_high_risk"],
                "frames_medium_risk": self._running_stats["frames_medium_risk"],
                "frames_low_risk": self._running_stats["frames_low_risk"],
            },
        }

    def _on_snapshot(self, event: Event) -> None:
        """Handle ContextSnapshotCreatedEvent."""
        if not isinstance(event, type(Event)):
            snapshot = getattr(event, "snapshot", None)
            if snapshot is not None:
                self.add_snapshot(snapshot)
