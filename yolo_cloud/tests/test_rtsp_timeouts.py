"""RTSP connect-timeout guards (sell-readiness QA: hung-core root cause).

An unreachable host hung raw ffmpeg in TCP connect for 120 s+ (measured —
no timeout flags), stalling every reconnect cycle; orphaned ffmpeg
processes from dead parents then accumulated and starved the box until
health checks timed out. Covered here:

1. The ffmpeg/ffprobe command carries bounded-connect flags for RTSP.
2. Non-RTSP sources still get no pre-input flags (ffmpeg 9 rejects them).
3. add/get/remove on a refused host completes quickly and the manager
   stays responsive (the foreground path never blocks on the network).
4. stop()/kill never block on the child's pipes, and the camera
   endpoints stay sync so FastAPI runs them off the event loop — the
   wedged-core regression of 2026-09-27 (a silent ffmpeg + a cross-
   thread pipe close froze every route, /health included).
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time

from yolo_cloud.rtsp_manager import CameraInfo, CameraState, RTSPManager, RTSPStream


def test_rtsp_options_bounded_connect():
    opts = RTSPStream._input_url_options("rtsp://cam/stream")
    assert "-rtsp_transport" in opts
    assert "-timeout" in opts
    assert opts[opts.index("-timeout") + 1] == "10000000"


def test_rtsp_options_never_pass_removed_stimeout():
    """ffmpeg 8+ dropped ``-stimeout`` from the RTSP demuxer.

    With it in the command line the 9.0 build aborted with "Option not
    found" *before* opening the stream, so every RTSP camera failed to
    start (found 2026-09-27 while testing public streams). ``-timeout``
    is the supported spelling and must be the only bound passed.
    """
    for url in ("rtsp://cam/stream", "rtsps://cam/stream"):
        assert "-stimeout" not in RTSPStream._input_url_options(url)


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


def test_dead_source_never_reports_streaming():
    """A camera that decodes no frames must never show as streaming.

    Regression for 2026-09-27: the state moved to STREAMING immediately
    after the *fallback-tolerant* ffprobe, so four dead public cameras
    showed "streaming" in the UI with fps=0, no frames, and no error.
    """
    mgr = RTSPManager()
    mgr.add_camera("never-qa", "dead", "rtsp://127.0.0.1:1/stream", auto_start=True)
    try:
        states = set()
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            cam = mgr.get_camera("never-qa")
            if cam is not None:
                states.add(cam.state)
            time.sleep(0.2)
        assert CameraState.STREAMING not in states, states
    finally:
        mgr.remove_camera("never-qa")


def test_stop_never_blocks_on_a_silent_child():
    """stop() must not wait on a pipe lock held by a parked reader.

    Shape of the freeze: ffmpeg alive but sending nothing, the reader
    parked in ``proc.stdout.read()`` holding the buffered-reader lock,
    and ``_kill_process`` closing that same pipe from another thread —
    an unbounded wait, inside an endpoint that used to be ``async def``,
    which took every route down (health included) and left ffmpeg
    running. With the pipe close gone the stop must finish quickly and
    leave no child behind.
    """
    stream = RTSPStream(
        CameraInfo(id="silent-qa", name="silent", url="rtsp://example.invalid/x")
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream._process = proc
    stream.camera.pid = proc.pid
    reader = threading.Thread(target=proc.stdout.read, args=(65536,), daemon=True)
    reader.start()
    time.sleep(0.2)  # let the reader take the buffer lock
    try:
        done = threading.Event()
        stopper = threading.Thread(
            target=lambda: (stream.stop(), done.set()), daemon=True
        )
        stopper.start()
        assert done.wait(10), "stop() deadlocked on a silent ffmpeg child"
        assert proc.poll() is not None, "ffmpeg child survived stop()"
        assert stream._process is None
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_camera_endpoints_stay_sync():
    """Camera handlers must stay plain ``def`` (FastAPI threadpool).

    Async handlers run on the event loop; one blocked ffmpeg kill then
    freezes every route in the process (2026-09-27). Pinned so a later
    ``async def`` refactor cannot silently reintroduce it.
    """
    import inspect

    import yolo_cloud.api as api

    for name in (
        "list_cameras",
        "add_camera",
        "remove_camera",
        "probe_camera",
        "get_camera",
        "camera_snapshot",
        "start_camera",
        "stop_camera",
    ):
        assert not inspect.iscoroutinefunction(getattr(api, name)), (
            f"{name} must stay sync so FastAPI runs it in the threadpool; "
            f"blocking work on the event loop freezes the whole cloud core"
        )
