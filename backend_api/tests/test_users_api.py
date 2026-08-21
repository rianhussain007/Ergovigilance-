"""Tests for the user admin API (admin-only CRUD for user accounts).

Covers:
- List/create/update/delete users (admin only)
- Role validation (invalid roles rejected)
- Duplicate email conflict (409)
- Self-deletion prevention (409)
- Password reset (custom + generated)
- Role-based access control (non-admin gets 403)
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


class TestUserList:
    def test_list_users_returns_seeded_accounts(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.get("/api/users", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        emails = [u["email"] for u in data]
        assert "admin@example.local" in emails
        assert "operator@example.local" in emails

    def test_list_users_requires_admin(self, client: TestClient):
        headers = _auth_headers(client, email="operator@example.local", password="OperatorPass123!")
        res = client.get("/api/users", headers=headers)
        assert res.status_code == 403

    def test_list_users_unauthenticated(self, client: TestClient):
        res = client.get("/api/users")
        assert res.status_code in (401, 403)


class TestUserCreate:
    def test_create_user_success(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.post(
            "/api/users",
            json={"email": "qa-create@example.local", "password": "StrongPass123!", "role": "operator"},
            headers=headers,
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["email"] == "qa-create@example.local"
        assert body["role"] == "operator"
        assert "id" in body

    def test_create_duplicate_email_conflict(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.post(
            "/api/users",
            json={"email": "admin@example.local", "password": "Whatever123!", "role": "operator"},
            headers=headers,
        )
        assert res.status_code == 409

    def test_create_invalid_role_rejected(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.post(
            "/api/users",
            json={"email": "qa-badrole@example.local", "password": "StrongPass123!", "role": "superuser"},
            headers=headers,
        )
        assert res.status_code == 400

    def test_create_weak_password_rejected(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.post(
            "/api/users",
            json={"email": "qa-weak@example.local", "password": "short", "role": "operator"},
            headers=headers,
        )
        assert res.status_code == 422

    def test_create_user_requires_admin(self, client: TestClient):
        headers = _auth_headers(client, email="supervisor@example.local", password="SupervisorPass123!")
        res = client.post(
            "/api/users",
            json={"email": "qa-noauth@example.local", "password": "StrongPass123!", "role": "operator"},
            headers=headers,
        )
        assert res.status_code == 403


class TestUserUpdate:
    def test_update_user_role(self, client: TestClient):
        headers = _auth_headers(client)
        # Create a user first
        created = client.post(
            "/api/users",
            json={"email": "qa-update@example.local", "password": "StrongPass123!", "role": "operator"},
            headers=headers,
        ).json()
        uid = created["id"]
        res = client.put(f"/api/users/{uid}", json={"role": "supervisor"}, headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["role"] == "supervisor"

    def test_update_invalid_role_rejected(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.put("/api/users/1", json={"role": "root"}, headers=headers)
        assert res.status_code == 400

    def test_update_unknown_user_404(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.put("/api/users/999999", json={"role": "operator"}, headers=headers)
        assert res.status_code == 404


class TestUserPasswordReset:
    def _create_throwaway_user(self, client: TestClient, headers: dict) -> int:
        """Create a disposable user for password-reset tests so the seeded
        accounts' credentials are never modified (which would break other
        tests that log in with them)."""
        res = client.post(
            "/api/users",
            json={"email": "qa-reset@example.local", "password": "OriginalPass123!", "role": "operator"},
            headers=headers,
        )
        assert res.status_code == 201, res.text
        return res.json()["id"]

    def test_reset_with_custom_password(self, client: TestClient):
        headers = _auth_headers(client)
        uid = self._create_throwaway_user(client, headers)
        try:
            res = client.post(
                f"/api/users/{uid}/reset-password",
                json={"password": "NewPassword123!"},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["new_password"] == "NewPassword123!"

            # The new password works for login.
            res = client.post(
                "/api/auth/login",
                json={"email": "qa-reset@example.local", "password": "NewPassword123!"},
            )
            assert res.status_code == 200, res.text
        finally:
            client.delete(f"/api/users/{uid}", headers=headers)

    def test_reset_generates_password_when_omitted(self, client: TestClient):
        headers = _auth_headers(client)
        uid = self._create_throwaway_user(client, headers)
        try:
            res = client.post(f"/api/users/{uid}/reset-password", headers=headers)
            assert res.status_code == 200, res.text
            body = res.json()
            pw = body["new_password"]
            # Generated password must be strong enough to pass login validation
            assert len(pw) >= 8
            assert any(c.islower() for c in pw)
            assert any(c.isupper() for c in pw)
            assert any(c.isdigit() for c in pw)
        finally:
            client.delete(f"/api/users/{uid}", headers=headers)

    def test_reset_unknown_user_404(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.post("/api/users/999999/reset-password", headers=headers)
        assert res.status_code == 404


class TestUserDelete:
    def test_delete_user_success(self, client: TestClient):
        headers = _auth_headers(client)
        created = client.post(
            "/api/users",
            json={"email": "qa-delete@example.local", "password": "StrongPass123!", "role": "operator"},
            headers=headers,
        ).json()
        uid = created["id"]
        res = client.delete(f"/api/users/{uid}", headers=headers)
        assert res.status_code == 204
        # Verify it's gone
        res = client.get("/api/users", headers=headers)
        emails = [u["email"] for u in res.json()]
        assert "qa-delete@example.local" not in emails

    def test_cannot_delete_own_account(self, client: TestClient):
        """Admin must not be able to delete their own account (lockout prevention)."""
        headers = _auth_headers(client)
        # Find the admin's id
        users = client.get("/api/users", headers=headers).json()
        admin = next(u for u in users if u["email"] == "admin@example.local")
        res = client.delete(f"/api/users/{admin['id']}", headers=headers)
        assert res.status_code == 409

    def test_delete_unknown_user_404(self, client: TestClient):
        headers = _auth_headers(client)
        res = client.delete("/api/users/999999", headers=headers)
        assert res.status_code == 404

    def test_delete_requires_admin(self, client: TestClient):
        headers = _auth_headers(client, email="operator@example.local", password="OperatorPass123!")
        res = client.delete("/api/users/1", headers=headers)
        assert res.status_code == 403
