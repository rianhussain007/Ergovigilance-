"""Tests for yolo_cloud/stream_probe.py (sell-readiness QA: honest tester).

The subprocess runner is always faked — no network, no ffprobe needed.
"""

from __future__ import annotations

import subprocess

import pytest
from fastapi import HTTPException


class _Result:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def test_reachable():
    from yolo_cloud.stream_probe import probe_stream

    out = probe_stream("rtsp://cam/stream", runner=lambda *a, **k: _Result(0, ""))
    assert out["reachable"] is True
    assert out["detail"] == "Stream opened successfully."
    assert out["latency_ms"] >= 0


def test_unreachable_exit_code_reports_stderr_tail():
    from yolo_cloud.stream_probe import probe_stream

    def _fail(*args, **kwargs):
        return _Result(1, "noise\n[rtsp @ 0] Connection refused\n")

    out = probe_stream("rtsp://dead/stream", runner=_fail)
    assert out["reachable"] is False
    assert "Connection refused" in out["detail"]


def test_timeout():
    from yolo_cloud.stream_probe import probe_stream

    def _hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=8)

    out = probe_stream("rtsp://slow/stream", timeout_s=8, runner=_hang)
    assert out["reachable"] is False
    assert "timeout" in out["detail"].lower()


def test_missing_ffprobe():
    from yolo_cloud.stream_probe import probe_stream

    def _missing(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    out = probe_stream("rtsp://cam/stream", runner=_missing)
    assert out["reachable"] is False
    assert "ffprobe" in out["detail"]


def test_bad_scheme_never_runs():
    from yolo_cloud.stream_probe import probe_stream

    def _boom(*args, **kwargs):
        raise AssertionError("runner must not run for bad scheme")

    out = probe_stream("ftp://cam/stream", runner=_boom)
    assert out["reachable"] is False
    assert "rtsp://" in out["detail"]


def test_endpoint_wiring(monkeypatch):
    import yolo_cloud.api as api
    import yolo_cloud.stream_probe as probe_mod

    monkeypatch.setattr(
        probe_mod, "probe_stream", lambda url, **kwargs: {"reachable": True, "detail": "ok"}
    )
    out = api.probe_camera({"url": "rtsp://x"}, tenant={"tenant_id": "t"})
    assert out["reachable"] is True


def test_endpoint_missing_url():
    import yolo_cloud.api as api

    with pytest.raises(HTTPException) as exc:
        api.probe_camera({}, tenant={"tenant_id": "t"})
    assert exc.value.status_code == 400
