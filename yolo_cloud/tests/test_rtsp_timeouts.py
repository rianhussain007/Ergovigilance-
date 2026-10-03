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

import io
import os
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


def test_ffmpeg_logs_errors_so_reason_is_not_swallowed():
    """FFmpeg must run at error loglevel, never quiet.

    Regression for 2026-09-27: ``-v quiet`` silenced ffmpeg entirely, so
    a dead camera surfaced as "FFmpeg exited with code 3436169992:"
    with an empty reason — the 403/DNS/timeout text the operator needs
    was thrown away.
    """
    captured: dict = {}

    class FakeProc:
        pid = 4242
        stderr = None
        stdout = None

    import yolo_cloud.rtsp_manager as rm

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProc()

    stream = RTSPStream(
        CameraInfo(id="loglvl-qa", name="l", url="rtsp://127.0.0.1:1/x")
    )
    original = rm.subprocess.Popen
    rm.subprocess.Popen = fake_popen
    try:
        stream._start_ffmpeg()
    finally:
        rm.subprocess.Popen = original
    cmd = captured["cmd"]
    assert "quiet" not in cmd, cmd
    assert cmd[cmd.index("-v") + 1] == "error", cmd


def test_stderr_drain_keeps_short_reason_tail():
    """The drain thread keeps the tail of stderr for last_error."""
    stream = RTSPStream(
        CameraInfo(id="drain-qa", name="d", url="rtsp://127.0.0.1:1/x")
    )

    class FakeProc:
        stderr = io.BytesIO(
            b"noise\n" + b"x" * 3000 + b"\nServer returned 403 Forbidden (access denied)\n"
        )

    stream._drain_stderr(FakeProc())
    assert "403 Forbidden" in stream._stderr_tail
    assert len(stream._stderr_tail) <= 1000


def test_dead_source_reports_a_nonempty_reason():
    """A dead camera must expose a human-readable failure reason.

    The UI shows ``last_error`` verbatim; an empty string after the
    colon (the old ``-v quiet`` behaviour) tells the operator nothing
    about 403 vs DNS vs timeout.
    """
    mgr = RTSPManager()
    mgr.add_camera("reason-qa", "dead", "rtsp://127.0.0.1:1/stream", auto_start=True)
    try:
        last = None
        # probe (10 s bound) + ffmpeg start/exit must complete first;
        # on this host even a closed local port can eat the full probe
        # timeout, so allow generous headroom.
        deadline = time.monotonic() + 16
        while time.monotonic() < deadline:
            cam = mgr.get_camera("reason-qa")
            if cam is not None and cam.last_error:
                last = cam.last_error
                break
            time.sleep(0.2)
        assert last, "dead camera never recorded a reason"
        assert not last.rstrip().endswith(":"), f"empty reason: {last!r}"
        # something actionable beyond the raw exit code
        tail = last.split(":", 1)[-1].strip()
        assert tail, f"reason carries no detail: {last!r}"
    finally:
        mgr.remove_camera("reason-qa")


def test_remove_dead_camera_returns_quickly():
    """remove/DELETE must not wait out the reader's probe or backoff.

    Regression for 2026-09-27: deleting a dead camera took >10 s
    (client timeout, observed as curl 000) because stop() joined a
    reader parked in a 10 s ffprobe run or a 30 s reconnect sleep while
    holding the manager lock. The stop event now wakes both.
    """
    mgr = RTSPManager()
    mgr.add_camera("rmfast-qa", "dead", "rtsp://127.0.0.1:1/stream", auto_start=True)
    time.sleep(1.5)  # reader is inside the resolution probe by now
    started = time.monotonic()
    removed = mgr.remove_camera("rmfast-qa")
    elapsed = time.monotonic() - started
    assert removed
    assert elapsed < 5, f"remove_camera took {elapsed:.1f}s"


def test_watchdog_kills_a_stalled_streaming_decoder():
    """A STREAMING camera that goes silent must be restarted, not trusted.

    Regression for 2026-09-27: a decoder wedged mid-session kept
    state=streaming with a frozen fps for 20+ minutes while the
    ingestion loop re-scored one stale frame. The reader thread is
    blocked inside stdout.read() and can never notice the silence
    itself, so a watchdog kills the child to force EOF → reconnect.
    """
    stream = RTSPStream(
        CameraInfo(id="stall-qa", name="s", url="rtsp://127.0.0.1:1/x")
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream._process = proc
    stream.camera.pid = proc.pid
    stream._running = True
    try:
        # Fresh frame: the watchdog leaves a healthy decoder alone.
        stream.camera.state = CameraState.STREAMING
        stream.camera.last_frame_time = time.time()
        stream._watchdog_tick()
        assert proc.poll() is None, "watchdog killed a healthy decoder"

        # Silent past the stall timeout: decoder is killed and the stall
        # reason is recorded for the reconnect path.
        stream.camera.last_frame_mono = time.monotonic() - 60
        stream._watchdog_tick()
        deadline = time.monotonic() + 8
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert proc.poll() is not None, "watchdog left a stalled decoder alive"
        assert stream._stall_restart, "stall reason was not recorded"
    finally:
        stream._running = False
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_watchdog_ignores_a_wall_clock_jump():
    """A healthy decoder must survive a clock step.

    The staleness check originally used ``time.time()`` on both ends, so
    an NTP step (or a sleep/resume) could make a decoder that is actively
    delivering frames look 15 s stale. Observed 2026-09-28: a stall
    restart fired while the list endpoint showed decoded frames still
    climbing at ~6 fps. Staleness is monotonic now; only the monotonic
    stamp may trigger a kill.
    """
    stream = RTSPStream(
        CameraInfo(id="clock-qa", name="c", url="rtsp://127.0.0.1:1/x")
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream._process = proc
    stream.camera.pid = proc.pid
    stream._running = True
    try:
        stream.camera.state = CameraState.STREAMING
        # Frames are arriving (fresh monotonic stamp) but the wall clock
        # claims an hour of silence — the old check killed this decoder.
        stream.camera.last_frame_time = time.time() - 3600
        stream.camera.last_frame_mono = time.monotonic()
        stream._watchdog_tick()
        assert proc.poll() is None, (
            "wall-clock skew killed a decoder that was still delivering frames"
        )
    finally:
        stream._running = False
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_watchdog_falls_back_to_wall_clock_without_a_mono_stamp():
    """Hand-built streams still get watched (no mono stamp recorded)."""
    stream = RTSPStream(
        CameraInfo(id="legacy-qa", name="l", url="rtsp://127.0.0.1:1/x")
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream._process = proc
    stream.camera.pid = proc.pid
    stream._running = True
    try:
        stream.camera.state = CameraState.STREAMING
        stream.camera.last_frame_mono = 0.0
        stream.camera.last_frame_time = time.time() - 60
        stream._watchdog_tick()
        assert stream._stall_restart, "unstamped stream was never watched"
    finally:
        stream._running = False
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_kill_on_close_job_is_a_safe_noop_when_unsupported():
    """Assigning a child must never raise and must report the truth.

    POSIX needs no Job Object (orphans are reparented); a fake Popen
    without a native handle must not blow up a camera start on Windows.
    """
    import yolo_cloud.rtsp_manager as rm

    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        if os.name != "nt":
            assert rm._assign_to_kill_on_close_job(proc) is False
            assert rm._assign_to_kill_on_close_job(object()) is False
        else:
            # No native handle -> handled, not raised.
            assert rm._assign_to_kill_on_close_job(object()) is False
            # A real child must be assignable to the kill-on-close job.
            assert rm._assign_to_kill_on_close_job(proc) is True
        assert proc.wait(timeout=10) == 0, "child was disturbed by assignment"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_kill_on_close_job_reaps_a_hard_killed_parents_child():
    """Closing the job handle must kill the assigned decoder.

    This is the whole point of the helper: when the cloud core is killed
    outright (Task Manager / crash / dev-tool restart) the OS closes our
    job handle, and every ffmpeg under it dies instead of surviving as a
    CPU-starving orphan (five of them starved a live camera's reader to a
    frozen 0.227 fps on 2026-09-27).
    """
    import yolo_cloud.rtsp_manager as rm

    if os.name != "nt":
        return  # documented no-op off Windows; asserted above

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"]
    )
    try:
        assert rm._assign_to_kill_on_close_job(child) is True
        assert child.poll() is None
        # Hand the singleton job to this test so we own closing it exactly
        # once; later cameras just build a fresh job.
        with rm._JOB_LOCK:
            job = rm._JOB_HANDLE
            rm._JOB_HANDLE = None
        import ctypes

        assert job, "no job handle was ever created"
        rm._KERNEL32.CloseHandle(ctypes.c_void_p(job))
        assert child.wait(timeout=10) is not None, (
            "child survived the job handle being closed"
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_add_camera_wires_the_job_object_helper():
    """_start_ffmpeg must actually assign the decoder to the job."""
    import yolo_cloud.rtsp_manager as rm

    seen: list = []

    class FakeProc:
        pid = 5150
        stdout = None
        stderr = None

    original_popen = rm.subprocess.Popen
    original_assign = rm._assign_to_kill_on_close_job
    rm.subprocess.Popen = lambda cmd, **kw: FakeProc()
    rm._assign_to_kill_on_close_job = lambda proc: seen.append(proc) or True
    try:
        stream = RTSPStream(
            CameraInfo(id="job-qa", name="j", url="rtsp://127.0.0.1:1/x")
        )
        stream._start_ffmpeg()
    finally:
        rm.subprocess.Popen = original_popen
        rm._assign_to_kill_on_close_job = original_assign
    proc = seen[0]
    assert proc.pid == 5150, "helper was not handed the ffmpeg process"


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
