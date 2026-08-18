"""Tests for the de-identified benchmark percentile baseline."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.services import benchmark

VALID_METRIC = "avg_neck_flexion"


def _write_session(tmp_path, session_id: str, **metrics) -> None:
    """Write a minimal session file with the given avg_* values."""
    (tmp_path / f"{session_id}.json").write_text(
        json.dumps({"session_id": session_id, **metrics}),
        encoding="utf-8",
    )


@pytest.fixture()
def bench_dir(tmp_path, monkeypatch):
    """Point the benchmark at a temp sessions dir + temp baseline output."""
    sessions = tmp_path / "sessions"
    sessions.mkdir(exist_ok=True)
    out = tmp_path / "bench"
    monkeypatch.setattr(benchmark, "SESSIONS_DIR", str(sessions))
    monkeypatch.setattr(benchmark, "BENCHMARK_DIR", str(out))
    monkeypatch.setattr(benchmark, "BASELINE_PATH", str(out / "baseline.json"))
    return sessions


class TestRebuild:
    def test_rebuild_collects_metrics(self, bench_dir):
        _write_session(bench_dir, "s1", avg_neck_flexion=10.0, avg_trunk_flexion=5.0)
        _write_session(bench_dir, "s2", avg_neck_flexion=20.0, avg_trunk_flexion=8.0)
        _write_session(bench_dir, "s3", avg_neck_flexion=30.0)  # no trunk value

        summary = benchmark.rebuild_baseline()
        assert summary["session_count"] == 3
        assert summary["metrics"]["avg_neck_flexion"]["count"] == 3
        assert summary["metrics"]["avg_neck_flexion"]["min"] == 10.0
        assert summary["metrics"]["avg_neck_flexion"]["max"] == 30.0
        assert summary["metrics"]["avg_trunk_flexion"]["count"] == 2

    def test_rebuild_skips_corrupt_and_nan(self, bench_dir):
        (bench_dir / "bad.json").write_text("{not json", encoding="utf-8")
        _write_session(bench_dir, "s1", avg_neck_flexion="not-a-number")
        _write_session(bench_dir, "s2", avg_neck_flexion=float("nan"))
        _write_session(bench_dir, "s3", avg_neck_flexion=15.0)

        summary = benchmark.rebuild_baseline()
        # Corrupt file, string value, and NaN are all excluded; only s3 counts.
        assert summary["session_count"] == 1
        assert summary["metrics"]["avg_neck_flexion"]["count"] == 1

    def test_baseline_contains_no_identifiers(self, bench_dir):
        """The persisted baseline must contain only numbers — no ids or names."""
        _write_session(bench_dir, "s1", avg_neck_flexion=10.0)
        _write_session(bench_dir, "s2", avg_neck_flexion=25.0)
        benchmark.rebuild_baseline()

        raw = json.load(open(benchmark.BASELINE_PATH, encoding="utf-8"))
        joined = json.dumps(raw)
        assert "s1" not in joined and "s2" not in joined
        for metric, vals in raw["metrics"].items():
            assert all(isinstance(v, (int, float)) for v in vals)


class TestPercentile:
    def test_percentile_rank(self, bench_dir):
        _write_session(bench_dir, "s1", avg_neck_flexion=10.0)
        _write_session(bench_dir, "s2", avg_neck_flexion=20.0)
        _write_session(bench_dir, "s3", avg_neck_flexion=30.0)
        benchmark.rebuild_baseline()

        low = benchmark.percentile_for(VALID_METRIC, 5.0)  # below every value
        assert low["percentile"] == 0.0
        assert low["band"] == "below-typical"

        mid = benchmark.percentile_for(VALID_METRIC, 15.0)  # 1 of 3 at/below
        assert mid["percentile"] == pytest.approx(33.3, abs=0.1)

        high = benchmark.percentile_for(VALID_METRIC, 35.0)  # above every value
        assert high["percentile"] == 100.0
        assert high["band"] == "above-typical"

    def test_no_baseline_returns_zeroed(self, bench_dir):
        out = benchmark.percentile_for(VALID_METRIC, 12.0)
        assert out["percentile"] is None
        assert out["n"] == 0
        assert out["band"] == "no-baseline"

    def test_missing_metric_value_tolerated(self, bench_dir):
        _write_session(bench_dir, "s1", avg_neck_flexion=10.0)
        benchmark.rebuild_baseline()
        # No knee data in the pool -> zeroed result, not an error.
        out = benchmark.percentile_for("avg_knee_angle", 5.0)
        assert out["percentile"] is None
        assert out["n"] == 0


@pytest.fixture(autouse=True, scope="module")
def _isolate_benchmark_paths(tmp_path_factory):
    """Point the benchmark at temp paths so API tests never touch the real
    outputs/benchmark baseline (conftest redirects SESSIONS_DIR but not
    BENCHMARK_DIR)."""
    tmp = tmp_path_factory.mktemp("bench-api")
    sessions = tmp / "sessions"
    sessions.mkdir(exist_ok=True)
    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(benchmark, "SESSIONS_DIR", str(sessions))
    monkeypatch.setattr(benchmark, "BENCHMARK_DIR", str(tmp / "bench"))
    monkeypatch.setattr(benchmark, "BASELINE_PATH", str(tmp / "bench" / "baseline.json"))
    yield
    monkeypatch.undo()


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _auth_headers(client: TestClient, email="admin@example.local", pw="AdminPass123!") -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


class TestBenchmarkApi:
    def test_get_benchmark_builds_on_first_use(self, client: TestClient):
        res = client.get("/api/benchmark", headers=_auth_headers(client))
        assert res.status_code == 200
        body = res.json()
        assert "session_count" in body
        assert "metrics" in body

    def test_percentile_endpoint_validates_metric(self, client: TestClient):
        res = client.post(
            "/api/benchmark/percentile",
            json={"metric": "bogus_metric", "value": 5.0},
            headers=_auth_headers(client),
        )
        assert res.status_code == 422

    def test_rebuild_requires_manager_role(self, client: TestClient):
        headers = _auth_headers(client, email="operator@example.local", pw="OperatorPass123!")
        res = client.post("/api/benchmark/rebuild", headers=headers)
        assert res.status_code == 403
