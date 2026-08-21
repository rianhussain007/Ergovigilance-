"""Tests for the audit trail API endpoints.

Verifies:
- Audit log retrieval (admin/safety_mgr only)
- Filtering by action_type and actor_email
- Pagination (limit/offset)
- Role-based access control (non-admin/safety_mgr gets 403)
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
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


class TestAuditLog:
    """Tests for GET /api/audit."""

    def test_audit_log_returns_list(self, client: TestClient):
        """Admin can retrieve audit log entries."""
        headers = _auth_headers(client)
        res = client.get("/api/audit", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_audit_log_limit_parameter(self, client: TestClient):
        """Limit parameter caps the number of returned entries."""
        headers = _auth_headers(client)
        res = client.get("/api/audit?limit=5", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_audit_log_offset_parameter(self, client: TestClient):
        """Offset parameter skips entries for pagination."""
        headers = _auth_headers(client)
        # Get first page
        res1 = client.get("/api/audit?limit=5&offset=0", headers=headers)
        # Get second page
        res2 = client.get("/api/audit?limit=5&offset=5", headers=headers)
        assert res1.status_code == 200
        assert res2.status_code == 200
        # If there are enough entries, pages should differ
        data1 = res1.json()
        data2 = res2.json()
        if len(data1) == 5 and len(data2) > 0:
            # Pages should have different first entries
            assert data1[0]["id"] != data2[0]["id"]

    def test_audit_log_filter_by_action_type(self, client: TestClient):
        """Filtering by action_type returns only matching entries."""
        headers = _auth_headers(client)
        res = client.get("/api/audit?action_type=worker_created", headers=headers)
        assert res.status_code == 200
        data = res.json()
        for entry in data:
            assert entry["action_type"] == "worker_created"

    def test_audit_log_filter_by_actor_email(self, client: TestClient):
        """Filtering by actor_email returns only matching entries."""
        headers = _auth_headers(client)
        res = client.get("/api/audit?actor_email=admin@example.local", headers=headers)
        assert res.status_code == 200
        data = res.json()
        for entry in data:
            assert entry["actor_email"] == "admin@example.local"

    def test_audit_log_entry_schema(self, client: TestClient):
        """Each audit entry has the expected fields."""
        headers = _auth_headers(client)
        res = client.get("/api/audit?limit=1", headers=headers)
        assert res.status_code == 200
        data = res.json()
        if len(data) > 0:
            entry = data[0]
            required_fields = ["id", "actor_email", "actor_role", "action_type", "timestamp"]
            for field in required_fields:
                assert field in entry, f"Missing field: {field}"

    def test_audit_log_unauthenticated_returns_401(self, client: TestClient):
        """Unauthenticated request returns 401."""
        res = client.get("/api/audit")
        assert res.status_code in (401, 403)

    def test_audit_log_operator_forbidden(self, client: TestClient):
        """Operator role cannot access audit log (403)."""
        headers = _auth_headers(
            client,
            email="operator@example.local",
            password="OperatorPass123!",
        )
        res = client.get("/api/audit", headers=headers)
        assert res.status_code == 403

    def test_audit_log_limit_validation(self, client: TestClient):
        """Invalid limit values are rejected."""
        headers = _auth_headers(client)
        # Limit < 1
        res = client.get("/api/audit?limit=0", headers=headers)
        assert res.status_code == 422
        # Limit > 1000
        res = client.get("/api/audit?limit=1001", headers=headers)
        assert res.status_code == 422

    def test_audit_log_offset_validation(self, client: TestClient):
        """Invalid offset values are rejected."""
        headers = _auth_headers(client)
        # Negative offset
        res = client.get("/api/audit?offset=-1", headers=headers)
        assert res.status_code == 422
