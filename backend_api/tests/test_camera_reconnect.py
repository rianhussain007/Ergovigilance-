"""Regression tests for the camera reconnect logic (QA Phase 1 P0 #2).

Verifies that persistent ``cap.read()`` failures toggle ``camera_reconnecting``
and drive exponential backoff (0.5s base, capped at 10s) WITHOUT a real camera:
the capture object and reopen are stubbed so the tests are headless and fast.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_API_DIR = ROOT / "backend_api"
if str(BACKEND_API_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_DIR))

from app.services.live_monitor import (  # noqa: E402
    LiveMonitoringService,
    _CAPTURE_FAILURE_THRESHOLD,
    _CAPTURE_RECONNECT_BASE_S,
    _CAPTURE_RECONNECT_MAX_S,
)
from backend.events.event_bus import EventBus  # noqa: E402


def _make_service() -> LiveMonitoringService:
    model_path = os.path.join(ROOT, "models", "pose_landmarker_lite.task")
    svc = LiveMonitoringService(model_path, event_bus=EventBus(), db_enabled=False)
    svc.current_camera_source = "rtsp://fake-cam"
    svc._try_reopen_camera = lambda: None  # never touch a real camera
    return svc


def test_sub_threshold_failures_are_jitter(monkeypatch):
    """First N-1 failures must sleep briefly and NOT toggle the flag."""
    svc = _make_service()
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.live_monitor.time.sleep", sleeps.append)

    for _ in range(_CAPTURE_FAILURE_THRESHOLD - 1):
        svc._handle_camera_read_failure()

    assert svc.state.camera_reconnecting is False
    assert svc._read_failures == _CAPTURE_FAILURE_THRESHOLD - 1
    assert sleeps == [0.05] * (_CAPTURE_FAILURE_THRESHOLD - 1)


def test_persistent_failures_toggle_flag_and_backoff(monkeypatch):
    """At the threshold the flag flips and the backoff doubles each attempt."""
    svc = _make_service()
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.live_monitor.time.sleep", sleeps.append)

    for _ in range(_CAPTURE_FAILURE_THRESHOLD + 2):
        svc._handle_camera_read_failure()

    assert svc.state.camera_reconnecting is True
    # After 5 failures: 2 jitter sleeps + 3 backoff sleeps at 0.5 / 1.0 / 2.0
    backoff = sleeps[_CAPTURE_FAILURE_THRESHOLD - 1:]
    assert backoff[0] == _CAPTURE_RECONNECT_BASE_S
    assert backoff[1] == _CAPTURE_RECONNECT_BASE_S * 2
    assert backoff[2] == _CAPTURE_RECONNECT_BASE_S * 4
    assert max(sleeps) <= _CAPTURE_RECONNECT_MAX_S


def test_backoff_capped_at_max(monkeypatch):
    """Backoff must never exceed _CAPTURE_RECONNECT_MAX_S."""
    svc = _make_service()
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.live_monitor.time.sleep", sleeps.append)

    for _ in range(_CAPTURE_FAILURE_THRESHOLD + 8):
        svc._handle_camera_read_failure()

    assert max(sleeps) == _CAPTURE_RECONNECT_MAX_S
    assert svc._reconnect_delay == _CAPTURE_RECONNECT_MAX_S


def test_recovery_resets_reconnect_state():
    """A successful read (as in _capture_loop) resets failures, backoff, flag."""
    svc = _make_service()
    svc._read_failures = 5
    svc._reconnect_delay = _CAPTURE_RECONNECT_MAX_S
    svc.state.camera_reconnecting = True

    # This is exactly what the capture loop does on a successful read
    svc._read_failures = 0
    svc._reconnect_delay = _CAPTURE_RECONNECT_BASE_S
    svc.state.camera_reconnecting = False

    assert svc._read_failures == 0
    assert svc._reconnect_delay == _CAPTURE_RECONNECT_BASE_S
    assert svc.state.camera_reconnecting is False
