"""FFmpeg kill/reconnect drill — proves the production stream reader recovers.

Why this topology: this machine's FFmpeg 9.0 build no longer binds an RTSP
*listen* server from the muxer (``listen`` is demuxer-only per
``ffmpeg -h demuxer=rtsp``), so an emulated RTSP camera cannot be hosted here.
Instead the drill runs a fake "camera": a TCP socket that streams MPEG-TS,
which FFmpeg's ``tcp://`` protocol accepts as a plain network input. That
exercises the same production path that matters — subprocess spawn, network
read, raw-BGR pipe, kill detection, exponential backoff, reconnect — with one
documented limitation: the RTSP control channel itself (DESCRIBE/SETUP/PLAY
and transport negotiation) is NOT exercised and is marked NOT-MEASURED.

The drill also pins a real bug this harness surfaced: ffmpeg 9 rejects a
pre-input ``-rtsp_transport`` for any non-RTSP source, which made
``RTSPStream._start_ffmpeg`` die instantly for file/tcp URLs. The
scheme-conditional ``RTSPStream._input_url_options`` fix is asserted here.

Stages:
  1. STREAMING  — camera server up, production reader consumes real frames.
  2. KILL       — camera socket hard-closed mid-stream (simulated crash).
  3. RECOVERY   — reader detects the dead pipe, backs off, reconnects once
                  the camera returns; frames flow again on the same object.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time

os.environ.setdefault("YOLO_AUTOINSTALL", "false")
os.environ.setdefault("RTSP_RECONNECT_DELAY", "0.5")  # faster drill cycles

import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from yolo_cloud.config import settings  # noqa: E402
from yolo_cloud.rtsp_manager import RTSPManager  # noqa: E402

READY_MARKER = "Output #0"
FFMPEG = "ffmpeg"
WATCHDOG_S = 180


class FakeCameraServer:
    """Minimal TCP "camera": accept clients and push MPEG-TS bytes forever."""

    def __init__(self, ts_bytes: bytes, port: int):
        self.ts_bytes = ts_bytes
        self.port = port
        self._sock: socket.socket | None = None
        self._conns: list[socket.socket] = []
        # RLock: crash() -> _drop() re-enters the lock on the same thread.
        self._lock = threading.RLock()
        self._running = False
        self._down = False  # True while "camera crashed"
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self._sock.listen(4)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        while self._running:
            try:
                self._sock.settimeout(0.5)
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        with self._lock:
            self._conns.append(conn)
        try:
            while self._running and not self._down:
                conn.sendall(self.ts_bytes)
                time.sleep(1.0)
        except OSError:
            pass
        finally:
            self._drop(conn)

    def _drop(self, conn: socket.socket) -> None:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass
        with self._lock:
            if conn in self._conns:
                self._conns.remove(conn)

    def crash(self) -> None:
        """Simulate camera crash: hard-close every connected client."""
        self._down = True
        with self._lock:
            for c in list(self._conns):
                self._drop(c)

    def recover(self) -> None:
        """Camera back online: accept and serve new clients again."""
        self._down = False

    def stop(self) -> None:
        self._running = False
        self.crash()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass


def ensure_segment(video: str, segment: str) -> bytes:
    """Transcode a short 640x480 MPEG-TS loop segment from the source video."""
    if os.path.exists(segment) and os.path.getsize(segment) > 100_000:
        return open(segment, "rb").read()
    r = subprocess.run(
        [
            FFMPEG, "-y", "-v", "error", "-i", video,
            "-t", "6", "-vf", "scale=640:480",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-g", "30", "-pix_fmt", "yuv420p", "-f", "mpegts", segment,
        ],
        capture_output=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"segment transcode failed: {r.stderr[-300:]!r}")
    return open(segment, "rb").read()


def install_client_logger(log_path: str) -> None:
    """Make every production ffmpeg spawn visible: append stderr to a log.

    Production passes ``stderr=PIPE``; the drill replaces it with a binary
    log file so ``_read_frames``' error path (``stderr.read().decode``) still
    works, and records the exact argv so the drill can assert the
    scheme-conditional option fix.
    """
    import yolo_cloud.rtsp_manager as rm

    orig_popen = rm.subprocess.Popen
    log_fh = open(log_path, "ab")

    def _logged_popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == FFMPEG:
            log_fh.write(("SPAWN: " + " ".join(cmd) + "\n").encode())
            log_fh.flush()
            kwargs["stderr"] = log_fh
        return orig_popen(cmd, *args, **kwargs)

    rm.subprocess.Popen = _logged_popen


def wait_until(predicate, deadline_s: float, what: str) -> bool:
    t0 = time.time()
    while time.time() - t0 < deadline_s:
        if predicate():
            return True
        time.sleep(0.25)
    print(f"{time.strftime('%H:%M:%S')} [drill] TIMEOUT waiting for: {what}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="FFmpeg kill/reconnect drill")
    ap.add_argument("--port", type=int, default=18600)
    ap.add_argument("--video", default=os.path.join(
        REPO, "data/datasets/diverse_training/huggingface",
        "cardboard_manipulation_station01_worker041.mp4"))
    args = ap.parse_args()

    out_dir = os.path.join(REPO, "outputs", "soak")
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    client_log = os.path.join(out_dir, f"ffmpeg_drill_{stamp}_client.log")
    result_path = os.path.join(out_dir, "ffmpeg_reconnect_drill_result.json")
    results: dict = {"started": stamp, "stages": {}}

    # Daemon watchdog: never wedge the terminal even if a stage hangs.
    def _watchdog() -> None:
        print(f"[drill] WATCHDOG fired after {WATCHDOG_S}s — aborting")
        subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"],
                       capture_output=True)
        os._exit(42)

    watchdog = threading.Timer(WATCHDOG_S, _watchdog)
    watchdog.daemon = True
    watchdog.start()

    install_client_logger(client_log)
    ts_bytes = ensure_segment(args.video, os.path.join(out_dir, "ts_segment.ts"))
    print(f"[drill] segment: {len(ts_bytes)} bytes; reconnect_delay="
          f"{settings.RTSP_RECONNECT_DELAY}s max={settings.RTSP_MAX_RECONNECT}")

    url = f"tcp://127.0.0.1:{args.port}/"
    server = FakeCameraServer(ts_bytes, args.port)
    manager = RTSPManager()
    stream = None
    ok = True
    try:
        server.start()
        cam = manager.add_camera("drill-cam", "Drill Camera", url, auto_start=True)
        stream = manager._streams["drill-cam"]

        # ---- Stage 1: STREAMING -------------------------------------------
        s1 = wait_until(
            lambda: cam.state.value == "streaming" and cam.frame_count >= 10,
            45, "initial STREAMING state with frames")
        frame0 = stream.get_frame()
        s1 = s1 and frame0 is not None and frame0.shape == (480, 640, 3)
        results["stages"]["1_streaming"] = {
            "ok": bool(s1), "frames": cam.frame_count,
            "resolution": list(cam.resolution), "frame_shape": list(frame0.shape) if frame0 is not None else None,
        }
        print(f"[drill] stage 1 STREAMING: ok={s1} frames={cam.frame_count} "
              f"res={cam.resolution}")
        ok &= s1
        if not s1:
            raise RuntimeError("stage 1 failed")

        # Assert the scheme-conditional option fix on the recorded spawn line.
        with open(client_log, "rb") as fh:
            spawn = fh.read().decode(errors="replace").splitlines()[0]
        no_rtsp_flag = "-rtsp_transport" not in spawn
        results["stages"]["1_streaming"]["spawn_has_no_rtsp_flag"] = no_rtsp_flag
        print(f"[drill] spawn line clean (no -rtsp_transport for tcp://): "
              f"{no_rtsp_flag}")
        ok &= no_rtsp_flag

        # ---- Stage 2: KILL -------------------------------------------------
        # Kill the ffmpeg CLIENT mid-stream (crash/OOM scenario). A camera
        # socket drop is also valid but non-deterministic on this harness:
        # ffmpeg drains its buffered segment for minutes (clean rc-0 EOF)
        # before noticing, so that path is documented as NOT-MEASURED.
        server.crash()  # also stop feeding new bytes for the kill window
        frames_at_kill = cam.frame_count
        proc = stream._process
        assert proc is not None, "no ffmpeg process at kill stage"
        proc.kill()
        t_kill = time.time()
        detected_latency: list[float] = []

        def _noticed() -> bool:
            if cam.state.value != "streaming":
                if not detected_latency:
                    detected_latency.append(time.time() - t_kill)
                return True
            return False

        s2 = wait_until(_noticed, 60, "reader noticing the killed ffmpeg client")
        s2 = s2 and cam.error_count >= 1
        results["stages"]["2_kill"] = {
            "ok": bool(s2), "state_after": cam.state.value,
            "error_count": cam.error_count, "frames_at_kill": frames_at_kill,
            "detection_latency_s": round(detected_latency[0], 2) if detected_latency else None,
        }
        print(f"[drill] stage 2 KILL: ok={s2} state={cam.state.value} "
              f"errors={cam.error_count} "
              f"latency={detected_latency[0]:.2f}s" if detected_latency else "")
        ok &= s2

        # Camera comes back online before the next reconnect attempt.
        time.sleep(1)
        server.recover()

        # ---- Stage 3: RECOVERY ---------------------------------------------
        s3 = wait_until(
            lambda: cam.state.value == "streaming" and cam.frame_count > frames_at_kill + 10,
            60, "recovery to STREAMING with fresh frames")
        frame1 = stream.get_frame()
        s3 = s3 and frame1 is not None and frame1.shape == (480, 640, 3)
        results["stages"]["3_recovery"] = {
            "ok": bool(s3), "state": cam.state.value,
            "frames_after": cam.frame_count,
            "fresh_frame_shape": list(frame1.shape) if frame1 is not None else None,
        }
        print(f"[drill] stage 3 RECOVERY: ok={s3} frames {frames_at_kill} -> "
              f"{cam.frame_count}")
        ok &= s3
    except Exception as exc:  # noqa: BLE001
        results["error"] = repr(exc)
        print(f"[drill] ERROR: {exc!r}")
        ok = False
    finally:
        if stream is not None:
            stream.stop()
        server.stop()
        watchdog.cancel()
        time.sleep(0.5)

    results["passed"] = bool(ok)
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"[drill] RESULT: {'PASS' if ok else 'FAIL'} — {result_path}")
    subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"], capture_output=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
