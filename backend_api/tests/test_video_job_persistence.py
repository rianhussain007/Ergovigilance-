"""Regression tests for SQLite-backed video-analysis job persistence.

Verifies that analysis jobs survive backend restarts: a completed job
rehydrates with its full result, and a job that was in-flight when the
process died is marked ``error`` with a helpful message instead of hanging
forever in the polling UI.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from app.schemas.api import VideoAnalysisResponse, VideoAnalysisSummary  # noqa: E402

# Test against a throwaway DB so real job state is never touched.
_TEST_DB = Path(__file__).resolve().parent / "test_jobs.db"


@pytest.fixture()
def fresh_module(monkeypatch):
    import app.api.video_analysis as va

    # Point the module at a unique test DB (per-process pid avoids cross-run
    # locks on Windows, where an unclosed handle blocks deletion).
    test_db = _TEST_DB.with_name(f"test_jobs_{os.getpid()}.db")
    va._JOB_DB = test_db
    va._init_job_db()
    with va._job_db() as conn:
        conn.execute("DELETE FROM video_analysis_jobs")
        conn.commit()
    va._jobs.clear()
    yield va
    va._jobs.clear()
    try:
        test_db.unlink()
    except OSError:
        pass
    test_auth = test_db.with_name(f"test_auth_{os.getpid()}.db")
    if test_auth.exists():
        try:
            test_auth.unlink()
        except OSError:
            pass


def _make_complete_job(va, jid: str) -> None:
    summary = VideoAnalysisSummary(
        analyzed_frames=10,
        source_frames=100,
        duration_seconds=3.3,
        fps=30.0,
        frame_step=10,
        risk_counts={"LOW": 8, "MEDIUM": 2},
        risk_percentages={"LOW": 80.0, "MEDIUM": 20.0},
        average_features={"neck_flexion": 5.0},
    )
    res = VideoAnalysisResponse(filename="demo.mp4", summary=summary, frames=[])
    job = va.VideoAnalysisJob(job_id=jid, status="complete")
    job.result = res
    job.progress = {"frames_processed": 10, "total_frames": 100, "percent": 100.0}
    job._finished_at = time.time()
    va._jobs[jid] = job
    va._persist_job(job)


def test_completed_job_rehydrates_with_result(fresh_module) -> None:
    va = fresh_module
    _make_complete_job(va, "VIDJOB-COMPLETE-TEST")

    # Simulate a fresh process: clear memory and reload from SQLite.
    va._jobs.clear()
    va._load_jobs_from_db()

    job = va._jobs.get("VIDJOB-COMPLETE-TEST")
    assert job is not None
    assert job.status == "complete"
    assert job.result is not None
    assert job.result.filename == "demo.mp4"
    assert job.progress["percent"] == 100.0


def test_inflight_job_becomes_error_on_reload(fresh_module) -> None:
    va = fresh_module
    job = va.VideoAnalysisJob(job_id="VIDJOB-INFLIGHT-TEST", status="processing")
    va._jobs[job.job_id] = job
    va._persist_job(job)

    va._jobs.clear()
    va._load_jobs_from_db()

    job = va._jobs.get("VIDJOB-INFLIGHT-TEST")
    assert job is not None
    assert job.status == "error"
    assert "restart" in (job.error or "").lower()


def test_job_row_written_to_sqlite(fresh_module) -> None:
    va = fresh_module
    _make_complete_job(va, "VIDJOB-ROW-TEST")
    with va._job_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM video_analysis_jobs WHERE job_id = ?", ("VIDJOB-ROW-TEST",)
        ).fetchone()
    assert row is not None
    assert row["status"] == "complete"
    assert json.loads(row["result"])["filename"] == "demo.mp4"


def test_ttl_cleanup_removes_rows(fresh_module) -> None:
    va = fresh_module
    _make_complete_job(va, "VIDJOB-TTL-TEST")
    job = va._jobs["VIDJOB-TTL-TEST"]
    job._finished_at = time.time() - va.JOB_TTL_SECONDS - 1  # expired
    va._persist_job(job)

    va._cleanup_expired_jobs()

    assert "VIDJOB-TTL-TEST" not in va._jobs
    with va._job_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM video_analysis_jobs WHERE job_id = ?", ("VIDJOB-TTL-TEST",)
        ).fetchone()
    assert row is None
