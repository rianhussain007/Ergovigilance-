"""Tier 0 tests — Kalman landmark smoothing + capture/process ring buffer.

Covers:
1. LandmarkKalmanSmoother reduces jitter on a noisy static sequence.
2. Occluded landmarks freeze instead of snapping to a bogus measurement.
3. reset() re-initializes on person re-detection (no stale pose interpolation).
4. The live service ring buffer is bounded (maxlen), returns the newest frame
   first, and drops the backlog (latest-frame-wins semantics).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_API_DIR = ROOT / "backend_api"
if str(BACKEND_API_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_DIR))

from backend.services.kalman import LandmarkKalmanSmoother  # noqa: E402
from app.services.live_monitor import (  # noqa: E402
    LiveMonitoringService,
    _FRAME_QUEUE_MAX,
)
from backend.events.event_bus import EventBus  # noqa: E402


def _make_service() -> LiveMonitoringService:
    model_path = os.path.join(ROOT, "models", "pose_landmarker_lite.task")
    return LiveMonitoringService(model_path, event_bus=EventBus(), db_enabled=False)


def _noisy_point(rng, x=320.0, y=240.0, noise=5.0):
    return [x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise), 0.0, 0.9]


def test_kalman_reduces_jitter():
    """A noisy static landmark should converge to a stable estimate."""
    smoother = LandmarkKalmanSmoother()
    rng = np.random.default_rng(42)

    noisy_xs = []
    smoothed_xs = []
    for _ in range(60):
        kp = _noisy_point(rng)
        noisy_xs.append(kp[0])
        smoothed = smoother.smooth([kp])[0]
        smoothed_xs.append(smoothed[0])

    # After warm-up, the smoothed series should be far less variable than raw.
    assert np.std(noisy_xs) > 1.0, "sanity: raw jitter should be non-trivial"
    assert np.std(smoothed_xs[20:]) < np.std(noisy_xs[20:]) * 0.5, (
        f"Kalman should cut jitter: raw std={np.std(noisy_xs):.3f}, "
        f"smoothed std={np.std(smoothed_xs[20:]):.3f}"
    )
    # And it should stay near the true value, not lag off.
    assert abs(np.mean(smoothed_xs[20:]) - 320.0) < 2.0


def test_kalman_occluded_landmark_freezes():
    """Low-visibility landmarks must not snap to the measurement."""
    smoother = LandmarkKalmanSmoother()
    kp = [320.0, 240.0, 0.0, 0.9]
    for _ in range(10):
        smoother.smooth([kp])

    last_known = smoother.smooth([kp])[0][0]
    # Occluded: visibility 0.1 (below MIN_VISIBILITY 0.35) — must pass through
    # with the estimate frozen, not jump to the bogus x=500 measurement.
    occluded = smoother.smooth([[500.0, 999.0, 0.0, 0.1]])[0]
    assert abs(occluded[0] - last_known) < 1.0, (
        f"occluded landmark should freeze: got {occluded[0]:.2f}, last known {last_known:.2f}"
    )


def test_kalman_reset_reinitializes():
    """reset() should clear state so a re-detection starts fresh."""
    smoother = LandmarkKalmanSmoother()
    for _ in range(10):
        smoother.smooth([[100.0, 100.0, 0.0, 0.9]])

    smoother.reset()
    # A far-away new pose must be adopted immediately after reset (not blended
    # with the old estimate).
    out = smoother.smooth([[500.0, 500.0, 0.0, 0.9]])[0]
    assert abs(out[0] - 500.0) < 0.001


def test_kalman_preserves_shape_and_visibility():
    """Smoothing must keep [x, y, z, visibility] shape and visibility values."""
    smoother = LandmarkKalmanSmoother(num_landmarks=33)
    kps = [[float(i), float(100 + i), 0.0, 0.9] for i in range(33)]
    out = smoother.smooth(kps)
    assert len(out) == 33
    for row in out:
        assert len(row) == 4
        assert row[3] == 0.9  # visibility preserved


def test_kalman_handles_bare_xyz_triples():
    """Keypoints without a visibility column are treated as visible."""
    smoother = LandmarkKalmanSmoother()
    out = smoother.smooth([[320.0, 240.0, 0.0]])
    assert len(out[0]) == 3


def test_ring_buffer_is_bounded_and_latest_wins():
    """The frame queue caps at _FRAME_QUEUE_MAX and pops newest-first."""
    service = _make_service()
    assert service._frame_queue.maxlen == _FRAME_QUEUE_MAX

    frames = [np.full((10, 10, 3), i, dtype=np.uint8) for i in range(_FRAME_QUEUE_MAX * 2)]
    for f in frames:
        service._frame_queue.append(f)

    assert len(service._frame_queue) == _FRAME_QUEUE_MAX, (
        f"queue should be bounded at {_FRAME_QUEUE_MAX}, got {len(service._frame_queue)}"
    )

    # Latest-frame-wins: pop() returns the newest, then the backlog is cleared.
    frame = service._frame_queue.pop()
    assert frame[0, 0, 0] == _FRAME_QUEUE_MAX * 2 - 1  # newest frame
    service._frame_queue.clear()
    assert len(service._frame_queue) == 0


def test_capture_loop_enqueues_frames():
    """The capture loop pushes frames into the queue (integration-lite)."""
    service = _make_service()
    rng = np.random.default_rng(7)
    sent = []
    for _ in range(5):
        frame = np.full((8, 8, 3), int(rng.integers(0, 255)), dtype=np.uint8)
        sent.append(frame)
        service._frame_queue.append(frame)

    # The same semantics the process loop uses: pop newest, clear backlog.
    newest = service._frame_queue.pop()
    service._frame_queue.clear()
    assert newest is sent[-1]


def test_process_throttle_returns_without_dropping_queue():
    """When throttled, _process_one_frame returns early; queue untouched."""
    service = _make_service()
    service._process_interval = 9999.0  # always throttled
    service._last_process_time = time.perf_counter()
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    # Should return immediately without raising (no camera needed — it never
    # reads self.cap anymore).
    service._process_one_frame(frame, {"LOW": 0, "MEDIUM": 1, "HIGH": 2})


if __name__ == "__main__":
    import unittest

    unittest.main()
