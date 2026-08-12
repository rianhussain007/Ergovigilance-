"""Tests for the Tier 1 PostgreSQL telemetry store.

Unit tests exercise pure logic (sample-time synthesis, source selection in the
session cache) without needing a live database. Integration tests run only when
DATABASE_URL points at a reachable Postgres (skipped otherwise) so CI and
offline dev stay green.

Run against the local instance:
    DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/ergovigilance_test \
        pytest tests/test_postgres_store.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_API_DIR = ROOT / "backend_api"
if str(BACKEND_API_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_DIR))

from app.core import postgres  # noqa: E402
from app.services import session_cache  # noqa: E402

PG_URL = os.environ.get("DATABASE_URL", "")


def test_sample_time_combines_session_ts_and_frame_seconds():
    payload = {"session_timestamp": "20260810_114836_241"}
    out = postgres._sample_time(payload, 65.5)
    assert out == "2026-08-10T11:49:41.500000+00:00", out


def test_sample_time_handles_missing_timestamp():
    out = postgres._sample_time({}, 5.0)
    assert out == "1970-01-01T00:00:00Z"


def test_sample_time_handles_bad_timestamp():
    out = postgres._sample_time({"session_timestamp": "garbage"}, 5.0)
    assert out == "1970-01-01T00:00:00Z"


def test_session_cache_prefers_postgres_when_rows_present(monkeypatch):
    """When the Postgres store returns rows, the cache uses them."""
    rows = [{"session_id": "SESH-PG-1", "session_timestamp": "20260810_120000", "total_frames": 5}]

    monkeypatch.setattr(postgres, "pg_enabled", lambda: True)
    monkeypatch.setattr(postgres, "fetch_sessions", lambda: rows)
    monkeypatch.setattr(session_cache, "_scan_session_files", lambda: [{"session_id": "SESH-FILE-1"}])

    session_cache.invalidate_session_cache()
    result = session_cache.get_all_sessions()
    assert result == rows
    assert session_cache.cache_source() == "postgres"


def test_session_cache_falls_back_to_files_when_pg_empty(monkeypatch):
    """An empty/offline Postgres store must not hide the file-based sessions."""
    rows: list[dict] = []

    monkeypatch.setattr(postgres, "pg_enabled", lambda: True)
    monkeypatch.setattr(postgres, "fetch_sessions", lambda: rows)
    monkeypatch.setattr(
        session_cache, "_scan_session_files",
        lambda: [{"session_id": "SESH-FILE-1", "session_timestamp": "20260810_120000"}],
    )

    session_cache.invalidate_session_cache()
    result = session_cache.get_all_sessions()
    assert result[0]["session_id"] == "SESH-FILE-1"
    assert session_cache.cache_source() == "file"


def test_session_cache_file_mode_when_pg_disabled(monkeypatch):
    """With DATABASE_URL unset, the file path is used directly."""
    monkeypatch.setattr(postgres, "pg_enabled", lambda: False)
    monkeypatch.setattr(
        session_cache, "_scan_session_files",
        lambda: [{"session_id": "SESH-FILE-2", "session_timestamp": "20260810_120000"}],
    )

    session_cache.invalidate_session_cache()
    result = session_cache.get_all_sessions()
    assert result[0]["session_id"] == "SESH-FILE-2"
    assert session_cache.cache_source() == "file"


@pytest.mark.skipif(not PG_URL, reason="DATABASE_URL not set")
def test_pg_round_trip_integration():
    """Real Postgres round-trip: schema init, upsert, fetch (integration)."""
    import uuid

    postgres.reset_connection()
    assert postgres.init_postgres_schema()

    sid = f"SESH-PG-TEST-{uuid.uuid4().hex[:8]}"
    payload = {
        "session_id": sid,
        "session_timestamp": "20260810_120000",
        "worker_id": "worker-test",
        "task_name": "Assembly Work",
        "highest_risk_level": "MEDIUM",
        "session_duration_seconds": 60.0,
        "total_frames": 3,
        "risk_percentages": {"LOW": 50.0, "MEDIUM": 50.0, "HIGH": 0.0},
        "most_frequent_issue": "Elevated Left Shoulder",
    }
    frames = [
        {"frame_number": 1, "timestamp": 0.5, "risk_score": 40.0, "risk_level": "MEDIUM",
         "confidence": 90.0, "fatigue": 1.0, "exposure": 2.0, "current_task": "Assembly Work",
         "features": {"neck_flexion": 10.0}},
        {"frame_number": 2, "timestamp": 1.5, "risk_score": 45.0, "risk_level": "MEDIUM",
         "confidence": 91.0, "fatigue": 1.5, "exposure": 3.0, "current_task": "Assembly Work",
         "features": {"neck_flexion": 12.0}},
        {"frame_number": 3, "timestamp": 2.5, "risk_score": 50.0, "risk_level": "MEDIUM",
         "confidence": 92.0, "fatigue": 2.0, "exposure": 4.0, "current_task": "Assembly Work",
         "features": {"neck_flexion": 14.0}},
    ]

    try:
        assert postgres.upsert_session(payload) is True
        assert postgres.bulk_insert_frames(payload, frames) is True

        sessions = postgres.fetch_sessions()
        match = [s for s in sessions if s.get("session_id") == sid]
        assert len(match) == 1
        assert match[0]["task_name"] == "Assembly Work"

        fetched = postgres.fetch_frames(sid)
        assert len(fetched) == 3
        assert fetched[0]["frame_number"] == 1
        assert fetched[2]["features"]["neck_flexion"] == 14.0
    finally:
        # Clean up the test rows.
        conn = postgres.get_connection()
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM ergo_session_frames WHERE session_id = %s", (sid,))
                    cur.execute("DELETE FROM ergo_sessions WHERE session_id = %s", (sid,))
                conn.commit()
            except Exception:
                pass
        postgres.reset_connection()
