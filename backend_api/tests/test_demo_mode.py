"""Demo-mode camera resolution: camera_id="demo" resolves to DEMO_VIDEO_PATH,
and a camera_id naming an existing video file is used as-is — so a recorded
session can be replayed through the live pipeline with no camera hardware.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.live_monitor as lm  # noqa: E402


def test_demo_id_resolves_to_env_path(monkeypatch, tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"not a real video, resolver only checks isfile")
    monkeypatch.setenv("DEMO_VIDEO_PATH", str(video))
    assert lm._resolve_camera_source(0, "demo") == str(video)


def test_demo_id_without_env_falls_back_to_token():
    import os as _os
    old = _os.environ.get("DEMO_VIDEO_PATH")
    _os.environ.pop("DEMO_VIDEO_PATH", None)
    try:
        assert lm._resolve_camera_source(0, "demo") == "demo"
    finally:
        if old is not None:
            _os.environ["DEMO_VIDEO_PATH"] = old


def test_existing_video_file_used_as_is(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x" * 4)
    assert lm._resolve_camera_source(2, str(video)) == str(video)


def test_missing_file_path_falls_through_to_index(tmp_path):
    missing = str(tmp_path / "nope.mp4")
    assert lm._resolve_camera_source(3, missing) == 3


def test_numeric_and_url_unchanged():
    assert lm._resolve_camera_source(1, "2") == 2
    assert lm._resolve_camera_source(1, "rtsp://cam.example/stream") == "rtsp://cam.example/stream"
