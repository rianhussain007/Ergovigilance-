"""Capture before/after Session History drawer screenshots for status fix."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports" / "screenshots"
SESSION_ID = "SESH-20260708-E807"
BASE = "http://localhost:3000"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def login_token() -> str:
    data = json.dumps({"email": "admin@example.local", "password": "AdminPass123!"}).encode()
    req = urllib.request.Request(
        "http://localhost:8000/api/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req))["token"]


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    auth = {
        "token": login_token(),
        "user": {"id": 4, "email": "admin@example.local", "role": "admin"},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"{BASE}/login")
        page.evaluate(
            "(auth) => localStorage.setItem('ergovigilance_auth', JSON.stringify(auth))",
            auth,
        )
        page.goto(f"{BASE}/sessions")
        page.wait_for_selector("text=Session History", timeout=30000)

        def open_drawer() -> None:
            page.get_by_role("table").get_by_text(SESSION_ID, exact=True).click()
            page.wait_for_selector("text=Session Metadata", timeout=20000)
            page.wait_for_timeout(700)

        def close_drawer() -> None:
            page.locator(".fixed.inset-0.bg-black\\/50").click(position={"x": 8, "y": 8})
            page.wait_for_timeout(500)

        # BEFORE: strip status from API response (simulates pre-fix frontend behavior)
        def strip_status(route):
            response = route.fetch()
            body = response.json()
            body.pop("status", None)
            route.fulfill(
                status=response.status,
                headers=response.headers,
                content_type="application/json",
                body=json.dumps(body),
            )

        page.route(f"**/api/sessions/{SESSION_ID}", strip_status)
        open_drawer()
        before = SHOTS / "frontend_before_no_replay_button.png"
        page.screenshot(path=str(before), full_page=False)
        has_button_before = page.get_by_role("button", name="Open in Replay").count() > 0
        print(f"BEFORE: {before} | Open in Replay visible: {has_button_before}")

        page.unroute(f"**/api/sessions/{SESSION_ID}")
        close_drawer()
        open_drawer()
        after = SHOTS / "frontend_after_replay_button.png"
        page.wait_for_selector("button:has-text('Open in Replay')", timeout=20000)
        page.screenshot(path=str(after), full_page=False)
        has_button_after = page.get_by_role("button", name="Open in Replay").count() > 0
        print(f"AFTER:  {after} | Open in Replay visible: {has_button_after}")

        browser.close()


if __name__ == "__main__":
    main()
