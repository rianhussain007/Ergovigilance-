"""Tests for the analytics endpoint (GET /api/analytics).

In the isolated test environment there are no session files, so the endpoint
must return a well-formed empty analytics payload (not crash).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _auth_headers(client: TestClient, email: str = "admin@example.local", password: str = "AdminPass123!") -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


class TestAnalytics:
    def test_analytics_requires_auth(self, client: TestClient):
        res = client.get("/api/analytics")
        assert res.status_code in (401, 403)

    def test_analytics_empty_payload_shape(self, client: TestClient):
        """With no sessions, the endpoint returns a well-formed empty payload."""
        headers = _auth_headers(client)
        res = client.get("/api/analytics", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["summary"]["total_sessions"] == 0
        assert body["summary"]["avg_risk_score"] == 0
        assert body["weekly_risk_trend"] == []
        assert body["risk_distribution"] == []
        assert body["issue_frequency"] == []
        assert body["neck_trunk_trend"] == []

    def test_analytics_available_to_any_role(self, client: TestClient):
        """Operators can view analytics (role-gating applies to other modules)."""
        headers = _auth_headers(client, email="operator@example.local", password="OperatorPass123!")
        res = client.get("/api/analytics", headers=headers)
        assert res.status_code == 200
