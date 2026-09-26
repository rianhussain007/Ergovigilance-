"""PDF export failure mapping (P0-9): missing Chromium => HTTP 503, not 500."""

import asyncio

import pytest
from fastapi import HTTPException


def _get_browser():
    from backend.services import report_pdf

    return report_pdf


def test_missing_playwright_package_maps_to_503(monkeypatch):
    report_pdf = _get_browser()
    monkeypatch.setattr(report_pdf, "_HAS_PLAYWRIGHT", False)
    monkeypatch.setattr(report_pdf, "_browser", None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(report_pdf._get_browser())

    assert exc.value.status_code == 503
    assert "playwright install chromium" in exc.value.detail


def test_launch_failure_maps_to_503(monkeypatch):
    report_pdf = _get_browser()
    monkeypatch.setattr(report_pdf, "_browser", None)

    async def _boom():
        raise RuntimeError("Executable doesn't exist: chromium-headless-shell")

    monkeypatch.setattr(report_pdf, "init_browser", _boom)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(report_pdf._get_browser())

    assert exc.value.status_code == 503
    assert "chromium-headless-shell" in exc.value.detail  # original cause kept
    assert "backend_api/Dockerfile" in exc.value.detail  # actionable fix


def test_healthy_browser_instance_is_returned(monkeypatch):
    report_pdf = _get_browser()

    class _FakeBrowser:
        def is_connected(self):
            return True

    fake = _FakeBrowser()
    monkeypatch.setattr(report_pdf, "_browser", fake)

    assert asyncio.run(report_pdf._get_browser()) is fake
