"""Tests for the pilot request API.

Covers:
- Public submission (no auth required) with valid/invalid payloads
- Admin-only listing
- Round-trip: submitted request appears in the admin list
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _admin_headers(client: TestClient) -> dict:
    res = client.post("/api/auth/login", json={"email": "admin@example.local", "password": "AdminPass123!"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


class TestPilotRequestSubmit:
    def test_submit_public_no_auth(self, client: TestClient):
        """Pilot request submission is public (landing page flow)."""
        res = client.post(
            "/api/pilot-requests",
            json={
                "company_name": "QA Corp",
                "contact_name": "Jane Doe",
                "email": "jane@qacorp.example",
                "role": "Safety Manager",
                "num_stations": "5",
                "message": "Interested in a pilot.",
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["detail"] == "Pilot request submitted successfully"

    def test_submit_minimal_payload(self, client: TestClient):
        """Optional fields may be omitted."""
        res = client.post(
            "/api/pilot-requests",
            json={
                "company_name": "MinimalCo",
                "contact_name": "Bob",
                "email": "bob@minimal.example",
                "role": "Operator",
            },
        )
        assert res.status_code == 201

    def test_submit_invalid_email_rejected(self, client: TestClient):
        res = client.post(
            "/api/pilot-requests",
            json={
                "company_name": "BadCo",
                "contact_name": "X",
                "email": "not-an-email",
                "role": "Operator",
            },
        )
        assert res.status_code == 422

    def test_submit_missing_required_field_rejected(self, client: TestClient):
        res = client.post(
            "/api/pilot-requests",
            json={"company_name": "NoContact", "email": "x@y.example", "role": "Operator"},
        )
        assert res.status_code == 422


class TestPilotRequestList:
    def test_list_requires_admin(self, client: TestClient):
        res = client.get("/api/pilot-requests")
        assert res.status_code in (401, 403)

    def test_list_requires_admin_role(self, client: TestClient):
        """Non-admin roles are forbidden from listing pilot requests."""
        res = client.post("/api/auth/login", json={"email": "operator@example.local", "password": "OperatorPass123!"})
        token = res.json()["token"]
        res = client.get("/api/pilot-requests", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    def test_submitted_request_appears_in_admin_list(self, client: TestClient):
        headers = _admin_headers(client)
        res = client.get("/api/pilot-requests", headers=headers)
        assert res.status_code == 200
        emails = [r["email"] for r in res.json()]
        assert "jane@qacorp.example" in emails
        # The entry has the expected schema
        entry = next(r for r in res.json() if r["email"] == "jane@qacorp.example")
        assert entry["company_name"] == "QA Corp"
        assert entry["num_stations"] == "5"
        assert entry["message"] == "Interested in a pilot."
