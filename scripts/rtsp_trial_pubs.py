#!/usr/bin/env python3
"""Trial RTSP camera rig for the TRL-6 relevant-environment demo.

Starts MediaMTX on 127.0.0.1:8554 with four static paths (cam1..cam4) and
publishes one *different* trial clip per path via ffmpeg (``-f rtsp``), so the
production RTSP ingestion path runs against four real network streams with
genuine RTP transport, jitter and source pacing.

Usage:
  python scripts/rtsp_trial_pubs.py --seconds 300     # run rig for 5 minutes
  # then, in another shell:
  python scripts/soak_cloud.py --urls rtsp://127.0.0.1:8554/cam1 \
      rtsp://127.0.0.1:8554/cam2 rtsp://127.0.0.1:8554/cam3 \
      rtsp://127.0.0.1:8554/cam4 --seconds 60 --label trl6-rtsp

Paths: MediaMTX binary + config live in tools/mediamtx/ (gitignored binaries;
fetch with any release download — see docs/TRL6_EVIDENCE.md). The publisher
list below is the demo's camera plan; edit TRIAL_CAMERAS to change it.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MTX_DIR = ROOT / "tools" / "mediamtx"
MTX_EXE = MTX_DIR / "mediamtx.exe"
MTX_CFG = MTX_DIR / "trial.yml"
TRIAL = ROOT / "data" / "datasets" / "cctv_trial"
RTSP_BASE = "rtsp://127.0.0.1:8554"

# camera_id -> source clip (4 DIFFERENT sources — crowd CCTV + worker content)
TRIAL_CAMERAS = {
    "cam1": TRIAL / "pets_s1l2_14-06.mp4",        # PETS crowd, cropped panel
    "cam2": TRIAL / "ucsd_peds1_test001.mp4",      # UCSD elevated CCTV crowd
    "cam3": TRIAL / "local_warehouse_lifting.mp4", # worker posture / lifting
    "cam4": TRIAL / "local_assembly_lines.mp4",    # worker posture / assembly
}

CFG = """\
logLevel: info
logDestinations: [stdout]
rtspAddress: 127.0.0.1:8554
paths:
  cam1:
  cam2:
  cam3:
  cam4:
"""


def log(msg: str) -> None:
    print(f"[rtsp-rig] {msg}", flush=True)


def wait_port(port: int, timeout: float = 10.0) -> bool:
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=int, default=300,
                    help="how long to keep the rig up (default 300)")
    args = ap.parse_args()

    if not MTX_EXE.exists():
        log(f"ERROR: {MTX_EXE} missing — download a MediaMTX windows_amd64 "
            "release zip into tools/mediamtx/ (see module docstring)")
        return 2
    missing = [c for c, p in TRIAL_CAMERAS.items() if not p.exists()]
    if missing:
        log(f"ERROR: trial clips missing for {missing} — run "
            "scripts/fetch_cctv_footage.py first")
        return 2

    MTX_CFG.write_text(CFG, encoding="utf-8")
    procs: list[subprocess.Popen] = []
    try:
        mtx = subprocess.Popen([str(MTX_EXE), str(MTX_CFG)], cwd=str(MTX_DIR),
                               stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        procs.append(mtx)
        if not wait_port(8554):
            log("ERROR: MediaMTX did not open rtsp://127.0.0.1:8554 within 10s")
            return 1
        log("MediaMTX up on 127.0.0.1:8554")

        for cam, clip in TRIAL_CAMERAS.items():
            pub = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-re",
                 "-stream_loop", "-1", "-i", str(clip), "-an", "-c", "copy",
                 "-f", "rtsp", "-rtsp_transport", "tcp",
                 f"{RTSP_BASE}/{cam}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            procs.append(pub)
            log(f"publishing {cam} <- {clip.name}")

        # Give publishers time to ANNOUNCE/SETUP before any reader connects.
        time.sleep(4)
        alive = [p.poll() is None for p in procs[1:]]
        if not all(alive):
            log(f"ERROR: {alive.count(False)} publisher(s) died immediately")
            return 1
        log(f"all {len(alive)} publishers live; rig up for {args.seconds}s "
            f"(soak can now run: --urls {' '.join(f'{RTSP_BASE}/{c}' for c in TRIAL_CAMERAS)})")

        start = time.time()
        try:
            while time.time() - start < args.seconds:
                time.sleep(1)
                if procs[0].poll() is not None:
                    log("ERROR: MediaMTX exited early")
                    return 1
        except KeyboardInterrupt:
            log("interrupted — tearing down")
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.terminate()
        for p in reversed(procs):
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        log("rig down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
