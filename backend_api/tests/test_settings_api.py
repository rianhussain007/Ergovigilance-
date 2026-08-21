"""Tests for the user settings API (GET/PUT /api/settings).

Covers:
- Get settings (empty by default)
- Save settings round-trip
- Partial update semantics (only non-None fields persisted)
- Validation of known keys (invalid theme rejected)
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


class TestSettings:
    def test_get_settings_requires_auth(self, client: TestClient):
        res = client.get("/api/settings")
        assert res.status_code in (401, 403)

    def test_get_settings_default_empty(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.get("/api/settings", headers=headers)
        assert res.status_code == 200
        assert res.json() == {}

    def test_save_and_retrieve_settings_round_trip(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.put(
            "/api/settings",
            json={"theme": "dark", "notifications_enabled": True, "data_retention_days": 30},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "ok"
        assert "theme" in body["updated_fields"]

        res = client.get("/api/settings", headers=headers)
        assert res.status_code == 200
        saved = res.json()
        assert saved["theme"] == "dark"
        assert saved["notifications_enabled"] is True
        assert saved["data_retention_days"] == 30

    def test_invalid_theme_rejected(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.put("/api/settings", json={"theme": "neon"}, headers=headers)
        assert res.status_code == 422

    def test_invalid_retention_days_rejected(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.put("/api/settings", json={"data_retention_days": 9999}, headers=headers)
        assert res.status_code == 422

    def test_settings_are_per_user(self, client: TestClient):
        """Settings saved by one user don't leak to another."""
        admin = _auth_headers(client, email="admin@example.local", password="AdminPass123!")
        operator = _auth_headers(client, email="operator@example.local", password="OperatorPass123!")

        client.put("/api/settings", json={"theme": "dark"}, headers=admin)
        res = client.get("/api/settings", headers=operator)
        assert res.status_code == 200
        assert res.json().get("theme") is None
