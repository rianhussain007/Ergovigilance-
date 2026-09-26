"""Consent tenant scoping (sell-readiness QA: cross-tenant leak).

The consent endpoints previously ignored organizations entirely: every
org listed every worker and could grant/deny/withdraw for anyone,
including workers that do not exist (ghost rows). Covered here.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.core.database import init_local_database
    from app.main import app

    init_local_database()
    return TestClient(app)


def _signup(client: TestClient, tag: str) -> dict:
    email = f"consent-{tag}-{uuid.uuid4().hex[:8]}@acme-manufacturing.com"
    resp = client.post(
        "/api/auth/signup",
        json={
            "organization_name": f"Consent {tag}",
            "email": email,
            "password": "ConsentPass123!",
            "agree_terms": True,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_worker(client: TestClient, token: str, tag: str) -> str:
    emp = f"CTMP-{tag}-{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/workers",
        json={"employee_id": emp, "name": f"CT {tag}", "department": "QA", "shift": "Day"},
        headers=_auth(token),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json().get("worker_id", emp)


def test_grant_deny_withdraw_roundtrip(client: TestClient):
    data = _signup(client, "roundtrip")
    headers = _auth(data["token"])
    wid = _make_worker(client, data["token"], "roundtrip")

    grant = client.post(
        f"/api/consent/worker-consents/{wid}/grant",
        json={"purposes": ["monitoring"], "data_categories": ["pose"]},
        headers=headers,
    )
    assert grant.status_code == 200, grant.text

    listed = client.get("/api/consent/worker-consents", headers=headers)
    assert listed.status_code == 200
    mine = [w for w in listed.json()["workers"] if w["worker_id"] == wid]
    assert mine and mine[0]["consent_status"] == "granted"

    deny = client.post(f"/api/consent/worker-consents/{wid}/deny", headers=headers)
    assert deny.status_code == 200

    withdraw = client.post(f"/api/consent/worker-consents/{wid}/withdraw", headers=headers)
    assert withdraw.status_code == 200
    listed2 = client.get("/api/consent/worker-consents", headers=headers)
    mine2 = [w for w in listed2.json()["workers"] if w["worker_id"] == wid]
    assert mine2 and mine2[0]["consent_status"] == "withdrawn"

    client.delete(f"/api/workers/{wid}", headers=headers)


def test_foreign_org_worker_is_invisible(client: TestClient):
    owner = _signup(client, "owner")
    other = _signup(client, "other")
    wid = _make_worker(client, owner["token"], "foreign")

    for method in ("grant", "deny", "withdraw"):
        if method == "grant":
            resp = client.post(
                f"/api/consent/worker-consents/{wid}/{method}",
                json={"purposes": ["x"], "data_categories": ["y"]},
                headers=_auth(other["token"]),
            )
        else:
            resp = client.post(
                f"/api/consent/worker-consents/{wid}/{method}",
                headers=_auth(other["token"]),
            )
        assert resp.status_code == 404, (method, resp.text)

    listed = client.get("/api/consent/worker-consents", headers=_auth(other["token"]))
    assert all(w["worker_id"] != wid for w in listed.json()["workers"])

    client.delete(f"/api/workers/{wid}", headers=_auth(owner["token"]))


def test_ghost_worker_grant_is_404(client: TestClient):
    data = _signup(client, "ghost")
    resp = client.post(
        "/api/consent/worker-consents/WORKER-DOES-NOT-EXIST/grant",
        json={"purposes": ["x"], "data_categories": ["y"]},
        headers=_auth(data["token"]),
    )
    assert resp.status_code == 404
