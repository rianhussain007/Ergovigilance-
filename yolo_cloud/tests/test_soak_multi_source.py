"""Multi-source VideoFeeder + --videos wiring for the TRL-6 demo run.

The TRL-6 relevant-environment run feeds N *different* files (crowd CCTV +
worker clips) — one decode position per camera. These tests pin:
  * ``--videos`` parsing and its precedence over ``--video``/``--streams``
  * one opened capture per listed file, with independent decode positions
  * a missing file fails loudly at construction (not silently mid-run)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "soak_cloud.py"
_spec = importlib.util.spec_from_file_location("soak_cloud_under_test", _SCRIPT)
soak = importlib.util.module_from_spec(_spec)
sys.modules["soak_cloud_under_test"] = soak
_spec.loader.exec_module(soak)


def _write_clip(path: Path, size: tuple[int, int], frames: int = 8) -> Path:
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, size)
    assert w.isOpened(), f"cannot open writer for {path}"
    for i in range(frames):
        img = np.full((size[1], size[0], 3), 40 + i * 10, dtype=np.uint8)
        w.write(img)
    w.release()
    return path


def test_videos_flag_sets_stream_count(tmp_path):
    args = soak.parse_args(["--videos", "a.mp4", "b.mp4", "c.mp4"])
    assert args.videos == ["a.mp4", "b.mp4", "c.mp4"]
    assert args.streams == 4  # default untouched; only consulted without --videos


def test_single_video_default_unchanged():
    args = soak.parse_args([])
    assert args.videos is None
    assert args.streams == 4
    assert args.video.endswith("cardboard_manipulation_station01_worker041.mp4")


def test_feeder_one_capture_per_source(tmp_path):
    a = _write_clip(tmp_path / "cam_a.mp4", (64, 48))
    b = _write_clip(tmp_path / "cam_b.mp4", (96, 72))
    feeder = soak.VideoFeeder([str(a), str(b)])
    assert len(feeder.caps) == 2
    assert feeder.paths == [str(a), str(b)]
    # Independent positions: reading stream 0 repeatedly must not advance 1.
    for _ in range(4):
        frame_a = feeder.frame(0)
    frame_b = feeder.frame(1)
    assert frame_a is not None and frame_a.shape[:2] == (48, 64)
    assert frame_b is not None and frame_b.shape[:2] == (72, 96)


def test_feeder_loops_on_end(tmp_path):
    a = _write_clip(tmp_path / "loop.mp4", (64, 48), frames=6)
    feeder = soak.VideoFeeder([str(a)])
    for _ in range(20):  # 6-frame clip read 20x must wrap, not die
        assert feeder.frame(0) is not None


def test_missing_file_raises_at_construction(tmp_path):
    good = _write_clip(tmp_path / "ok.mp4", (64, 48))
    with pytest.raises(RuntimeError, match="cannot open video"):
        soak.VideoFeeder([str(good), str(tmp_path / "missing.mp4")])


def test_bind_spec_parsing():
    pending = soak.parse_bind_specs(["soak-3:1=W-001", "soak-1:4=W-002"])
    assert pending == {("soak-3", 1): "W-001", ("soak-1", 4): "W-002"}
    assert soak.parse_bind_specs(None) == {}
    assert soak.parse_bind_specs([]) == {}


def test_bind_spec_wildcard_track():
    pending = soak.parse_bind_specs(["soak-3:*=W-001", "soak-4:2=W-002"])
    assert pending[("soak-3", "*")] == "W-001"
    assert pending[("soak-4", 2)] == "W-002"
    assert isinstance(next(k for k in pending if k[1] != "*")[1], int)


def test_bind_spec_bad_shape_exits():
    with pytest.raises(SystemExit, match="CAM:TRACK=WORKER"):
        soak.parse_bind_specs(["not-a-bind"])


def test_bind_and_persons_flags_parse():
    args = soak.parse_args(["--bind", "soak-3:1=W-001", "--persons-every", "10"])
    assert args.bind == ["soak-3:1=W-001"]
    assert args.persons_every == 10.0
