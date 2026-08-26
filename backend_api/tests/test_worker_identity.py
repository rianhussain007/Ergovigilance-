"""Tests for worker identity controls: consent enforcement in face matching,
badge/QR assignment, and the badge check-in endpoints.

The core guarantee under test: a worker who denies consent (or chooses
badge/off identity) is immediately excluded from face-recognition matching —
the matcher itself enforces this, not just the UI.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.database import (
    get_worker,
    get_worker_by_badge_id,
    init_local_database,
    insert_worker,
    set_worker_badge,
    update_worker_identity,
)
from app.services import worker_faces

init_local_database()  # apply migrations so the workers table has the identity columns


def _make_worker(prefix: str = "test") -> str:
    """Create a throwaway worker and return its worker_id."""
    return insert_worker(f"EMP-{prefix.upper()}", "Test Person", "Assembly", "Day")


def _cleanup(wid: str) -> None:
    from app.core.database import delete_worker, delete_alerts_for_worker

    delete_alerts_for_worker(wid)
    worker_faces.delete_worker_face(wid)
    delete_worker(wid)


class TestConsentEnforcement:
    def test_denied_consent_erases_biometrics_via_api(self, client: TestClient):
        """Consent withdrawal must PHYSICALLY erase stored face samples via the
        API (not just exclude them from matching) — privacy-first erasure."""
        wid = _make_worker("erase1")
        headers = _auth_headers(client)
        try:
            import numpy as np
            from datetime import datetime, timezone

            from app.core.database import get_connection

            # Insert a synthetic sample directly (embedding_from_image is
            # model-backed); the API erasure path under test is what matters.
            emb = np.zeros(128, dtype="float32")
            emb[0] = 1.0
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO worker_face_samples (worker_id, embedding, enrolled_at, sample_index) VALUES (?, ?, ?, 0)",
                    (wid, json.dumps(emb.tolist()), datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            assert any(r["worker_id"] == wid for r in worker_faces.list_enrolled_embeddings())

            res = client.patch(
                f"/api/workers/{wid}/identity",
                json={"identity_mode": "face", "consent_status": "denied"},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            # Erasure, not just exclusion: the samples table is empty now.
            assert worker_faces.get_face_status(wid)["enrolled"] is False
            assert all(r["worker_id"] != wid for r in worker_faces.list_enrolled_embeddings())
        finally:
            _cleanup(wid)

    def test_denied_consent_excludes_from_face_matching(self, monkeypatch):
        wid = _make_worker("deny1")
        try:
            # Enroll a synthetic embedding so the worker would normally match.
            monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: __import__(
                "numpy", fromlist=["array"]
            ).array([1.0] + [0.0] * 127, dtype="float32"))
            worker_faces.enroll_worker(wid, b"fake")

            # Initially the worker appears in the match pool.
            assert any(r["worker_id"] == wid for r in worker_faces.list_enrolled_embeddings())

            # Deny consent -> embedding must disappear from the pool.
            update_worker_identity(wid, "face", "denied")
            assert all(r["worker_id"] != wid for r in worker_faces.list_enrolled_embeddings())
        finally:
            _cleanup(wid)

    def test_badge_mode_excludes_from_face_matching(self, monkeypatch):
        wid = _make_worker("badge1")
        try:
            monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: __import__(
                "numpy", fromlist=["array"]
            ).array([1.0] + [0.0] * 127, dtype="float32"))
            worker_faces.enroll_worker(wid, b"fake")
            assert any(r["worker_id"] == wid for r in worker_faces.list_enrolled_embeddings())

            # Badge-only identity -> face matching must stop.
            update_worker_identity(wid, "badge", "pending")
            assert all(r["worker_id"] != wid for r in worker_faces.list_enrolled_embeddings())
        finally:
            _cleanup(wid)

    def test_granted_face_mode_keeps_worker_in_pool(self, monkeypatch):
        wid = _make_worker("grant1")
        try:
            monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: __import__(
                "numpy", fromlist=["array"]
            ).array([1.0] + [0.0] * 127, dtype="float32"))
            worker_faces.enroll_worker(wid, b"fake")
            update_worker_identity(wid, "face", "granted")
            assert any(r["worker_id"] == wid for r in worker_faces.list_enrolled_embeddings())
        finally:
            _cleanup(wid)


class TestBadgeHelpers:
    def test_badge_round_trip(self):
        wid = _make_worker("badge2")
        try:
            assert set_worker_badge(wid, "BADGE-1042") is True
            row = get_worker(wid)
            assert row["badge_id"] == "BADGE-1042"
            found = get_worker_by_badge_id("badge-1042")  # case-insensitive
            assert found is not None and found["worker_id"] == wid
            # Clear it.
            set_worker_badge(wid, None)
            assert get_worker(wid)["badge_id"] is None
        finally:
            from app.core.database import delete_worker

            delete_worker(wid)

    def test_identity_mode_persisted(self):
        wid = _make_worker("mode1")
        try:
            update_worker_identity(wid, "badge", "granted")
            row = get_worker(wid)
            assert row["identity_mode"] == "badge"
            assert row["consent_status"] == "granted"
        finally:
            from app.core.database import delete_worker

            delete_worker(wid)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _auth_headers(client: TestClient) -> dict:
    res = client.post(
        "/api/auth/login",
        json={"email": "admin@example.local", "password": "AdminPass123!"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


class TestBadgeEndpoints:
    def test_identity_patch_and_badge_qr(self, client: TestClient):
        wid = _make_worker("api1")
        headers = _auth_headers(client)
        try:
            res = client.patch(
                f"/api/workers/{wid}/identity",
                json={"identity_mode": "badge", "consent_status": "granted"},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["identity_mode"] == "badge"
            assert body["consent_status"] == "granted"

            res = client.put(
                f"/api/workers/{wid}/badge",
                json={"badge_id": "BADGE-77"},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            assert res.json()["badge_id"] == "BADGE-77"

            # QR endpoint returns an SVG.
            res = client.get(f"/api/workers/{wid}/badge/qr", headers=headers)
            assert res.status_code == 200
            assert "image/svg" in res.headers["content-type"]
            assert "<svg" in res.text

            # Badge check-in resolves the worker.
            res = client.post(
                "/api/workers/identify-badge",
                json={"code": "BADGE-77"},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            assert res.json()["worker_id"] == wid

            # Unknown badge -> 404.
            res = client.post(
                "/api/workers/identify-badge",
                json={"code": "NOPE-000"},
                headers=headers,
            )
            assert res.status_code == 404
        finally:
            from app.core.database import delete_worker

            delete_worker(wid)

    def test_duplicate_badge_conflict(self, client: TestClient):
        wid1 = _make_worker("dup1")
        wid2 = _make_worker("dup2")
        headers = _auth_headers(client)
        try:
            res = client.put(
                f"/api/workers/{wid1}/badge",
                json={"badge_id": "DUP-BADGE"},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            res = client.put(
                f"/api/workers/{wid2}/badge",
                json={"badge_id": "DUP-BADGE"},
                headers=headers,
            )
            assert res.status_code == 409
        finally:
            from app.core.database import delete_worker

            delete_worker(wid1)
            delete_worker(wid2)

    def test_invalid_identity_mode_rejected(self, client: TestClient):
        wid = _make_worker("inv1")
        headers = _auth_headers(client)
        try:
            res = client.patch(
                f"/api/workers/{wid}/identity",
                json={"identity_mode": "telepathy", "consent_status": "granted"},
                headers=headers,
            )
            assert res.status_code == 422
        finally:
            from app.core.database import delete_worker

            delete_worker(wid)
