"""RTSP connect-timeout guards (sell-readiness QA: hung-core root cause).

An unreachable host hung raw ffmpeg in TCP connect for 120 s+ (measured —
no timeout flags), stalling every reconnect cycle; orphaned ffmpeg
processes from dead parents then accumulated and starved the box until
health checks timed out. Covered here:

1. The ffmpeg/ffprobe command carries bounded-connect flags for RTSP.
2. Non-RTSP sources still get no pre-input flags (ffmpeg 9 rejects them).
3. add/get/remove on a refused host completes quickly and the manager
   stays responsive (the foreground path never blocks on the network).
"""

from __future__ import annotations

import time

from yolo_cloud.rtsp_manager import RTSPManager, RTSPStream


def test_rtsp_options_bounded_connect():
    opts = RTSPStream._input_url_options("rtsp://cam/stream")
    assert "-rtsp_transport" in opts
    assert "-timeout" in opts
    assert "-stimeout" in opts
    assert opts[opts.index("-timeout") + 1] == "10000000"


def test_non_rtsp_options_unchanged():
    assert RTSPStream._input_url_options("/data/video.mp4") == []
    assert RTSPStream._input_url_options("tcp://cam:1234") == []
    assert RTSPStream._input_url_options("rtsps://cam/stream")[0] == "-rtsp_transport"


def test_dead_host_never_blocks_manager():
    mgr = RTSPManager()
    started = time.monotonic()
    mgr.add_camera("dead-qa", "dead", "rtsp://127.0.0.1:1/stream", auto_start=True)
    mgr.get_all_cameras()
    assert mgr.remove_camera("dead-qa") is True
    elapsed = time.monotonic() - started
    assert elapsed < 60, f"manager blocked {elapsed:.1f}s on a dead host"
    assert mgr.get_all_cameras() == []
