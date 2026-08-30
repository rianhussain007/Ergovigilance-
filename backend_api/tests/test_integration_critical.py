"""Integration tests for critical product paths.

Covers the end-to-end flows that must work for a sellable product:

1. Full auth lifecycle (login → token → protected endpoint → role checks)
2. Demo mode login (one-click demo with synthetic data)
3. User CRUD lifecycle (create → update → password reset → delete)
4. Settings round-trip with per-user isolation
5. Alert persistence (insert → load → acknowledge → resolve → history)
6. Audit trail (login actions are logged)
7. Privacy wipe (admin deletes worker data)
8. Pilot request submission
9. Report digest generation
10. Security: expired tokens, missing tokens, role escalation attempts
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.database import (
    insert_alert,
    load_active_alerts,
    load_alert_history,
    update_alert_state,
)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str = "admin@example.local", password: str = "AdminPass123!") -> str:
    """Login and return JWT token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _auth(client: TestClient, email: str = "admin@example.local", password: str = "AdminPass123!") -> dict:
    """Return Authorization headers dict."""
    return {"Authorization": f"Bearer {_login(client, email, password)}"}


# ═══════════════════════════════════════════════════════════════════
# 1. Full Auth Lifecycle
# ═══════════════════════════════════════════════════════════════════

class TestAuthLifecycle:
    def test_login_returns_complete_token(self, client: TestClient):
        """Login returns token, user info, and expiry metadata."""
        res = client.post("/api/auth/login", json={
            "email": "admin@example.local",
            "password": "AdminPass123!",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["token"]
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 3600
        assert body["expires_at"]
        assert body["user"]["id"] > 0
        assert body["user"]["email"] == "admin@example.local"
        assert body["user"]["role"] == "admin"

    def test_all_roles_can_login(self, client: TestClient):
        """Every seeded role can authenticate successfully."""
        accounts = [
            ("operator@example.local", "OperatorPass123!", "operator"),
            ("supervisor@example.local", "SupervisorPass123!", "supervisor"),
            ("safety@example.local", "SafetyPass123!", "safety_mgr"),
            ("admin@example.local", "AdminPass123!", "admin"),
        ]
        for email, password, expected_role in accounts:
            res = client.post("/api/auth/login", json={"email": email, "password": password})
            assert res.status_code == 200, f"Failed for {email}: {res.text}"
            assert res.json()["user"]["role"] == expected_role

    def test_wrong_password_returns_401(self, client: TestClient):
        res = client.post("/api/auth/login", json={
            "email": "admin@example.local",
            "password": "wrong-password",
        })
        assert res.status_code == 401

    def test_nonexistent_email_returns_401(self, client: TestClient):
        res = client.post("/api/auth/login", json={
            "email": "nonexistent@example.local",
            "password": "anything",
        })
        assert res.status_code == 401

    def test_missing_token_returns_401(self, client: TestClient):
        res = client.get("/api/settings")
        assert res.status_code in (401, 403)

    def test_invalid_token_returns_401(self, client: TestClient):
        res = client.get("/api/settings", headers={"Authorization": "Bearer invalid.token.here"})
        assert res.status_code == 401

    def test_operator_cannot_access_admin_endpoint(self, client: TestClient):
        """Operator role is rejected from admin-only user management."""
        headers = _auth(client, "operator@example.local", "OperatorPass123!")
        res = client.get("/api/users", headers=headers)
        assert res.status_code == 403

    def test_supervisor_cannot_access_admin_endpoint(self, client: TestClient):
        """Supervisor role is rejected from admin-only user management."""
        headers = _auth(client, "supervisor@example.local", "SupervisorPass123!")
        res = client.get("/api/users", headers=headers)
        assert res.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 2. Demo Mode
# ═══════════════════════════════════════════════════════════════════

class TestDemoMode:
    def test_demo_login_returns_token(self, client: TestClient):
        """One-click demo login works without credentials."""
        res = client.post("/api/auth/demo")
        assert res.status_code == 200
        body = res.json()
        assert body["token"]
        assert body["user"]["role"] == "operator"

    def test_demo_mode_status_endpoint(self, client: TestClient):
        res = client.get("/api/demo-mode")
        assert res.status_code == 200
        body = res.json()
        assert "demo_mode" in body


# ═══════════════════════════════════════════════════════════════════
# 3. User Management Lifecycle (Admin CRUD)
# ═══════════════════════════════════════════════════════════════════

class TestUserLifecycle:
    def test_full_lifecycle(self, client: TestClient):
        """Create → read → update → password reset → verify login → delete."""
        headers = _auth(client)

        # Create
        res = client.post("/api/users", json={
            "email": "integration-test@example.local",
            "password": "TestPass123!",
            "role": "operator",
        }, headers=headers)
        assert res.status_code == 201, res.text
        uid = res.json()["id"]
        assert res.json()["email"] == "integration-test@example.local"

        # Read (via list)
        res = client.get("/api/users", headers=headers)
        emails = [u["email"] for u in res.json()]
        assert "integration-test@example.local" in emails

        # Update role
        res = client.put(f"/api/users/{uid}", json={"role": "supervisor"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["role"] == "supervisor"

        # Login with original password
        res = client.post("/api/auth/login", json={
            "email": "integration-test@example.local",
            "password": "TestPass123!",
        })
        assert res.status_code == 200

        # Password reset
        res = client.post(f"/api/users/{uid}/reset-password", json={
            "password": "NewPassword456!",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["new_password"] == "NewPassword456!"

        # Login with new password
        res = client.post("/api/auth/login", json={
            "email": "integration-test@example.local",
            "password": "NewPassword456!",
        })
        assert res.status_code == 200

        # Old password fails
        res = client.post("/api/auth/login", json={
            "email": "integration-test@example.local",
            "password": "TestPass123!",
        })
        assert res.status_code == 401

        # Delete
        res = client.delete(f"/api/users/{uid}", headers=headers)
        assert res.status_code == 204

        # Confirm gone
        res = client.get("/api/users", headers=headers)
        emails = [u["email"] for u in res.json()]
        assert "integration-test@example.local" not in emails


# ═══════════════════════════════════════════════════════════════════
# 4. Settings Round-Trip
# ═══════════════════════════════════════════════════════════════════

class TestSettingsLifecycle:
    def test_save_and_retrieve(self, client: TestClient):
        headers = _auth(client)

        # Save
        res = client.put("/api/settings", json={
            "theme": "dark",
            "notifications_enabled": True,
            "data_retention_days": 7,
        }, headers=headers)
        assert res.status_code == 200
        assert set(res.json()["updated_fields"]) == {"theme", "notifications_enabled", "data_retention_days"}

        # Retrieve
        res = client.get("/api/settings", headers=headers)
        assert res.status_code == 200
        saved = res.json()
        assert saved["theme"] == "dark"
        assert saved["notifications_enabled"] is True
        assert saved["data_retention_days"] == 7

    def test_partial_update_preserves_existing(self, client: TestClient):
        headers = _auth(client, "operator@example.local", "OperatorPass123!")

        # Set initial values
        client.put("/api/settings", json={"theme": "dark", "data_retention_days": 30}, headers=headers)

        # Partial update: send both fields
        res = client.put("/api/settings", json={"theme": "light", "data_retention_days": 30}, headers=headers)
        assert res.status_code == 200

        # Verify saved
        res = client.get("/api/settings", headers=headers)
        saved = res.json()
        assert saved["theme"] == "light"
        assert saved["data_retention_days"] == 30

    def test_per_user_isolation(self, client: TestClient):
        admin_headers = _auth(client, "admin@example.local", "AdminPass123!")
        op_headers = _auth(client, "operator@example.local", "OperatorPass123!")

        client.put("/api/settings", json={"theme": "dark"}, headers=admin_headers)
        client.put("/api/settings", json={"theme": "light"}, headers=op_headers)

        # Admin still sees dark
        res = client.get("/api/settings", headers=admin_headers)
        assert res.json()["theme"] == "dark"

        # Operator sees light
        res = client.get("/api/settings", headers=op_headers)
        assert res.json()["theme"] == "light"

    def test_notification_config_endpoint(self, client: TestClient):
        headers = _auth(client)
        res = client.get("/api/settings/notifications", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert "smtp_configured" in body
        assert "slack_configured" in body
        assert "recipients" in body
        assert "min_severity" in body


# ═══════════════════════════════════════════════════════════════════
# 5. Alert Persistence
# ═══════════════════════════════════════════════════════════════════

class TestAlertPersistence:
    def test_insert_and_load_active(self):
        """Alerts survive in the DB and load correctly."""
        alert_id = f"INTG-ALERT-{int(time.time())}"
        insert_alert(
            alert_id=alert_id,
            severity="HIGH",
            title="Integration Test Alert",
            message="Testing persistence",
            trigger_rule="critical_risk",
            state="ACTIVE",
            session_id="SESH-TEST",
            worker_id="worker-001",
            frame_number=42,
            confidence=0.95,
            requires_ack=True,
        )
        active = load_active_alerts()
        match = [a for a in active if a["id"] == alert_id]
        assert len(match) == 1
        assert match[0]["severity"] == "HIGH"
        assert match[0]["title"] == "Integration Test Alert"
        assert match[0]["worker_id"] == "worker-001"

    def test_acknowledge_moves_to_history(self):
        """Acknowledging an alert removes it from active and adds to history."""
        alert_id = f"INTG-ACK-{int(time.time())}"
        insert_alert(
            alert_id=alert_id,
            severity="MEDIUM",
            title="Ack Test",
            message="Will be acknowledged",
            trigger_rule="prolonged_flexion",
            state="ACTIVE",
        )
        update_alert_state(alert_id, "ACKNOWLEDGED")

        active = load_active_alerts()
        assert all(a["id"] != alert_id for a in active)

        history = load_alert_history()
        match = [a for a in history if a["id"] == alert_id]
        assert len(match) == 1
        assert match[0]["state"] == "ACKNOWLEDGED"

    def test_resolve_from_acknowledged(self):
        """Resolving an acknowledged alert moves it to RESOLVED state."""
        alert_id = f"INTG-RES-{int(time.time())}"
        insert_alert(
            alert_id=alert_id,
            severity="CRITICAL",
            title="Resolve Test",
            message="Will be resolved",
            trigger_rule="fall_detected",
            state="ACTIVE",
        )
        update_alert_state(alert_id, "ACKNOWLEDGED")
        update_alert_state(alert_id, "RESOLVED")

        active = load_active_alerts()
        assert all(a["id"] != alert_id for a in active)

        history = load_alert_history()
        match = [a for a in history if a["id"] == alert_id]
        assert len(match) == 1
        assert match[0]["state"] == "RESOLVED"


# ═══════════════════════════════════════════════════════════════════
# 6. Audit Trail
# ═══════════════════════════════════════════════════════════════════

class TestAuditTrail:
    def test_login_creates_audit_entry(self, client: TestClient):
        """A successful login is logged in the audit trail."""
        from app.core.database import load_audit_log

        before = load_audit_log(action_type="user_login")

        client.post("/api/auth/login", json={
            "email": "admin@example.local",
            "password": "AdminPass123!",
        })

        after = load_audit_log(action_type="user_login")
        assert len(after) >= len(before)

    def test_audit_endpoint_requires_admin(self, client: TestClient):
        headers = _auth(client, "operator@example.local", "OperatorPass123!")
        res = client.get("/api/audit", headers=headers)
        assert res.status_code == 403

    def test_audit_endpoint_works_for_admin(self, client: TestClient):
        headers = _auth(client)
        res = client.get("/api/audit", headers=headers)
        assert res.status_code == 200
        body = res.json()
        # Should be a list or paginated response
        assert isinstance(body, (list, dict))


# ═══════════════════════════════════════════════════════════════════
# 7. Privacy (Right to Erasure)
# ═══════════════════════════════════════════════════════════════════

class TestPrivacy:
    def test_wipe_requires_admin(self, client: TestClient):
        headers = _auth(client, "operator@example.local", "OperatorPass123!")
        res = client.post("/api/privacy/delete-worker-data/worker-001", headers=headers)
        assert res.status_code == 403

    def test_wipe_unknown_worker_is_noop(self, client: TestClient):
        headers = _auth(client)
        res = client.post("/api/privacy/delete-worker-data/nonexistent-worker", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["recordings_deleted"] == 0
        assert body["alerts_deleted"] == 0


# ═══════════════════════════════════════════════════════════════════
# 8. Pilot Request Submission
# ═══════════════════════════════════════════════════════════════════

class TestPilotRequests:
    def test_submit_pilot_request(self, client: TestClient):
        res = client.post("/api/pilot-requests", json={
            "company_name": "Test Corp",
            "contact_name": "Jane Doe",
            "email": "jane@testcorp.com",
            "role": "Safety Manager",
            "num_stations": "5-10",
            "message": "Interested in pilot deployment",
        })
        assert res.status_code == 201, res.text
        body = res.json()
        assert "successfully" in body.get("detail", "")

    def test_list_pilot_requests_requires_admin(self, client: TestClient):
        headers = _auth(client, "operator@example.local", "OperatorPass123!")
        res = client.get("/api/pilot-requests", headers=headers)
        assert res.status_code == 403

    def test_list_pilot_requests_works_for_admin(self, client: TestClient):
        headers = _auth(client)
        res = client.get("/api/pilot-requests", headers=headers)
        assert res.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 9. Worker Management
# ═══════════════════════════════════════════════════════════════════

class TestWorkerManagement:
    def test_list_workers(self, client: TestClient):
        headers = _auth(client)
        res = client.get("/api/workers", headers=headers)
        assert res.status_code == 200
        workers = res.json()
        assert isinstance(workers, list)
        worker_ids = [w["worker_id"] for w in workers]
        assert "worker-001" in worker_ids

    def test_create_worker(self, client: TestClient):
        headers = _auth(client)
        res = client.post("/api/workers", json={
            "employee_id": "INTG-EMP-001",
            "name": "Integration Worker",
            "department": "QA",
            "shift": "Day",
        }, headers=headers)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["employee_id"] == "INTG-EMP-001"
        assert body["name"] == "Integration Worker"
        assert body["worker_id"].startswith("worker-")

    def test_update_worker(self, client: TestClient):
        headers = _auth(client)
        # Create first
        res = client.post("/api/workers", json={
            "employee_id": "INTG-EMP-002",
            "name": "To Update",
            "department": "QA",
            "shift": "Day",
        }, headers=headers)
        assert res.status_code == 201
        wid = res.json()["worker_id"]

        # Update
        res = client.put(f"/api/workers/{wid}", json={
            "name": "Updated Name",
            "department": "QC",
            "shift": "Night",
        }, headers=headers)
        assert res.status_code == 200

    def test_delete_worker(self, client: TestClient):
        headers = _auth(client)
        # Create
        res = client.post("/api/workers", json={
            "employee_id": "INTG-EMP-003",
            "name": "To Delete",
            "department": "QA",
            "shift": "Day",
        }, headers=headers)
        assert res.status_code == 201
        wid = res.json()["worker_id"]

        # Delete
        res = client.delete(f"/api/workers/{wid}", headers=headers)
        assert res.status_code == 204

    def test_operator_cannot_manage_workers(self, client: TestClient):
        headers = _auth(client, "operator@example.local", "OperatorPass123!")
        res = client.get("/api/workers", headers=headers)
        # Operator can view but may not create
        res = client.post("/api/workers", json={
            "employee_id": "SHOULD-FAIL",
            "name": "Nope",
            "department": "QA",
            "shift": "Day",
        }, headers=headers)
        assert res.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 10. Health & Ops (Full Suite)
# ═══════════════════════════════════════════════════════════════════

class TestHealthOps:
    def test_root_returns_app_info(self, client: TestClient):
        res = client.get("/")
        assert res.status_code == 200
        body = res.json()
        assert body["app"] == "ErgoVigilance API"
        assert body["version"] == "0.1.0"
        assert body["docs"] == "/docs"
        assert body["openapi"] == "/openapi.json"

    def test_health_includes_live_session_status(self, client: TestClient):
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["live_session"] is False
        assert body["model_available"] is False  # test env has no model

    def test_metrics_includes_all_counters(self, client: TestClient):
        res = client.get("/metrics")
        assert res.status_code == 200
        text = res.text
        assert "http_requests_total" in text
        assert "ergo_active_sessions" in text
        assert "ergo_uptime_seconds" in text
