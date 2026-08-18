"""Incident evidence package: assembles session JSON + recording sidecars into
a zip with a README framing, and skips oversized videos.
"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.evidence_package as ep  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    recordings = tmp_path / "recordings"
    (sessions / "worker-001").mkdir(parents=True)
    (recordings / "w1" / "20260818_120000_SESH-EV").mkdir(parents=True)
    session_file = sessions / "session_20260818_120000_SESH-EV.json"
    session_file.write_text(
        json.dumps({
            "session_timestamp": "20260818_120000",
            "total_frames": 120,
            "highest_risk_level": "HIGH",
            "alerts": [{"id": "ALT-1", "severity": "CRITICAL"}],
        }),
        encoding="utf-8",
    )
    (recordings / "w1" / "20260818_120000_SESH-EV" / "timeline.json").write_text(
        json.dumps([{"frame": 1}]), encoding="utf-8"
    )
    (recordings / "w1" / "20260818_120000_SESH-EV" / "original.mp4").write_bytes(b"FAKEVIDEO" * 100)
    # Overlay preferred when present — reviewers read the burned-in skeleton.
    (recordings / "w1" / "20260818_120000_SESH-EV" / "overlay.mp4").write_bytes(b"OVERLAY" * 200)

    monkeypatch.setattr(ep, "_SESSIONS_DIR", str(sessions))
    monkeypatch.setattr(ep, "_EVIDENCE_DIR", str(tmp_path / "evidence"))
    monkeypatch.setattr(ep, "_MAX_PACKAGE_MB", 0.00001)  # tiny cap -> video skipped
    import app.api.recordings as recordings_api
    monkeypatch.setattr(
        recordings_api,
        "_find_recording_dir",
        lambda sid: str(recordings / "w1" / "20260818_120000_SESH-EV"),
    )


def test_package_bundles_session_timeline_and_readme(tmp_path):
    result = ep.build_evidence_package("SESH-EV")
    assert result["path"]
    assert result["size_bytes"] > 0
    assert not any(e.startswith("recording/") and e.endswith(".mp4") for e in result["entries"])
    assert any("too large" in s for s in result["skipped"])

    with zipfile.ZipFile(result["path"]) as zf:
        names = set(zf.namelist())
        assert "session.json" in names
        assert "recording/timeline.json" in names
        assert "README.txt" in names
        readme = zf.read("README.txt").decode("utf-8")
        assert "not clinically validated" in readme
        assert "heuristic" in readme.lower()


def test_package_includes_overlay_not_original(tmp_path, monkeypatch):
    monkeypatch.setattr(ep, "_MAX_PACKAGE_MB", 100.0)
    result = ep.build_evidence_package("SESH-EV")
    assert "recording/overlay.mp4" in result["entries"]
    assert "recording/original.mp4" not in result["entries"]  # one video only
    assert result["skipped"] == []


def test_missing_session_raises_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ep, "_find_session_file", lambda sid: None)
    with pytest.raises(FileNotFoundError):
        ep.build_evidence_package("SESH-NOPE")


def test_package_without_recording_still_builds(tmp_path, monkeypatch):
    import app.api.recordings as recordings_api
    monkeypatch.setattr(recordings_api, "_find_recording_dir", lambda sid: None)
    result = ep.build_evidence_package("SESH-EV")
    with zipfile.ZipFile(result["path"]) as zf:
        assert "session.json" in zf.namelist()
        assert not any(n.startswith("recording/") for n in zf.namelist())
