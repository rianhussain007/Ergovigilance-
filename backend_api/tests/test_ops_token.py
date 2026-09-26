"""Tests for the METRICS_TOKEN gate on internal-stats endpoints (P0-10).

Probe endpoints (healthz/readyz/health) must stay open; the stats family
(/metrics, /sla, /storage, ...) must fail closed outside DEBUG.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_stats_open_in_debug_without_token(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True)  # conftest posture

    assert client.get("/metrics").status_code == 200
    assert "http_requests_total" in client.get("/metrics").text


def test_token_configured_means_403_without_header(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "sekrit-token")

    assert client.get("/metrics").status_code == 403
    assert client.get("/sla").status_code == 403  # whole stats family
    assert client.get("/storage").status_code == 403


def test_wrong_bearer_rejected_right_bearer_accepted(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "sekrit-token")

    assert client.get(
        "/metrics", headers={"Authorization": "Bearer wrong"}
    ).status_code == 403
    ok = client.get(
        "/metrics", headers={"Authorization": "Bearer sekrit-token"}
    )
    assert ok.status_code == 200
    assert "http_requests_total" in ok.text


def test_x_metrics_token_header_accepted(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "sekrit-token")

    ok = client.get("/metrics", headers={"X-Metrics-Token": "sekrit-token"})
    assert ok.status_code == 200


def test_production_without_token_fails_closed(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    monkeypatch.setattr(settings, "DEBUG", False)

    assert client.get("/metrics").status_code == 403
    # Health probes are exempt — orchestrators depend on them.
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code in (200, 503)
