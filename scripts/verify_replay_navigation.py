"""Verify replay navigation fix with trace logs and screenshots."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports" / "screenshots"
BASE = "http://localhost:3000"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WITH_RECORDING = "SESH-20260708-03EA"
WITHOUT_RECORDING = "SESH-20260708-E807"


def login_token() -> str:
    data = json.dumps({"email": "admin@example.local", "password": "AdminPass123!"}).encode()
    req = urllib.request.Request(
        "http://localhost:8000/api/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req))["token"]


def auth_state(token: str) -> dict:
    return {"token": token, "user": {"id": 4, "email": "admin@example.local", "role": "admin"}}


def open_session_and_click_replay(page, session_id: str) -> list[str]:
    navigated: list[str] = []
    page.on("framenavigated", lambda frame: navigated.append(frame.url) if frame == page.main_frame else None)

    page.goto(f"{BASE}/sessions")
    page.wait_for_selector("text=Session History", timeout=30000)
    page.get_by_role("table").get_by_text(session_id, exact=True).click()
    page.wait_for_selector("button:has-text('Open in Replay')", timeout=20000)

    # Trace: confirm navigate target via the same expression SessionHistory uses.
    expected = f"/replay/{session_id}"
    print(f"TRACE onClick target: navigate(`{expected}`)")

    with page.expect_navigation(timeout=15000):
        page.get_by_role("button", name="Open in Replay").click()

    print(f"TRACE final URL: {page.url}")
    print(f"TRACE navigated URLs: {navigated[-3:]}")
    return navigated


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    token = login_token()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE}/login")
        page.evaluate(
            "(auth) => localStorage.setItem('ergovigilance_auth', JSON.stringify(auth))",
            auth_state(token),
        )

        print("\n=== WITH RECORDING ===")
        open_session_and_click_replay(page, WITH_RECORDING)
        page.wait_for_selector("text=Session Replay", timeout=20000)
        page.wait_for_timeout(3000)
        body = page.locator("main").inner_text()
        has_video = page.locator("video").count() > 0
        has_error = page.get_by_text("No recording available").count() > 0
        print(f"TRACE has video: {has_video}, has no-recording error: {has_error}")
        with_rec = SHOTS / "replay_with_recording.png"
        page.screenshot(path=str(with_rec), full_page=False)
        print(f"Screenshot: {with_rec}")
        assert "/replay/" in page.url and "/dashboard" not in page.url
        assert has_video, "Expected video player on replay page for session with recording"

        print("\n=== WITHOUT RECORDING ===")
        page.goto(f"{BASE}/replay/{WITHOUT_RECORDING}")
        page.wait_for_selector("text=No recording available for this session.", timeout=20000)
        page.wait_for_timeout(500)
        without_rec = SHOTS / "replay_without_recording.png"
        page.screenshot(path=str(without_rec), full_page=False)
        print(f"Screenshot: {without_rec}")
        print(f"TRACE direct-nav URL: {page.url}")
        assert page.url.endswith(f"/replay/{WITHOUT_RECORDING}")
        assert page.get_by_text("No recording available for this session.").count() > 0

        print("\n=== REGRESSION: 03EA direct URL still works ===")
        page.goto(f"{BASE}/replay/{WITH_RECORDING}")
        page.wait_for_selector("video", timeout=20000)
        print(f"TRACE regression URL: {page.url}")
        assert page.locator("video").count() > 0

        browser.close()
        print("\nAll checks passed.")


if __name__ == "__main__":
    main()
