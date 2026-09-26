"""Tests for backend/services/assessment_pack.py (sell-readiness N3c).

Covers: top-3 ranking (severity > count > name), station rollups,
percentile math, empty/missing-input honesty, tier validation.
"""

from __future__ import annotations

import pytest

from backend.services.assessment_pack import (
    ASSESSMENT_TIERS,
    SCREENING_NOTE,
    benchmark_percentiles,
    build_pack,
    station_comparison,
    top_risks,
)


def _alerts():
    return [
        {"severity": "MEDIUM", "task": "Lifting", "station": "A"},
        {"severity": "MEDIUM", "task": "Lifting", "station": "A"},
        {"severity": "HIGH", "task": "Assembly", "station": "B"},
        {"severity": "LOW", "task": "Seated", "station": "A"},
        {"severity": "MEDIUM", "task": "Assembly", "station": "B"},
    ]


def test_top_risks_severity_first():
    rows = top_risks(_alerts())
    assert [r["task"] for r in rows] == ["Assembly", "Lifting", "Assembly"]
    assert [r["severity"] for r in rows] == ["HIGH", "MEDIUM", "MEDIUM"]
    assert rows[0]["count"] == 1
    assert rows[0]["share"] == pytest.approx(0.2)
    assert sum(r["count"] for r in rows) <= 5


def test_top_risks_tiebreak_and_empty():
    rows = top_risks(
        [
            {"severity": "MEDIUM", "task": "Zebra"},
            {"severity": "MEDIUM", "task": "Apple"},
        ],
        n=2,
    )
    assert [r["task"] for r in rows] == ["Apple", "Zebra"]
    assert top_risks([]) == []
    assert top_risks(None) == []


def test_station_comparison():
    sessions = [
        {"station": "B", "duration_min": 60, "alerts": _alerts()[:2]},
        {"station": "A", "duration_min": 30, "alerts": _alerts()[2:3]},
        {"station": "A", "duration_min": 30, "alerts": []},
    ]
    rows = station_comparison(sessions)
    assert [r["station"] for r in rows] == ["A", "B"]
    by_station = {r["station"]: r for r in rows}
    assert by_station["A"]["sessions"] == 2
    assert by_station["A"]["alerts"] == 1
    assert by_station["A"]["alerts_per_hour"] == 1.0
    assert by_station["A"]["worst_severity"] == "HIGH"
    assert by_station["B"]["alerts_per_hour"] == 2.0


def test_station_comparison_zero_minutes():
    rows = station_comparison([{"station": "A", "duration_min": 0, "alerts": [{"severity": "LOW"}]}])
    assert rows[0]["alerts_per_hour"] == 0.0


def test_benchmark_percentiles():
    rows = benchmark_percentiles({"A": 2.0, "B": 5.0}, [1.0, 2.0, 3.0, 4.0])
    assert {r["station"]: r["percentile"] for r in rows} == {"A": 50.0, "B": 100.0}


def test_benchmark_empty_baseline_is_none():
    rows = benchmark_percentiles({"A": 2.0}, [])
    assert rows[0]["percentile"] is None


def test_build_pack_tiers():
    rapid = build_pack("rapid", sessions=[], alerts=_alerts())
    assert rapid["tier"] == "rapid"
    assert "benchmarks" not in rapid
    assert rapid["screening_note"] == SCREENING_NOTE
    assert len(rapid["top_risks"]) == 3

    line = build_pack(
        "line",
        sessions=[{"station": "A", "duration_min": 60, "alerts": _alerts()}],
        alerts=_alerts(),
        baseline_rates=[1.0, 5.0, 10.0],
    )
    assert line["benchmarks"][0]["station"] == "A"

    baseline = build_pack("baseline", sessions=[], alerts=[])
    assert baseline["top_risks"] == []
    assert baseline["benchmarks"] == []


def test_build_pack_rejects_unknown_tier():
    with pytest.raises(ValueError):
        build_pack("enterprise", sessions=[], alerts=[])


def test_tiers_match_pricing_doc():
    assert set(ASSESSMENT_TIERS) == {"rapid", "line", "baseline"}
