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
import signal
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
    frame_count: int = 0
    error_count: int = 0
    last_error: str = ""
    pid: Optional[int] = None


class RTSPStream:
    """Manages a single RTSP camera stream via FFmpeg subprocess.

    FFmpeg decodes the RTSP stream to raw BGR24 frames piped to stdout.
    The reader thread decodes the raw frames and stores the latest one
    in a ring buffer for the consumer.
    """

    # BGR24: 3 bytes per pixel
    HEADER_SIZE = 12  # width(4) + height(4) + format(4)
    PIXEL_FORMAT = "bgr24"

    def __init__(self, camera: CameraInfo):
        self.camera = camera
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._reconnect_count = 0
        self._frame_width = 0
        self._frame_height = 0
        self._bytes_per_frame = 0

    @property
    def is_streaming(self) -> bool:
        return self.camera.state == CameraState.STREAMING

    def start(self) -> None:
        """Start the RTSP stream reader."""
        if self._running:
            return
        self._running = True
        self._reconnect_count = 0
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name=f"rtsp-{self.camera.id}"
        )
        self._reader_thread.start()
        logger.info("RTSP stream started for camera %s", self.camera.id)

    def stop(self) -> None:
        """Stop the RTSP stream reader and kill FFmpeg."""
        self._running = False
        self._kill_process()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=5)
        self.camera.state = CameraState.DISCONNECTED
        logger.info("RTSP stream stopped for camera %s", self.camera.id)

    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest decoded frame (non-blocking)."""
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return None

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
                delay = min(
                    settings.RTSP_RECONNECT_DELAY * (2 ** min(self._reconnect_count - 1, 5)),
                    30.0,
                )
                logger.info(
                    "Camera %s: reconnecting in %.1fs", self.camera.id, delay
                )
                time.sleep(delay)

    @staticmethod
    def _input_url_options(url: str) -> list:
        """Per-scheme input options for ffmpeg/ffprobe.

        ffmpeg 9 rejects a pre-input ``-rtsp_transport`` for any non-RTSP
        source ("Option rtsp_transport not found" -> instant exit before
        opening the file), so the flag is only passed for rtsp:// URLs.
        File and tcp:// sources are unaffected and need no options.
        """
        if url.lower().startswith(("rtsp://", "rtsps://")):
            return ["-rtsp_transport", settings.RTSP_TRANSPORT]
        return []

    def _start_ffmpeg(self) -> None:
        """Launch FFmpeg to decode the RTSP stream."""
        url = self.camera.url

        # FFmpeg command: decode RTSP to raw BGR24 frames on stdout
        cmd = [
            "ffmpeg",
            *self._input_url_options(url),
            "-i", url,
            "-tune", "zerolatency",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-f", "rawvideo",
            "-pix_fmt", self.PIXEL_FORMAT,
            "-v", "quiet",
            "-",
        ]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8,  # 100MB buffer
        )
        self.camera.pid = self._process.pid
        logger.info(
            "FFmpeg started for camera %s (PID %d)", self.camera.id, self._process.pid
        )

    def _read_frames(self) -> None:
        """Read raw BGR frames from FFmpeg stdout."""
        proc = self._process
        if proc is None or proc.stdout is None:
            return

        # First, extract resolution from the stream using FFprobe
        self._probe_resolution()

        if self._frame_width <= 0 or self._frame_height <= 0:
            raise RuntimeError(
                f"Could not determine stream resolution for {self.camera.id}"
            )

        self._bytes_per_frame = self._frame_width * self._frame_height * 3
        self.camera.resolution = (self._frame_width, self._frame_height)
        self.camera.state = CameraState.STREAMING
        self.camera.last_error = ""
        self._reconnect_count = 0

        logger.info(
            "Camera %s: streaming at %dx%d",
            self.camera.id,
            self._frame_width,
            self._frame_height,
        )

        # Read exactly bytes_per_frame bytes at a time
        raw_bytes = b""
        fps_counter_start = time.perf_counter()
        fps_frame_count = 0

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
                    self.camera.frame_count += 1
                    self.camera.last_frame_time = time.time()

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
                stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                raise RuntimeError(f"FFmpeg exited with code {ret}: {stderr[:200]}")

    def _probe_resolution(self) -> None:
        """Probe the RTSP stream for resolution using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                *self._input_url_options(self.camera.url),
                "-i", self.camera.url,
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-v", "quiet",
                "-of", "json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                stream = data.get("streams", [{}])[0]
                self._frame_width = int(stream.get("width", 0))
                self._frame_height = int(stream.get("height", 0))
            else:
                # Fallback: assume 640x480
                logger.warning(
                    "Camera %s: ffprobe failed, assuming 640x480", self.camera.id
                )
                self._frame_width = 640
                self._frame_height = 480
        except Exception as exc:
            logger.warning(
                "Camera %s: resolution probe failed (%s), assuming 640x480",
                self.camera.id,
                exc,
            )
            self._frame_width = 640
            self._frame_height = 480

    def _kill_process(self) -> None:
        """Kill the FFmpeg subprocess."""
        if self._process is not None:
            try:
                self._process.stdout.close() if self._process.stdout else None
                self._process.stderr.close() if self._process.stderr else None
                if os.name == "nt":
                    self._process.kill()
                else:
                    self._process.send_signal(signal.SIGTERM)
                    try:
                        self._process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
            except Exception:
                pass
            self._process = None
            self.camera.pid = None


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
