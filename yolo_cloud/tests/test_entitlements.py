"""Camera entitlement gate (sell-readiness audit F-01).

Covers the pure gate (under/at/over/unlimited/no-org) plus proof that
``add_camera`` consults it before starting any stream.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from yolo_cloud.entitlements import check_camera_allowance


def test_no_org_identity_never_gated():
    check_camera_allowance(None, 10**6)


def test_none_limit_means_unlimited():
    check_camera_allowance({"plan": "enterprise", "max_cameras": None}, 10**6)


def test_under_limit_ok():
    check_camera_allowance({"plan": "pilot", "max_cameras": 4}, 3)


def test_at_limit_403():
    with pytest.raises(HTTPException) as exc:
        check_camera_allowance({"plan": "pilot", "max_cameras": 4}, 4)
    assert exc.value.status_code == 403
    assert "pilot" in exc.value.detail


def test_over_limit_403():
    with pytest.raises(HTTPException) as exc:
        check_camera_allowance({"plan": "cloud", "max_cameras": 20}, 21)
    assert exc.value.status_code == 403


def test_add_camera_consults_gate(monkeypatch):
    import yolo_cloud.api as api

    monkeypatch.setattr(
        api, "lookup_org_by_api_key", lambda key: {"plan": "pilot", "max_cameras": 1}
    )
    monkeypatch.setattr(
        api.storage, "get_cameras", lambda tenant_id="default": [{"camera_id": "a"}]
    )

    def _must_not_start():
        raise AssertionError("service must not start when over limit")

    monkeypatch.setattr(api, "get_cloud_service", _must_not_start)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api.add_camera(
                {"id": "b", "name": "B", "url": "rtsp://x"},
                tenant={"tenant_id": "t"},
                x_api_key="k",
            )
        )
    assert exc.value.status_code == 403


def test_add_camera_under_limit_starts(monkeypatch):
    import yolo_cloud.api as api

    monkeypatch.setattr(
        api, "lookup_org_by_api_key", lambda key: {"plan": "pilot", "max_cameras": 4}
    )
    monkeypatch.setattr(api.storage, "get_cameras", lambda tenant_id="default": [])
    monkeypatch.setattr(api.storage, "pg_enabled", lambda: False)

    class _Service:
        def add_and_start_camera(self, *args, **kwargs):
            return {"started": "b"}

    monkeypatch.setattr(api, "get_cloud_service", lambda: _Service())

    result = asyncio.run(
        api.add_camera(
            {"id": "b", "name": "B", "url": "rtsp://x"},
            tenant={"tenant_id": "t"},
            x_api_key="k",
        )
    )
    assert result == {"started": "b"}
