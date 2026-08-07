"""Tests for the admin per-worker data deletion endpoint (privacy wipe)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import insert_alert, load_active_alerts


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _recordings_dir() -> Path:
    return Path(os.environ["RECORDINGS_DIR"])


def _admin_token(client: TestClient) -> str:
    res = client.post("/api/auth/login", json={"email": "admin@example.local", "password": "AdminPass123!"})
    assert res.status_code == 200
    return res.json()["token"]


def test_wipe_removes_recordings_and_alerts(client: TestClient):
    token = _admin_token(client)

    # Create a recording dir + a DB alert for a worker.
    worker_id = "privacy-test-worker"
    session_dir = _recordings_dir() / worker_id / "20260101_000000_000_TEST"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "summary.json").write_text('{"session_timestamp": "20260101_000000_000", "worker_id": "%s"}' % worker_id)
    (session_dir / "original.mp4").write_bytes(b"fake-video-bytes")

    insert_alert(
        alert_id="PRIV-ALERT-1",
        severity="HIGH",
        title="Test alert",
        message="privacy wipe test",
        trigger_rule="critical_risk",
        state="ACTIVE",
        worker_id=worker_id,
    )

    res = client.post(f"/api/privacy/delete-worker-data/{worker_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["recordings_deleted"] == 1
    assert body["recordings_freed_bytes"] > 0
    assert body["alerts_deleted"] == 1

    assert not session_dir.exists()
    assert all(a["worker_id"] != worker_id for a in load_active_alerts())


def test_wipe_rejects_non_admin(client: TestClient):
    res = client.post("/api/auth/login", json={"email": "operator@example.local", "password": "OperatorPass123!"})
    assert res.status_code == 200
    token = res.json()["token"]

    res = client.post("/api/privacy/delete-worker-data/some-worker", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_wipe_rejects_path_traversal(client: TestClient):
    """Encoded slashes are normalized away by the router → 404 before the guard.

    The endpoint additionally re-validates worker_id with Path(...).name, so a
    traversal-style id is rejected even if it somehow reaches the handler.
    """
    token = _admin_token(client)
    res = client.post("/api/privacy/delete-worker-data/..%2F..%2Fetc", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_wipe_unknown_worker_is_noop(client: TestClient):
    token = _admin_token(client)
    res = client.post("/api/privacy/delete-worker-data/does-not-exist", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["recordings_deleted"] == 0
