"""Fail-closed verification for repository-backed API endpoints.

The test environment runs with an invalid
POSE_MODEL_PATH, so the live monitoring service is never initialized. Every
endpoint that depends on the repository must return HTTP 503 (never silently
serve mock data) — this is the product's core fail-closed guarantee.

Also verifies that live-service-only endpoints fail gracefully (500 with a
clear message) rather than crashing.
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


# Endpoints that resolve the repository before touching the live service.
REPO_BACKED_ENDPOINTS = [
    ("GET", "/api/dashboard"),
    ("GET", "/api/session/latest"),
    ("GET", "/api/sessions"),
    ("GET", "/api/sessions/nonexistent-session"),
    ("GET", "/api/cameras"),
    ("GET", "/api/workstations"),
    ("GET", "/api/context/snapshot"),
    ("GET", "/api/reports"),
    ("GET", "/api/deployment"),
    ("GET", "/api/manager"),
]


class TestRepoBackedEndpointsFailClosed:
    @pytest.mark.parametrize("method,path", REPO_BACKED_ENDPOINTS)
    def test_repo_backed_endpoint_fails_closed(self, client: TestClient, method: str, path: str):
        """Without the live service, repo-backed endpoints return 503, not mock data."""
        headers = _auth_headers(client)
        res = client.request(method, path, headers=headers)
        assert res.status_code == 503, (
            f"{method} {path} expected 503, got {res.status_code}: {res.text[:200]}"
        )
        assert "unavailable" in res.json()["detail"].lower()

    def test_repo_backed_endpoints_unauthenticated(self, client: TestClient):
        """Unauthenticated requests to repo-backed endpoints do NOT leak data.

        Known behavior (documented finding): the repository dependency resolves
        before auth, so an unauthenticated request returns 503 rather than 401.
        This reveals service unavailability but never any data. See QA_REPORT.md
        for the recommended fix (reorder dependencies so auth runs first).
        """
        res = client.get("/api/dashboard")
        assert res.status_code in (401, 403, 503)
        # No data is ever returned in the body regardless of status.
        assert "liveStatus" not in res.text


class TestLiveServiceEndpointsFailClosed:
    """Endpoints that depend on the live service must fail closed with 503 when
    the service is not initialized — never an unhandled 500 stack trace."""

    # (method, path, body) — body is the minimal valid payload for POSTs so the
    # request passes schema validation and reaches the service-unavailable guard.
    LIVE_SERVICE_ENDPOINTS = [
        ("GET", "/api/session/status", None),
        ("GET", "/api/session/timeline/recent", None),
        ("POST", "/api/session/observation", {"note": "qa"}),
        ("POST", "/api/session/override", {"risk_level": "MEDIUM"}),
        ("GET", "/api/predictions/next-window", None),
        ("GET", "/api/predictions/session-forecast", None),
        ("GET", "/api/setup/status", None),
        ("POST", "/api/session/start", {"camera_index": 0}),
        ("POST", "/api/session/stop", None),
    ]

    @pytest.mark.parametrize("method,path,body", LIVE_SERVICE_ENDPOINTS)
    def test_live_service_endpoint_fails_closed(self, client: TestClient, method: str, path: str, body):
        headers = _auth_headers(client)
        res = client.request(method, path, headers=headers, json=body)
        assert res.status_code == 503, (
            f"{method} {path} expected 503 (service not initialized), got {res.status_code}: {res.text[:200]}"
        )
        assert "unavailable" in res.json()["detail"].lower()
