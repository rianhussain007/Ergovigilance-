"""RTSP Stream Manager — reads RTSP camera feeds via FFmpeg.

Each camera is a subprocess running FFmpeg that decodes the RTSP stream
to raw BGR frames piped to stdout. The manager handles:
- Automatic reconnection with exponential backoff
- Frame dropping when the consumer is slow
- Health monitoring per camera
- Graceful shutdown
"""

import io
import logging
import os
import subprocess
import struct
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np

from yolo_cloud.config import settings

logger = logging.getLogger(__name__)


# --- Windows orphan reaping -------------------------------------------------
# A hard-killed cloud core (Task Manager kill, crash, dev-tool restart) used
# to leave its ffmpeg decoders running: after the 2026-09-27 restart five
# stale rawvideo readers were still chewing CPU and starved a live camera's
# reader down to a frozen 0.227 fps. On Windows a Job Object with
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE makes the OS reap every assigned child
# the moment our process dies, with no cooperation from the core itself.
# POSIX needs none of this (orphans are reparented and _kill_process covers
# the normal path), so the helper is an explicit no-op off Windows.
_JOB_HANDLE = None  # kept open for the whole process lifetime
_KERNEL32 = None
_JOB_LOCK = threading.Lock()
_JOB_UNSUPPORTED = False

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


def _create_kill_on_close_job():
    """Create a Windows Job Object that kills its members when closed."""
    import ctypes
    from ctypes import wintypes

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    global _KERNEL32
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")

    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        ctypes.c_void_p(handle),
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        err = ctypes.get_last_error()
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        raise OSError(err, "SetInformationJobObject failed")

    _KERNEL32 = kernel32
    return handle


def _assign_to_kill_on_close_job(proc: subprocess.Popen) -> bool:
    """Tie *proc* to a kill-on-close Job Object (Windows only).

    Returns True once the child is guaranteed to die with this process,
    False when the platform does not need (or the job does not allow)
    that guarantee. Never raises: a failure here must not stop a camera
    from starting, so any error is logged and reported as unsupported.
    """
    global _JOB_HANDLE, _JOB_UNSUPPORTED
    if os.name != "nt" or _JOB_UNSUPPORTED:
        return False
    try:
        import ctypes

        with _JOB_LOCK:
            if _JOB_HANDLE is None:
                _JOB_HANDLE = _create_kill_on_close_job()
            job = _JOB_HANDLE
        kernel32 = _KERNEL32
        raw_handle = getattr(proc, "_handle", None)
        if raw_handle is None:
            raise AttributeError("Popen has no native _handle")
        if not kernel32.AssignProcessToJobObject(
            ctypes.c_void_p(job), ctypes.c_void_p(int(raw_handle))
        ):
            raise OSError(
                ctypes.get_last_error(), "AssignProcessToJobObject failed"
            )
        return True
    except Exception as exc:
        # Older shells/CI run the core inside a non-nestable job; that is
        # not fatal, it just means the OS will not reap for us.
        logger.debug(
            "kill-on-close job unavailable for PID %s: %s",
            getattr(proc, "pid", "?"),
            exc,
        )
        _JOB_UNSUPPORTED = os.name == "nt" and _JOB_HANDLE is None
        return False


class CameraState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class CameraInfo:
    id: str
    name: str
    url: str
    state: CameraState = CameraState.DISCONNECTED
    fps: float = 0.0
    resolution: tuple[int, int] = (0, 0)
    last_frame_time: float = 0.0
    # Monotonic companion to ``last_frame_time`` for the stall watchdog.
    # The watchdog used to compare wall-clock stamps, so an NTP step or a
    # sleep/resume made a healthy decoder look 15 s stale and get killed
    # (seen 2026-09-28: a stall restart fired while decoded frames were
    # demonstrably still arriving). Wall-clock stays for display/lag math
    # (ingestion computes frame lag from ``last_frame_time``); staleness is
    # measured with this one.
    last_frame_mono: float = 0.0
    frame_count: int = 0
    error_count: int = 0
    last_error: str = ""
    pid: Optional[int] = None
    # Mirrors RTSPStream._reconnect_count so API/UI consumers (camera cards,
    # the "Reconnecting (n)" hint) can report how hard the stream is trying
    # without reaching into the stream object.
    reconnect_attempts: int = 0


class RTSPStream:
    """Manages a single RTSP camera stream via FFmpeg subprocess.

    FFmpeg decodes the RTSP stream to raw BGR24 frames piped to stdout.
    The reader thread decodes the raw frames and stores the latest one
    in a ring buffer for the consumer.
    """

    # BGR24: 3 bytes per pixel
    HEADER_SIZE = 12  # width(4) + height(4) + format(4)
    PIXEL_FORMAT = "bgr24"
    # A STREAMING camera that decodes nothing for this long is stalled,
    # not streaming (observed 2026-09-27: a decoder wedged mid-session
    # kept state=streaming with a frozen fps for 20+ minutes while the
    # ingestion loop re-scored one stale frame). The watchdog kills the
    # child, which drives the normal EOF→reconnect path.
    #
    # Calibration (2026-09-28): on a CPU-saturated box a healthy H.264
    # stream still showed real ~15 s gaps in decoded frames roughly every
    # 50 s (the watchdog log recorded age=15.3 s with decoded=892). At 15 s
    # that meant three needless decoder restarts in 150 s — each one
    # resetting reconnect counters and flickering the camera card. The
    # threshold now sits above the observed hiccup, so a real wedge is
    # still caught inside 30 s (the failure this guards against lasted
    # 20+ minutes) without tearing down a decoder that is merely starved.
    STALL_TIMEOUT_S = 30.0

    def __init__(self, camera: CameraInfo):
        self.camera = camera
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stderr_tail = ""
        self._probe_reason = ""
        self._stall_restart = False
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._reconnect_count = 0
        self._frame_width = 0
        self._frame_height = 0
        self._bytes_per_frame = 0
        # Set by stop(), cleared by start(): lets the reader leave a
        # reconnect backoff or an in-flight probe immediately instead of
        # making stop()/DELETE wait out a 30 s sleep or a 10 s ffprobe.
        self._stop_event = threading.Event()

    @property
    def is_streaming(self) -> bool:
        return self.camera.state == CameraState.STREAMING

    def start(self) -> None:
        """Start the RTSP stream reader."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._reconnect_count = 0
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name=f"rtsp-{self.camera.id}"
        )
        self._reader_thread.start()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name=f"rtsp-watchdog-{self.camera.id}",
        )
        self._watchdog_thread.start()
        logger.info("RTSP stream started for camera %s", self.camera.id)

    def stop(self) -> None:
        """Stop the RTSP stream reader and kill FFmpeg.

        Always bounded: signal the child first (see ``_kill_process``),
        then collect the reader with a timeout. The pipes are never
        closed from this thread — that was the deadlock (see
        ``_kill_process``); the reader hits EOF on its own once the
        child's write end is gone.
        """
        self._running = False
        self._stop_event.set()
        self._kill_process()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=5)
            if self._reader_thread.is_alive():
                logger.warning(
                    "Camera %s: reader thread did not exit within 5 s of kill",
                    self.camera.id,
                )
        self.camera.state = CameraState.DISCONNECTED
        logger.info("RTSP stream stopped for camera %s", self.camera.id)

    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest decoded frame (non-blocking)."""
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return None

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        """Continuously drain ffmpeg's stderr, keeping the last lines.

        Two jobs: a full stderr PIPE would block ffmpeg mid-stream, and
        the tail is what turns "exited with code N" into the actual
        reason ("Server returned 403 Forbidden", DNS failure, …) once
        the child dies. Never closes the pipe — teardown belongs to the
        child (see ``_kill_process``); the read simply hits EOF.
        """
        tail = ""
        try:
            if proc.stderr is not None:
                for line in iter(proc.stderr.readline, b""):
                    tail = (tail + line.decode("utf-8", errors="replace"))[-1000:]
        except Exception:
            logger.debug(
                "Camera %s: stderr drain ended", self.camera.id, exc_info=True
            )
        self._stderr_tail = tail

    def _reader_loop(self) -> None:
        """Main reader loop — starts FFmpeg, reads frames, handles reconnect."""
        while self._running:
            if self._reconnect_count >= settings.RTSP_MAX_RECONNECT:
                self.camera.state = CameraState.ERROR
                self.camera.last_error = (
                    f"Exceeded max reconnection attempts ({settings.RTSP_MAX_RECONNECT})"
                )
                logger.error(
                    "Camera %s: max reconnection attempts reached", self.camera.id
                )
                break

            self.camera.state = (
                CameraState.RECONNECTING
                if self._reconnect_count > 0
                else CameraState.CONNECTING
            )

            try:
                self._start_ffmpeg()
                self._read_frames()
            except Exception as exc:
                if self._stall_restart:
                    self._stall_restart = False
                    self.camera.last_error = (
                        f"Stream stalled — no decoded frames for "
                        f"{int(self.STALL_TIMEOUT_S)}s, reconnecting"
                    )
                else:
                    self.camera.last_error = str(exc)
                self.camera.error_count += 1
                logger.warning(
                    "Camera %s stream error: %s (reconnect %d/%d)",
                    self.camera.id,
                    exc,
                    self._reconnect_count + 1,
                    settings.RTSP_MAX_RECONNECT,
                )

            self._kill_process()

            if self._running:
                self._reconnect_count += 1
                self.camera.reconnect_attempts = self._reconnect_count
                delay = min(
                    settings.RTSP_RECONNECT_DELAY * (2 ** min(self._reconnect_count - 1, 5)),
                    30.0,
                )
                logger.info(
                    "Camera %s: reconnecting in %.1fs", self.camera.id, delay
                )
                if self._stop_event.wait(delay):
                    break  # stop() requested during the backoff

    def _watchdog_tick(self) -> None:
        """Kill a decoder that stopped delivering frames while STREAMING.

        The reader thread is blocked inside ``proc.stdout.read()`` and
        can never notice the silence itself; killing the child is all it
        takes — the reader gets EOF and runs the normal reconnect path.
        The stall reason is recorded so the reconnect surfaces "stalled"
        instead of a bare exit code.
        """
        if not self._running or self.camera.state != CameraState.STREAMING:
            return
        mono = self.camera.last_frame_mono
        if mono:
            age = time.monotonic() - mono
        else:
            # Streams built by hand (tests, restored state) only carry the
            # wall-clock stamp; fall back to it rather than never watching.
            last = self.camera.last_frame_time
            if not last:
                return
            age = time.time() - last
        if age >= self.STALL_TIMEOUT_S:
            logger.warning(
                "Camera %s: no decoded frame for %.1fs while streaming "
                "(decoded=%d, pid=%s) — restarting decoder",
                self.camera.id,
                age,
                self.camera.frame_count,
                self.camera.pid,
            )
            self._stall_restart = True
            self._kill_process()

    def _watchdog_loop(self) -> None:
        while self._running:
            try:
                self._watchdog_tick()
            except Exception:
                logger.debug(
                    "Camera %s: watchdog tick failed", self.camera.id, exc_info=True
                )
            if self._stop_event.wait(2.0):
                break

    @staticmethod
    def _input_url_options(url: str) -> list:
        """Per-scheme input options for ffmpeg/ffprobe.

        ffmpeg 9 rejects a pre-input ``-rtsp_transport`` for any non-RTSP
        source ("Option rtsp_transport not found" -> instant exit before
        opening the file), so the flag is only passed for rtsp:// URLs.
        File and tcp:// sources are unaffected and need no options.

        Bounded connects: without ``-timeout`` an unreachable host hangs
        ffmpeg in TCP connect for 120 s+ (measured on 10.255.255.1),
        stalling every reconnect cycle and starving the box when cameras
        die. 10 s in microseconds, matching the ffprobe timeout.

        ``-stimeout`` is deliberately absent: ffmpeg 8+ removed it from
        the RTSP demuxer, and this host's 9.0 build aborted with
        "Failed to set value '10000000' for option 'stimeout': Option not
        found" before opening the stream, so every RTSP camera failed to
        start (2026-09-27). ``-timeout`` is the supported spelling —
        socket I/O timeout in microseconds — and still bounds the initial
        connect.
        """
        if url.lower().startswith(("rtsp://", "rtsps://")):
            return [
                "-rtsp_transport", settings.RTSP_TRANSPORT,
                "-timeout", "10000000",
            ]
        return []

    def _start_ffmpeg(self) -> None:
        """Launch FFmpeg to decode the RTSP stream."""
        url = self.camera.url

        # FFmpeg command: decode RTSP to raw BGR24 frames on stdout.
        #
        # ``-v error`` (was ``quiet``): with quiet, a dead stream surfaced
        # as "FFmpeg exited with code 12345:" with no reason at all — the
        # 403/DNS/timeout text the operator needs was swallowed (found
        # 2026-09-27). Error-level lines are tiny and are consumed by the
        # stderr drain thread below, so the PIPE can never fill.
        cmd = [
            "ffmpeg",
            *self._input_url_options(url),
            "-i", url,
            "-tune", "zerolatency",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-f", "rawvideo",
            "-pix_fmt", self.PIXEL_FORMAT,
            "-v", "error",
            "-",
        ]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8,  # 100MB buffer
        )
        self.camera.pid = self._process.pid
        # Windows: make the OS reap this decoder if the core is hard-killed.
        _assign_to_kill_on_close_job(self._process)
        self._stderr_tail = ""
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(self._process,),
            daemon=True,
            name=f"rtsp-stderr-{self.camera.id}",
        )
        self._stderr_thread.start()
        logger.info(
            "FFmpeg started for camera %s (PID %d)", self.camera.id, self._process.pid
        )

    def _read_frames(self) -> None:
        """Read raw BGR frames from FFmpeg stdout."""
        proc = self._process
        if proc is None or proc.stdout is None:
            return

        # First, extract resolution from the stream using FFprobe. A failed
        # probe keeps the 640x480 fallback for the byte math, but it is NOT
        # proof of a live stream — see the first-frame transition below.
        probed = self._probe_resolution()
        if not self._running:
            return  # stop() raced the probe; no point starting ffmpeg
        if not probed:
            self.camera.last_error = (
                "Resolution probe failed — assuming 640x480: "
                + (self._probe_reason or "ffprobe could not read the stream")
            )

        if self._frame_width <= 0 or self._frame_height <= 0:
            raise RuntimeError(
                f"Could not determine stream resolution for {self.camera.id}"
            )

        self._bytes_per_frame = self._frame_width * self._frame_height * 3
        self.camera.resolution = (self._frame_width, self._frame_height)

        # Read exactly bytes_per_frame bytes at a time
        raw_bytes = b""
        fps_counter_start = time.perf_counter()
        fps_frame_count = 0
        # STREAMING is claimed only once a real frame has been decoded. It used
        # to be set straight after the (fallback-tolerant) probe, so four dead
        # public cameras showed as "streaming" in the UI with fps=0 and no
        # frames (found 2026-09-27). Until then the state stays CONNECTING and
        # the reason ends up in last_error.
        first_frame = True

        while self._running:
            chunk = proc.stdout.read(min(65536, self._bytes_per_frame))
            if not chunk:
                break  # Stream ended

            raw_bytes += chunk

            if len(raw_bytes) >= self._bytes_per_frame:
                frame_data = raw_bytes[: self._bytes_per_frame]
                raw_bytes = raw_bytes[self._bytes_per_frame :]

                try:
                    frame = np.frombuffer(frame_data, dtype=np.uint8).reshape(
                        self._frame_height, self._frame_width, 3
                    )
                    with self._lock:
                        self._latest_frame = frame
                    if first_frame:
                        first_frame = False
                        self.camera.state = CameraState.STREAMING
                        self.camera.last_error = ""
                        self._stall_restart = False
                        self._reconnect_count = 0
                        self.camera.reconnect_attempts = 0
                        logger.info(
                            "Camera %s: streaming at %dx%d",
                            self.camera.id,
                            self._frame_width,
                            self._frame_height,
                        )
                    self.camera.frame_count += 1
                    self.camera.last_frame_time = time.time()
                    self.camera.last_frame_mono = time.monotonic()

                    # FPS calculation
                    fps_frame_count += 1
                    elapsed = time.perf_counter() - fps_counter_start
                    if elapsed >= 2.0:
                        self.camera.fps = fps_frame_count / elapsed
                        fps_counter_start = time.perf_counter()
                        fps_frame_count = 0

                except ValueError:
                    # Corrupted frame — skip
                    logger.debug("Camera %s: corrupted frame skipped", self.camera.id)

        # Process ended
        if self._running:
            ret = proc.wait()
            if ret != 0:
                # Prefer the drained tail: it is populated even when the
                # child already exited (a direct read can return empty).
                # The drain thread hits EOF right after the child dies —
                # give it a moment so the final error lines make it in.
                if self._stderr_thread is not None:
                    self._stderr_thread.join(timeout=1)
                stderr = self._stderr_tail
                if not stderr and proc.stderr:
                    try:
                        stderr = proc.stderr.read().decode(
                            "utf-8", errors="replace"
                        )
                    except Exception:
                        stderr = ""
                raise RuntimeError(
                    f"FFmpeg exited with code {ret}: {stderr.strip()[:300]}"
                )

    def _probe_resolution(self) -> bool:
        """Probe the RTSP stream for resolution using ffprobe.

        Returns True when ffprobe reported a real resolution, False when the
        640x480 fallback was used. Callers must not treat a fallback as
        evidence of a live stream.
        """
        try:
            cmd = [
                "ffprobe",
                *self._input_url_options(self.camera.url),
                "-i", self.camera.url,
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-v", "error",
                "-of", "json",
            ]
            result_probe = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            _assign_to_kill_on_close_job(result_probe)
            # Cancellable wait: stop()/remove must not sit behind a full
            # 10 s probe (DELETE of a dead camera blew a 10 s client
            # timeout on 2026-09-27 while the reader was parked here).
            deadline = time.monotonic() + 10
            while result_probe.poll() is None and time.monotonic() < deadline:
                if self._stop_event.wait(0.1):
                    break
            if result_probe.poll() is None:
                # Still running: kill it and never block on its pipes.
                reason = (
                    "probe aborted (stream stopping)"
                    if self._stop_event.is_set()
                    else "ffprobe timed out after 10s"
                )
                try:
                    result_probe.kill()
                except Exception:
                    pass
                try:
                    _out, err = result_probe.communicate(timeout=3)
                except Exception:
                    err = ""
                detail = (err or "").strip()
                self._probe_reason = (
                    detail.splitlines()[-1] if detail else reason
                )
                logger.warning(
                    "Camera %s: %s, assuming 640x480",
                    self.camera.id,
                    self._probe_reason,
                )
                self._frame_width = 640
                self._frame_height = 480
                return False
            probe_out, probe_err = result_probe.communicate()
            if result_probe.returncode == 0:
                import json
                data = json.loads(probe_out or "{}")
                stream = data.get("streams", [{}])[0]
                self._frame_width = int(stream.get("width", 0))
                self._frame_height = int(stream.get("height", 0))
                if self._frame_width > 0 and self._frame_height > 0:
                    return True
                self._probe_reason = "ffprobe reported no video size"
                logger.warning(
                    "Camera %s: ffprobe reported no video size, assuming 640x480",
                    self.camera.id,
                )
            else:
                # Keep the real reason (403 / DNS / timeout) for last_error
                err = (probe_err or "").strip()
                self._probe_reason = (
                    err.splitlines()[-1] if err else f"ffprobe exit {result_probe.returncode}"
                )
                logger.warning(
                    "Camera %s: ffprobe failed (%s), assuming 640x480",
                    self.camera.id,
                    self._probe_reason,
                )
        except Exception as exc:
            self._probe_reason = str(exc)
            logger.warning(
                "Camera %s: resolution probe failed (%s), assuming 640x480",
                self.camera.id,
                exc,
            )
        self._frame_width = 640
        self._frame_height = 480
        return False

    def _kill_process(self) -> None:
        """Kill the FFmpeg subprocess without blocking on its pipes.

        Regression (2026-09-27, wedged cloud core): this used to close
        stdout/stderr *before* killing. With the reader thread parked in
        ``proc.stdout.read()`` — camera silent, ffmpeg still alive — the
        buffered reader held its internal lock, so the cross-thread
        ``close()`` waited on that lock forever: ffmpeg was never
        killed, the ``async def`` stop endpoint blocked the event loop,
        and every route (even /api/cloud/health) timed out until the
        process was restarted by hand.

        Order is therefore: terminate, then reap with a bounded wait.
        Pipe teardown is deliberately left to the reader thread, whose
        pending read returns EOF as soon as the child's write end is
        gone. ``terminate()`` is SIGTERM on POSIX and a hard kill on
        Windows, so the child cannot outlive this call.
        """
        proc = self._process
        if proc is None:
            return
        self._process = None
        self.camera.pid = None
        try:
            proc.terminate()
        except Exception:
            logger.debug("Camera %s: terminate failed", self.camera.id, exc_info=True)
        for _ in range(2):
            try:
                proc.wait(timeout=3)
                return
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
            except Exception:
                return
        logger.warning(
            "Camera %s: ffmpeg (PID %s) survived terminate + kill",
            self.camera.id,
            proc.pid,
        )


class RTSPManager:
    """Manages multiple RTSP camera streams."""

    def __init__(self):
        self._streams: dict[str, RTSPStream] = {}
        self._lock = threading.Lock()

    def add_camera(
        self, camera_id: str, name: str, url: str, auto_start: bool = True
    ) -> CameraInfo:
        """Add a new camera and optionally start streaming."""
        with self._lock:
            if camera_id in self._streams:
                # Update existing
                self._streams[camera_id].stop()
                self._streams[camera_id].camera.name = name
                self._streams[camera_id].camera.url = url
            else:
                camera = CameraInfo(id=camera_id, name=name, url=url)
                self._streams[camera_id] = RTSPStream(camera)

            camera = self._streams[camera_id].camera
            if auto_start:
                self._streams[camera_id].start()

            logger.info("Camera added: %s (%s)", camera_id, name)
            return camera

    def remove_camera(self, camera_id: str) -> bool:
        """Remove and stop a camera."""
        with self._lock:
            stream = self._streams.pop(camera_id, None)
            if stream:
                stream.stop()
                logger.info("Camera removed: %s", camera_id)
                return True
            return False

    def start_camera(self, camera_id: str) -> bool:
        """Start streaming a camera."""
        with self._lock:
            stream = self._streams.get(camera_id)
            if stream:
                stream.start()
                return True
            return False

    def stop_camera(self, camera_id: str) -> bool:
        """Stop streaming a camera."""
        with self._lock:
            stream = self._streams.get(camera_id)
            if stream:
                stream.stop()
                return True
            return False

    def get_frame(self, camera_id: str) -> Optional[np.ndarray]:
        """Get the latest frame from a camera."""
        stream = self._streams.get(camera_id)
        if stream:
            return stream.get_frame()
        return None

    def get_all_cameras(self) -> list[CameraInfo]:
        """Get info on all cameras."""
        with self._lock:
            return [s.camera for s in self._streams.values()]

    def get_camera(self, camera_id: str) -> Optional[CameraInfo]:
        """Get info on a specific camera."""
        with self._lock:
            stream = self._streams.get(camera_id)
            return stream.camera if stream else None

    def stop_all(self) -> None:
        """Stop all camera streams."""
        with self._lock:
            for stream in self._streams.values():
                stream.stop()
        logger.info("All camera streams stopped")


# Global singleton
_manager: Optional[RTSPManager] = None


def get_rtsp_manager() -> RTSPManager:
    global _manager
    if _manager is None:
        _manager = RTSPManager()
    return _manager
