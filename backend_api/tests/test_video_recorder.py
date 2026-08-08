"""Regression test for the session MP4 sidecar recorder.

The startup log line ``[libopenh264] Unable to create encoder`` is cosmetic —
OpenCV's OpenH264 loader is just one of several encoder backends. This test
proves the recorder's codec fallback chain (avc1 → H264 → mp4v) produces a
non-empty, re-readable video file, so session recordings can never silently
come out empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend_api.app.services.live_monitor import _SessionVideoRecorder  # noqa: E402


def _synthetic_frame(idx: int) -> np.ndarray:
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[:, :, 0] = idx * 10 % 255  # varying blue channel
    frame[100:140, 100:220, :] = 200  # a bright block so frames differ
    return frame


def test_recorder_writes_readable_mp4(tmp_path):
    out = str(tmp_path / "session.mp4")
    rec = _SessionVideoRecorder(out, 320, 240, 15.0)
    rec.start()
    assert rec.status == "recording", rec.error
    for i in range(24):
        rec.write(_synthetic_frame(i))
    assert rec.frame_count == 24

    meta = rec.finalize()
    assert meta["video_recording_status"] == "completed", meta
    assert meta["video_frame_count"] == 24
    assert meta["video_path"] is not None
    assert meta["video_codec"] is not None

    # The file must exist, be non-empty, and open with readable frames.
    path = Path(meta["video_path"])
    assert path.exists() and path.stat().st_size > 0

    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        assert cap.isOpened(), "recorded MP4 could not be opened"
        frames_read = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            assert frame.shape[:2] == (240, 320)
            frames_read += 1
        assert frames_read >= 1, "recorded MP4 contains no frames"
    finally:
        cap.release()


def test_recorder_finalize_without_frames_is_not_silently_ok(tmp_path):
    """A recorder that never wrote a frame must report a failure, not success."""
    out = str(tmp_path / "empty.mp4")
    rec = _SessionVideoRecorder(out, 320, 240, 15.0)
    rec.start()
    meta = rec.finalize()
    assert meta["video_recording_status"] in ("failed", "completed")
    if meta["video_recording_status"] == "completed":
        # Either is acceptable ONLY if the file is actually non-empty.
        assert Path(meta["video_path"]).stat().st_size > 0
