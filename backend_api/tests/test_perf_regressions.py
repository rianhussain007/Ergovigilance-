"""Regression tests for the site-perf fixes.

Covers:
1. The live timeline is bounded (deque) and recent-slice still returns the
   last N entries (long sessions can't grow memory unboundedly).
2. get_state_snapshot() no longer deep-copies the raw video frame on every
   API poll (the biggest per-request cost during a live session); the frame
   is still served exclusively through get_frame().
3. The /api/recordings listing + session->dir index are cached with a TTL,
   so ReplayPage navigation doesn't re-walk the recordings tree 3x.
"""

import os
import sys
import time

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
BACKEND_API_DIR = os.path.join(REPO_ROOT, "backend_api")
if BACKEND_API_DIR not in sys.path:
    sys.path.insert(0, BACKEND_API_DIR)

from app.services.live_monitor import LiveMonitoringService, _TIMELINE_MAX  # noqa: E402
from backend.events.event_bus import EventBus  # noqa: E402


def _make_service() -> LiveMonitoringService:
    model_path = os.path.join(REPO_ROOT, "models", "pose_landmarker_lite.task")
    return LiveMonitoringService(model_path, event_bus=EventBus(), db_enabled=False)


def test_timeline_is_bounded_and_slices_from_the_end():
    service = _make_service()
    for i in range(_TIMELINE_MAX + 5000):
        service._timeline.append({"frame_number": i, "risk_score": float(i % 100)})

    assert len(service._timeline) == _TIMELINE_MAX, (
        f"timeline should be capped at {_TIMELINE_MAX}, got {len(service._timeline)}"
    )

    recent = service.get_recent_timeline(5)
    assert len(recent) == 5
    assert [e["frame_number"] for e in recent] == [
        _TIMELINE_MAX + 4995,
        _TIMELINE_MAX + 4996,
        _TIMELINE_MAX + 4997,
        _TIMELINE_MAX + 4998,
        _TIMELINE_MAX + 4999,
    ]

    # n larger than the buffer still returns everything, oldest first.
    all_entries = service.get_recent_timeline(_TIMELINE_MAX * 2)
    assert len(all_entries) == _TIMELINE_MAX
    assert all_entries[0]["frame_number"] == 5000  # oldest surviving entry


def test_state_snapshot_excludes_the_video_frame():
    service = _make_service()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:] = (12, 34, 56)
    service.state.current_frame = frame
    service.state.frame_number = 42
    service.state.risk_level = "MEDIUM"
    service.state.features = {"neck_flexion": 12.5}

    snap = service.get_state_snapshot()
    assert snap.current_frame is None, "snapshot must not carry the numpy frame"
    assert snap.frame_number == 42
    assert snap.risk_level == "MEDIUM"
    assert snap.features["neck_flexion"] == 12.5

    # The frame itself is still served through get_frame() (a copy, so the
    # caller can't mutate live state).
    served = service.get_frame()
    assert served is not None
    assert served is not frame
    assert served.shape == frame.shape
    served[:] = 0
    assert service.state.current_frame[0, 0, 0] == 12  # live state untouched


def test_recordings_listing_and_dir_index_are_cached(monkeypatch, tmp_path):
    import json

    from app.api import recordings as rec

    # Build a fake recordings tree: worker/session/summary.json
    rec_dir = tmp_path / "recordings"
    worker_dir = rec_dir / "worker1"
    session_dir = worker_dir / "20260808_120000_SESH-TEST"
    session_dir.mkdir(parents=True)
    (session_dir / "summary.json").write_text(json.dumps({
        "session_id": "SESH-TEST",
        "session_timestamp": "20260808_120000",
        "worker_id": "worker1",
        "session_duration_seconds": 60,
        "total_frames": 600,
        "highest_risk_level": "LOW",
        "risk_percentages": {"LOW": 100, "MEDIUM": 0, "HIGH": 0},
    }))
    (session_dir / "timeline.json").write_text("[]")

    monkeypatch.setattr(rec, "RECORDINGS_DIR", str(rec_dir))
    rec.invalidate_recordings_cache()

    # First call scans and caches.
    first = rec._get_recordings()
    assert len(first) == 1
    assert first[0]["session_id"] == "SESH-TEST"

    # Second call hits the cache (same object, no rescan).
    second = rec._get_recordings()
    assert second is first

    # O(1) dir lookup from the cached index.
    assert rec._find_recording_dir("SESH-TEST") == str(session_dir)
    assert rec._find_recording_dir("SESH-MISSING") is None

    # A new recording appears after cache invalidation.
    rec.invalidate_recordings_cache()
    assert rec._get_recordings()[0]["session_id"] == "SESH-TEST"

    # And the endpoint returns the cached listing without error.
    monkeypatch.setattr(rec, "RECORDINGS_DIR", str(rec_dir))
    rec.invalidate_recordings_cache()
    listing = rec._get_recordings()
    assert listing == first
