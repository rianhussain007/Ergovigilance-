"""Tests for the liveness (anti-photo-spoof) tracker.

The verdict logic (planarity 2D-vs-3D, non-rigid mouth motion, blink
counting, motion, degradation) is exercised without the MediaPipe model by
monkeypatching the landmark points and EAR computation, so the tests run
anywhere.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import liveness  # noqa: E402

# FaceLandmarker returns 478 landmarks; the mouth indices used by the
# non-rigid signal go up to ~409, so the synthetic grids must have at least
# that many points for the mouth path to run.
_N_POINTS = 480


def _box(x1=0.2, y1=0.2, x2=0.5, y2=0.9, conf=0.9) -> dict:
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": conf}


class _FakeLandmarker:
    """Truthy landmarker whose detect() reports a face, so _ear/_planarity run."""

    class _Res:
        face_landmarks = [object()]  # non-empty -> the sample path runs

    def detect(self, mp_img):
        return self._Res()


def _monkeypatch_samples(monkeypatch, ear_values=None, point_sets=None):
    """Stub the landmarker + per-sample signals.

    - ``ear_values``: one EAR per sample (both eyes averaged); None -> always open.
    - ``point_sets``: list of Nx2 landmark arrays, one per sample, fed to
      ``_planarity`` in order. None -> use a stable grid (no displacement).
    """
    if point_sets is None:
        rng = np.random.default_rng(7)
        base = _base_grid()
        point_sets = [base + rng.normal(0, 1e-6, base.shape).astype(np.float32)] * 12

    ears = iter([v for v in (ear_values or [0.30] * 12) for _ in (0, 1)])
    pts = iter(point_sets)

    def fake_ear(landmarks, eye_idx):
        return next(ears, 0.3)

    def fake_points(landmarks):
        return next(pts, None)

    monkeypatch.setattr(liveness, "_ear", fake_ear)
    monkeypatch.setattr(liveness, "_landmark_points", fake_points)
    monkeypatch.setattr(liveness, "_load_landmarker", lambda: _FakeLandmarker())


def _run(tracker, n, frames=None):
    """Run n updates and return the last verdict for box 0."""
    v = {}
    for i in range(n):
        f = (frames[i] if frames else np.zeros((240, 320, 3), np.uint8))
        v = tracker.update(f, [_box()])
    return v[0]


def _base_grid():
    """A 2D grid of non-collinear points (homography needs 2D spread)."""
    side = int(round(_N_POINTS ** 0.5))
    xx, yy = np.meshgrid(np.linspace(0.1, 0.9, side), np.linspace(0.1, 0.9, side))
    pts = np.stack([xx.ravel(), yy.ravel()], axis=1).astype(np.float32)
    return pts[:_N_POINTS]


def _planar_motion(n=12):
    """Landmark sets related by a true homography -> flat 2D surface motion."""
    import cv2
    base = _base_grid()
    sets = []
    for i in range(n):
        # A genuine projective transform (affine + perspective terms): any
        # planar object under any motion maps exactly via a homography, so
        # RANSAC fits with ~100% inliers regardless of how the photo moves.
        t = i * 0.01
        H = np.array([
            [1.0, 0.05, t * 4.0],
            [0.02, 1.0, t * 2.0],
            [0.0002, 0.0001, 1.0],
        ], dtype=np.float64)
        pts = cv2.perspectiveTransform(base.reshape(-1, 1, 2), H).reshape(-1, 2)
        sets.append(pts.astype(np.float32))
    return sets


def _parallax_motion(n=12):
    """Landmark sets with depth-dependent motion -> breaks a single homography.

    Each step applies a LARGE head rotation: points near the center (nose)
    shift much more than the edges (ears) because they sit at a different
    depth. The per-step parallax is big enough that even two *consecutive*
    sets cannot be explained by one homography.
    """
    base = _base_grid()
    sets = []
    for i in range(n):
        t = 0.06 + i * 0.03  # large per-step rotation (compare planar's 0.01)
        pts = base.copy()
        center = 0.5
        depth_scale = 1.0 - np.abs(pts[:, 0] - center) * 2.0  # 1.0 center .. 0.2 edge
        pts[:, 0] += t * (0.2 + 2.0 * depth_scale)
        pts[:, 1] += 0.5 * t * (0.2 + 2.0 * depth_scale)
        sets.append(pts.astype(np.float32))
    return sets


def _mouth_motion(n=12, mouth_disp=0.02):
    """Head still, but the mouth landmarks move (talking) -> non-rigid.

    Base and mouth-moved sets ALTERNATE so every consecutive pair shows the
    mouth moving beyond the (near-zero) head motion.
    """
    base = _base_grid()
    mouth_idx = list(liveness._MOUTH_INDICES)
    moved = base.copy()
    moved[mouth_idx, 0] += mouth_disp
    moved[mouth_idx, 1] += mouth_disp * 0.3
    sets = [(base if i % 2 == 0 else moved).astype(np.float32) for i in range(n)]
    return sets


def test_moving_photo_is_suspicious(monkeypatch):
    """Planar (homography-explained) motion = 2D surface -> suspicious."""
    tracker = liveness.FaceLivenessTracker()
    monkeypatch.setattr(liveness, "PLANAR_SUSPICIOUS_SECONDS", 0.0)
    monkeypatch.setattr(liveness, "PLANAR_DECIDED_FRACTION", 0.4)
    _monkeypatch_samples(monkeypatch, point_sets=_planar_motion())
    v = _run(tracker, 12)
    assert v["planar_fraction"] > 0.8
    assert v["liveness"] == "suspicious"


def test_moving_3d_head_is_live(monkeypatch):
    """Parallax (non-homography) motion = 3D object -> live."""
    tracker = liveness.FaceLivenessTracker()
    monkeypatch.setattr(liveness, "PARALLAX_DECIDED_FRACTION", 0.4)
    _monkeypatch_samples(monkeypatch, point_sets=_parallax_motion())
    v = _run(tracker, 12)
    assert v["parallax_fraction"] > 0.5
    assert v["liveness"] == "live"


def test_blink_overrides_planar_evidence(monkeypatch):
    """A real person walking moves homography-explainably (planar), but a
    single blink must override that — photos can never blink."""
    tracker = liveness.FaceLivenessTracker()
    monkeypatch.setattr(liveness, "PLANAR_SUSPICIOUS_SECONDS", 0.0)
    monkeypatch.setattr(liveness, "PLANAR_DECIDED_FRACTION", 0.4)
    _monkeypatch_samples(monkeypatch, point_sets=_planar_motion(),
                         ear_values=[0.30, 0.30, 0.30, 0.12, 0.30])
    v = _run(tracker, 12)
    assert v["planar_fraction"] > 0.8       # motion IS planar (like walking)
    assert v["blinks"] >= 1                 # but the person blinked
    assert v["liveness"] == "live"          # live wins over planar evidence


def test_mouth_motion_is_live(monkeypatch):
    """Talking moves the mouth beyond the head transform -> non-rigid -> live."""
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_samples(monkeypatch, point_sets=_mouth_motion())
    v = _run(tracker, 12)
    assert v["nonrigid_fraction"] > 0.5
    assert v["liveness"] == "live"


def test_planar_evidence_needs_time(monkeypatch):
    """Planar evidence alone is not suspicious until the window elapses —
    a real person walking through frame briefly stays unverified, not flagged."""
    tracker = liveness.FaceLivenessTracker()
    _monkeypatch_samples(monkeypatch, point_sets=_planar_motion())
    v = _run(tracker, 12)  # real wall-clock, far below PLANAR_SUSPICIOUS_SECONDS
    assert v["liveness"] == "unverified"


def test_blink_detection_counts_closed_eye(monkeypatch):
    """EAR dipping below threshold after open eyes counts a blink -> live."""
    tracker = liveness.FaceLivenessTracker()
    # No motion (stable grid) but a real blink: [0.30, 0.30, 0.12, 0.30].
    _monkeypatch_samples(monkeypatch, ear_values=[0.30, 0.30, 0.12, 0.30])
    v = _run(tracker, 5)
    assert v["blinks"] >= 1
    assert v["liveness"] == "live"


def test_static_face_without_blinks_is_suspicious(monkeypatch):
    """No motion, no blinks over the window -> suspicious (frozen photo)."""
    tracker = liveness.FaceLivenessTracker()
    monkeypatch.setattr(liveness, "SUSPICIOUS_MIN_SECONDS", 0.0)
    _monkeypatch_samples(monkeypatch, ear_values=[0.30] * 6)
    v = _run(tracker, 6)
    assert v["liveness"] == "suspicious"
    assert v["blinks"] == 0


def test_multiple_faces_tracked_independently(monkeypatch):
    """Two boxes get separate verdicts (IoU association)."""
    tracker = liveness.FaceLivenessTracker()
    monkeypatch.setattr(liveness, "SUSPICIOUS_MIN_SECONDS", 0.0)
    _monkeypatch_samples(monkeypatch, ear_values=[0.30] * 12)
    frame = np.full((480, 640, 3), 64, np.uint8)
    boxes = [_box(0.05, 0.1, 0.4, 0.9), _box(0.55, 0.1, 0.95, 0.9)]
    v = {}
    for _ in range(3):
        v = tracker.update(frame, boxes)
    assert set(v.keys()) == {0, 1}
    for verdict in v.values():
        assert verdict["liveness"] in ("live", "suspicious", "unverified")


def test_degrades_when_landmarker_missing(monkeypatch):
    """No landmarker -> no blinks/planarity; still face judged suspicious."""
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
    _monkeypatch_samples(monkeypatch, ear_values=[0.30, 0.12, 0.30])
    frame = np.full((240, 320, 3), 64, np.uint8)
    boxes = [_box()]
    for _ in range(3):
        tracker.update(frame, boxes)
    tracker.reset()
    assert tracker.tracks == []
