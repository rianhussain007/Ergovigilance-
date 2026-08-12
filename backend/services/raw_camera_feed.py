"""Per-camera raw feed manager — lightweight multi-camera support.

The live monitoring pipeline owns ONE camera (the active analysis session).
For the Multi-Camera view we additionally serve RAW frames from the other
connected cameras so every tile shows a real per-camera feed instead of a
duplicate of the analysis camera.

Design:
  - One background capture thread per requested camera source. A source is
    either an int camera index ("0", "1") or an RTSP/IP URL string
    ("rtsp://user:pass@192.168.1.50:554/stream1") — both are accepted by
    ``cv2.VideoCapture``.
  - Frames are read at a modest FPS (~15) to avoid saturating the CPU
    (analysis already consumes a core on the primary camera).
  - A feed auto-releases its camera after ``IDLE_TIMEOUT_S`` with no active
    consumers, so browsers closing a tile free the device.
  - Never raises on open/read failures: ``get_frame`` returns ``None`` and
    the caller can show an offline tile.

The manager is process-local; ``reset()`` exists for tests.
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Union

import cv2
import numpy as np

CAPTURE_FPS = 15.0
FRAME_INTERVAL_S = 1.0 / CAPTURE_FPS
IDLE_TIMEOUT_S = 30.0

CameraSource = Union[int, str]


def _source_key(source: CameraSource) -> str:
    return f"cam:{source}"


class _CameraFeed:
    def __init__(self, source: CameraSource):
        self.source = source
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._frame_number = 0
        self._consumers = 0
        self._last_read_at = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name=f"raw-camera-{_source_key(self.source)}",
        )
        self._thread.start()

    def _capture_loop(self) -> None:
        cap: Optional[cv2.VideoCapture] = None
        try:
            cap = cv2.VideoCapture(self.source)
            if not cap.isOpened():
                return
            while not self._stop.is_set():
                ok, frame = cap.read()
                now = time.time()
                if ok and frame is not None:
                    with self._lock:
                        self._frame = frame
                        self._frame_number += 1
                        self._last_read_at = now
                # Idle consumers + no new frame → exit so the device frees.
                if self._consumers == 0 and now - self._last_read_at > IDLE_TIMEOUT_S:
                    return
                self._stop.wait(FRAME_INTERVAL_S)
        finally:
            if cap is not None:
                cap.release()

    def acquire(self) -> None:
        with self._lock:
            self._consumers += 1
        self.start()

    def release(self) -> None:
        with self._lock:
            self._consumers = max(0, self._consumers - 1)

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_frame_number(self) -> Optional[int]:
        with self._lock:
            return self._frame_number if self._frame is not None else None

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._consumers = 0


_feeds: dict[str, _CameraFeed] = {}
_feeds_lock = threading.Lock()


def get_feed(source: CameraSource) -> _CameraFeed:
    """Return (creating if needed) the feed for a camera source.

    ``source`` is an int camera index (``0``, ``1``) or an RTSP URL string.
    """
    key = _source_key(source)
    with _feeds_lock:
        feed = _feeds.get(key)
        if feed is None:
            feed = _CameraFeed(source)
            _feeds[key] = feed
        return feed


def release_feed(source: CameraSource) -> None:
    """Drop a consumer from the feed; stops the thread when idle."""
    key = _source_key(source)
    with _feeds_lock:
        feed = _feeds.get(key)
    if feed is not None:
        feed.release()


def reset() -> None:
    """Stop all feeds and clear the registry (used by tests)."""
    with _feeds_lock:
        for feed in _feeds.values():
            feed.stop()
        _feeds.clear()
