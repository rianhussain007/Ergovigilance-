"""True RTSP connectivity probe (sell-readiness QA: honest tester).

Opens the stream read-only via ffprobe and reports success/failure —
persisting NOTHING. The Cloud Settings tester and the onboarding flow
use this instead of adding a throwaway camera (the old tester added a
real camera and then tried to delete it by a recomputed id, which
deleted the wrong camera or none at all).

Unreachability is a TEST RESULT (reachable=False), never an exception —
only a missing URL is the caller's error (raised by the endpoint).
"""

from __future__ import annotations

import subprocess
import time
from typing import Any, Callable, Optional

ALLOWED_SCHEMES = ("rtsp://", "rtmp://", "http://", "https://")


def probe_stream(
    url: str,
    timeout_s: int = 10,
    transport: str = "tcp",
    runner: Optional[Callable[..., Any]] = None,
) -> dict:
    """Probe one stream URL. Never raises for network outcomes."""
    url = (url or "").strip()
    if not url.startswith(ALLOWED_SCHEMES):
        return {
            "reachable": False,
            "detail": "URL must start with rtsp://, rtmp://, http://, or https://",
        }
    run = runner or subprocess.run
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-rtsp_transport",
        transport,
        "-analyzeduration",
        "2000000",
        "-probesize",
        "2000000",
        "-i",
        url,
    ]
    try:
        started = time.monotonic()
        result = run(cmd, capture_output=True, text=True, timeout=timeout_s)
        latency_ms = round((time.monotonic() - started) * 1000, 1)
    except FileNotFoundError:
        return {"reachable": False, "detail": "ffprobe not available on this host."}
    except subprocess.TimeoutExpired:
        return {
            "reachable": False,
            "detail": f"No response within {timeout_s}s (timeout). Check the URL, credentials, and network.",
        }
    except Exception as exc:  # never let a probe crash the caller
        return {"reachable": False, "detail": f"Probe failed: {exc}"}
    if result.returncode == 0:
        return {
            "reachable": True,
            "detail": "Stream opened successfully.",
            "latency_ms": latency_ms,
        }
    stderr = (getattr(result, "stderr", "") or "").strip().splitlines()
    tail = stderr[-1][:200] if stderr else f"ffprobe exited with code {result.returncode}"
    return {"reachable": False, "detail": tail}
