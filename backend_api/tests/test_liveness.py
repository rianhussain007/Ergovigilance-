"""Tests for the liveness (anti-photo-spoof) tracker.

The verdict logic (blink counting, motion, IoU association, degradation) is
exercised without the MediaPipe model by monkeypatching the EAR computation,
so the tests run anywhere.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import liveness  # noqa: E402


def _box(x1=0.2, y1=0.2, x2=0.5, y2=0.9, conf=0.9) -> dict:
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": conf}


class _FakeLandmarker:
    """Truthy landmarker whose detect() reports a face, so _ear is reached."""

    class _Res:
        face_landmarks = [object()]  # non-empty -> the EAR path runs

    def detect(self, mp_img):
        return self._Res()


def _monkeypatch_ears(monkeypatch, sample_values):
    """Script the per-sample EAR (one value per SAMPLE, both eyes averaged).

    _sample_face calls _ear once per eye and averages them, so each sample
    consumes two values from the iterator; we emit the same value twice per
    sample so the average equals the intended EAR.
    """
    it = iter([v for v in sample_values for _ in (0, 1)])

    def fake_ear(landmarks, eye_idx):
        return next(it, 0.3)

    monkeypatch.setattr(liveness, "_ear", fake_ear)
    monkeypatch.setattr(liveness, "_load_landmarker", lambda: _FakeLandmarker())


def test_blink_detection_counts_closed_eye(monkeypatch):
    """EAR dipping below threshold after open eyes counts a blink -> live."""
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_ears(monkeypatch, [0.30, 0.30, 0.12, 0.30])
    frame = np.zeros((240, 320, 3), np.uint8)
    boxes = [_box()]
    v = {}
    for _ in range(4):
        v = tracker.update(frame, boxes)
    verdict = v[0]
    assert verdict["blinks"] >= 1
    assert verdict["liveness"] == "live"


def test_static_face_becomes_suspicious(monkeypatch):
    """No blinks + no motion over the window -> suspicious (photo)."""
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_ears(monkeypatch, [0.30, 0.30, 0.30, 0.30, 0.30])
    monkeypatch.setattr(liveness, "SUSPICIOUS_MIN_SECONDS", 0.0)
    frame = np.full((240, 320, 3), 128, np.uint8)
    boxes = [_box()]
    v = {}
    for _ in range(5):
        v = tracker.update(frame, boxes)
    assert v[0]["liveness"] == "suspicious"
    assert v[0]["blinks"] == 0


def test_motion_marks_live_without_blinks(monkeypatch):
    """Changing face-region pixels (motion) marks live even with no blinks."""
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_ears(monkeypatch, [0.30, 0.30, 0.30, 0.30, 0.30])
    monkeypatch.setattr(liveness, "MOTION_THRESHOLD", 1.0)
    monkeypatch.setattr(liveness, "MOTION_LIVE_FRACTION", 0.4)
    boxes = [_box()]
    # Alternate the frame contents so the face crop differs every sample.
    frames = [np.full((240, 320, 3), v, np.uint8) for v in (10, 200, 10, 200, 10)]
    v = {}
    for f in frames:
        v = tracker.update(f, boxes)
    assert v[0]["liveness"] == "live"


def test_multiple_faces_tracked_independently(monkeypatch):
    """Two boxes get separate verdicts (IoU association)."""
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_ears(monkeypatch, [0.30] * 12)
    monkeypatch.setattr(liveness, "SUSPICIOUS_MIN_SECONDS", 0.0)
    frame = np.full((480, 640, 3), 64, np.uint8)
    boxes = [_box(0.05, 0.1, 0.4, 0.9), _box(0.55, 0.1, 0.95, 0.9)]
    v = {}
    for _ in range(3):
        v = tracker.update(frame, boxes)
    assert set(v.keys()) == {0, 1}
    for verdict in v.values():
        assert verdict["liveness"] in ("live", "suspicious", "unverified")


def test_degrades_when_landmarker_missing(monkeypatch):
    """No landmarker -> no blinks; static face still judged suspicious."""
    tracker = liveness.FaceLivenessTracker()
    monkeypatch.setattr(liveness, "_load_landmarker", lambda: None)
    monkeypatch.setattr(liveness, "SUSPICIOUS_MIN_SECONDS", 0.0)
    frame = np.full((240, 320, 3), 128, np.uint8)
    boxes = [_box()]
    v = {}
    for _ in range(5):
        v = tracker.update(frame, boxes)
    assert v[0]["liveness"] == "suspicious"
    assert v[0]["blinks"] == 0


def test_tracker_reset(monkeypatch):
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_ears(monkeypatch, [0.30, 0.12, 0.30])
    frame = np.full((240, 320, 3), 64, np.uint8)
    boxes = [_box()]
    for _ in range(3):
        tracker.update(frame, boxes)
    tracker.reset()
    assert tracker.tracks == []
