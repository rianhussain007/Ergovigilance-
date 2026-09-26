"""Tests for scripts/pilot_metrics.py (TRL-7 plan §4.4 automation).

All fixtures are synthetic; missing sources must yield n/a, never crash.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilot_metrics import (  # noqa: E402
    COLUMNS,
    append_csv,
    collect,
    disk_free_gb,
    newest_summary,
    parse_identity_audit,
    parse_soak_summary,
    _num,
)


def _write_summary(tmp_path: Path, name: str = "run_summary.json") -> Path:
    doc = {
        "started_utc": "2026-10-01T00:00:00Z",
        "duration_s": 3600,
        "clips": {"saved_total": 120, "truncated_total": 0},
        "alerts_total": 40,
        "alerts_with_worker_id": 30,
        "fps_per_stream": {"mean": 2.5},
        "frame_drops": {"dropped_frames_total": 100, "overall_drop_rate": 0.05},
        "latency": {"by_stream": {"a": {"p95": 800.0}, "b": {"p95": 1200.0}}},
        "id_switches": 1,
    }
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _write_audit(tmp_path: Path) -> Path:
    lines = [
        {"ts": "2026-10-01T08:00:00+00:00", "event": "bind", "worker_id": "W-1"},
        {"ts": "2026-10-01T09:00:00+00:00", "event": "bind", "worker_id": "W-2"},
        {"ts": "2026-10-01T10:00:00+00:00", "event": "reentry_rebind", "worker_id": "W-1"},
        {"ts": "2026-10-02T08:00:00+00:00", "event": "bind", "worker_id": "W-9"},
        "not json at all",
        "",
    ]
    path = tmp_path / "identity_audit.jsonl"
    path.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines), encoding="utf-8")
    return path


def test_num_shapes():
    assert _num(5) == 5.0
    assert _num({"mean": 2}) == 2.0
    assert _num(None) is None
    assert _num(True) is None
    assert _num("x") is None
    assert _num({}) is None


def test_newest_summary_picks_latest(tmp_path):
    _write_summary(tmp_path, "a_summary.json")
    latest = _write_summary(tmp_path, "z_summary.json")
    assert newest_summary(tmp_path) == latest
    assert newest_summary(tmp_path / "missing") is None


def test_parse_soak_summary(tmp_path):
    row = parse_soak_summary(_write_summary(tmp_path))
    assert row["clips_saved"] == 120.0
    assert row["clips_truncated"] == 0.0
    assert row["alerts_total"] == 40.0
    assert row["alerts_with_worker_id"] == 30.0
    assert row["fps_mean"] == 2.5
    assert row["frame_dropped_total"] == 100.0
    assert row["frame_drop_rate"] == 0.05
    assert row["p95_latency_ms"] == 1200.0  # worst stream, not gamed
    assert row["id_switches"] == 1.0


def test_parse_soak_summary_scalar_shapes(tmp_path):
    path = tmp_path / "s_summary.json"
    path.write_text(json.dumps({"fps_per_stream": 3.0, "clips": None}), encoding="utf-8")
    row = parse_soak_summary(path)
    assert row["fps_mean"] == 3.0
    assert row["clips_saved"] is None


def test_parse_soak_summary_missing_file(tmp_path):
    assert parse_soak_summary(tmp_path / "nope.json") == {}


def test_parse_identity_audit_filters_day(tmp_path):
    row = parse_identity_audit(_write_audit(tmp_path), "2026-10-01")
    assert row == {"identity_binds": 2, "identity_reentries": 1, "distinct_workers": 2}


def test_parse_identity_audit_empty_day(tmp_path):
    row = parse_identity_audit(_write_audit(tmp_path), "2026-10-03")
    assert row == {"identity_binds": None, "identity_reentries": None, "distinct_workers": None}


def test_parse_identity_audit_missing_file(tmp_path):
    row = parse_identity_audit(tmp_path / "nope.jsonl", "2026-10-01")
    assert row["identity_binds"] is None


def test_disk_free_positive(tmp_path):
    assert disk_free_gb(tmp_path) is not None
    assert disk_free_gb(tmp_path) > 0


def test_collect_end_to_end_and_append(tmp_path):
    soak_dir = tmp_path / "soak"
    soak_dir.mkdir()
    _write_summary(soak_dir, "run_summary.json")
    audit = _write_audit(tmp_path)

    row = collect("2026-10-01", soak_dir=soak_dir, audit_path=audit,
                  disk_path=tmp_path, restarts=2, notes="shakeout")
    assert set(row) == set(COLUMNS)
    assert row["clips_truncated"] == 0.0
    assert row["distinct_workers"] == 2
    assert row["compose_restarts"] == 2
    assert row["dismiss_reasons"] == ""
    assert row["disk_free_gb"] is not None

    ledger = tmp_path / "ledger.csv"
    append_csv(ledger, row)
    append_csv(ledger, collect("2026-10-02", soak_dir=tmp_path, audit_path=audit,
                              disk_path=tmp_path))
    with open(ledger, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-10-01"
    assert rows[0]["clips_saved"] == "120.0"
    assert rows[1]["identity_binds"] == "1"  # W-9 row only
    assert rows[1]["compose_restarts"] == ""  # n/a serializes empty
