"""Per-person risk (station view): compute_person_risks scores every detected
pose independently — the primary carries the authoritative engine risk, each
secondary gets its own deterministic threshold risk, and a visibly bad posture
on a secondary worker is still flagged.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.pose_engine import compute_person_risks  # noqa: E402


class _LM:
    """Minimal MediaPipe-landmark stand-in."""

    __slots__ = ("x", "y", "z", "visibility")

    def __init__(self, x, y, visibility=1.0):
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0
        self.visibility = float(visibility)


def _make_pose(neck_y: float = 0.4, trunk_y: float = 0.5, vis: float = 0.9):
    """A 33-landmark pose. Trunk flexion is encoded by the neck/hip geometry:
    lowering the neck toward the hip line raises trunk flexion."""
    landmarks = []
    for i in range(33):
        # Default upright-ish body: shoulders ~0.4, hips ~0.55.
        y = trunk_y if i >= 23 else (neck_y if i in (11, 12) else 0.4)
        x = 0.5 + (0.05 if i % 2 else -0.05)
        landmarks.append(_LM(x, y, vis))
    return landmarks


def test_two_people_each_get_a_risk_entry():
    risks = compute_person_risks(
        [_make_pose(), _make_pose()], 640, 480, primary_index=1, primary_risk_level="HIGH"
    )
    assert len(risks) == 2
    # Primary (index 1) mirrors the authoritative engine risk.
    assert risks[1]["is_primary"] is True
    assert risks[1]["risk_level"] == "HIGH"
    # Secondary is scored independently and lands in a valid band.
    assert risks[0]["is_primary"] is False
    assert risks[0]["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert risks[0]["person_index"] == 0


def test_secondary_bad_posture_is_flagged():
    """A secondary worker with a deeply flexed trunk gets HIGH + top_issue —
    the station view must not hide a bad posture just because the person is
    not the primary."""
    bad = _make_pose(neck_y=0.72, trunk_y=0.55)  # trunk flexed ~ far from hips? -> high
    # Force a clearly flexed trunk: neck well below shoulders while hips stay high.
    pose = _make_pose()
    pose[11].y = 0.75  # left shoulder pushed down
    pose[12].y = 0.75  # right shoulder pushed down
    pose[23].y = 0.60  # left hip
    pose[24].y = 0.60  # right hip
    risks = compute_person_risks([_make_pose(), pose], 640, 480, primary_index=0, primary_risk_level="LOW")
    assert risks[1]["risk_level"] in ("MEDIUM", "HIGH")
    assert risks[1]["top_issue"]  # some feature exceeded a threshold


def test_primary_overrides_threshold_score():
    """Even if the primary's raw threshold score would be LOW, the station
    entry must carry the authoritative engine risk (here CRITICAL)."""
    risks = compute_person_risks(
        [_make_pose()], 640, 480, primary_index=0, primary_risk_level="CRITICAL"
    )
    assert risks[0]["risk_level"] == "CRITICAL"
    assert risks[0]["is_primary"] is True


def test_keypoint_visibility_averaged():
    pose = _make_pose(vis=0.5)
    pose[0].visibility = 1.0
    risks = compute_person_risks([pose], 640, 480, primary_index=0, primary_risk_level="LOW")
    v = risks[0]["keypoint_visibility"]
    assert 0.0 < v <= 1.0
    # 32 landmarks at 0.5 + one at 1.0 -> mean slightly above 0.5.
    assert v > 0.5


def test_empty_input_yields_empty_list():
    assert compute_person_risks([], 640, 480, 0, "LOW") == []
