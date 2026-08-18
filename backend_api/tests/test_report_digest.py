"""Tests for the risk digest service: window filtering, aggregation math,
save + rotation, and listing. Uses a temp REPORTS_DIR so tests never touch
the real outputs/ directory.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.report_digest as rd  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(rd, "_MAX_DIGESTS", 3)
    sessions = [
        {
            "session_timestamp": (datetime.now() - timedelta(hours=1)).strftime("%Y%m%d_%H%M%S"),
            "total_frames": 100,
            "risk_percentages": {"LOW": 50.0, "MEDIUM": 30.0, "HIGH": 20.0},
            "alerts": [{"id": "a1"}, {"id": "a2"}],
            "most_frequent_issue": "neck_flexion",
            "highest_risk_level": "HIGH",
            "session_id": "SESH-RECENT",
            "worker_id": "w1",
        },
        {
            "session_timestamp": (datetime.now() - timedelta(days=3)).strftime("%Y%m%d_%H%M%S"),
            "total_frames": 50,
            "risk_percentages": {"LOW": 90.0, "MEDIUM": 5.0, "HIGH": 5.0},
            "alerts": [],
            "most_frequent_issue": None,
            "highest_risk_level": "LOW",
            "session_id": "SESH-OLD",
            "worker_id": "w2",
        },
    ]
    monkeypatch.setattr(rd, "get_all_sessions", lambda: sessions)


def test_digest_filters_to_window_and_aggregates():
    result = rd.generate_digest(since_hours=24.0, save=False)
    digest = result["digest"]
    assert result["saved"] is False
    assert digest["summary"]["session_count"] == 1  # old session excluded
    assert digest["summary"]["alert_count"] == 2
    assert digest["summary"]["highest_risk_level"] == "HIGH"
    assert digest["summary"]["top_issue"] == "neck_flexion"
    # Frame-weighted risk percentages (only the recent 100-frame session).
    assert digest["summary"]["risk_percentages"]["LOW"] == 50.0
    assert digest["summary"]["risk_percentages"]["HIGH"] == 20.0
    assert len(digest["sessions"]) == 1
    assert digest["sessions"][0]["session_id"] == "SESH-RECENT"


def test_digest_saves_file_and_lists(tmp_path):
    result = rd.generate_digest(since_hours=24.0, save=True)
    assert result["saved"] is True
    path = Path(result["path"])
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["digest_type"] == "risk_digest"
    assert data["summary"]["session_count"] == 1

    listed = rd.list_digests()
    assert len(listed) == 1
    assert listed[0]["filename"] == path.name
    assert listed[0]["summary"]["alert_count"] == 2


def test_digest_rotates_old_files(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    for i in range(5):
        (reports / f"digest_2026081{i}_000000.json").write_text(
            json.dumps({"generated_at": f"2026-08-1{i}T00:00:00", "summary": {}}),
            encoding="utf-8",
        )
    rd.generate_digest(since_hours=24.0, save=True)
    remaining = sorted(reports.glob("digest_*.json"))
    assert len(remaining) <= rd._MAX_DIGESTS


def test_digest_empty_window_does_not_save(tmp_path):
    monkeypatch_sessions = rd.get_all_sessions
    rd.get_all_sessions = lambda: []
    try:
        result = rd.generate_digest(since_hours=24.0, save=True)
        assert result["saved"] is False
        assert result["digest"]["summary"]["session_count"] == 0
        assert not list(rd.list_digests())
    finally:
        rd.get_all_sessions = monkeypatch_sessions
