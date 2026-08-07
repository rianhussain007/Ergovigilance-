"""Live browser test for the AI Assistant panel — extended wait for streaming.

Requires a running stack (backend on :8000 + frontend on :3000 + Ollama).
When the stack is not up this prints SKIP and exits 0 instead of crashing, so
it can be part of the legacy suite without a live environment.
"""

import socket
import sys
import time
import os

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _stack_available() -> bool:
    """Check the frontend host/port parsed from FRONTEND_URL is listening."""
    from urllib.parse import urlparse

    parsed = urlparse(FRONTEND_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def test_ai_assistant():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: playwright not installed — run `pip install playwright && playwright install chromium`")
        return

    if not _stack_available():
        print(f"SKIP: frontend stack not running at {FRONTEND_URL} — start the backend + frontend first")
        return

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        print("[1] Navigating...")
        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.wait_for_url("**/login", timeout=10000)

        print("[2] Logging in...")
        inputs = page.locator("input").all()
        inputs[0].fill("admin@example.local")
        inputs[1].fill("AdminPass123!")
        page.locator("button:has-text('Sign In')").click()
        page.wait_for_url("**/", timeout=10000)
        time.sleep(2)

        print("[3] Opening AI Assistant...")
        page.locator("button:has-text('AI Assistant')").click()
        time.sleep(1)
        page.locator("text=AI Safety Assistant").wait_for(state="visible", timeout=5000)

        # Screenshot empty state
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "ai_assistant_01_empty.png"))
        print("    Screenshot: ai_assistant_01_empty.png")

        print("[4] Sending question...")
        page.locator("input[placeholder*='ergonomics' i]").fill("What triggers a high risk alert?")
        # Click the send button (last button in the panel area)
        page.locator("button:has(svg):not([disabled])").last.click()

        # Wait for loading dots to appear then disappear
        print("    Waiting for response to stream...")
        # Wait up to 30 seconds for the "done" token / response to complete
        # The response text appears in a div with bg-surface-container-higher
        # After streaming, the loading dots disappear and text appears
        
        # Poll for response text (up to 30s)
        response_text = ""
        for i in range(30):
            time.sleep(1)
            # Check for assistant message bubbles (left-aligned, surface-container-higher bg)
            msgs = page.locator("[class*='surface-container-higher']").all()
            if msgs:
                for m in msgs:
                    txt = m.text_content().strip()
                    if txt and len(txt) > 5 and "Source:" not in txt:
                        response_text = txt
                        break
            if response_text:
                break
            # Also check if loading dots are gone and sources are shown
            if i % 5 == 0:
                print(f"    Still waiting... ({i}s)")

        print(f"    Response length: {len(response_text)} chars")
        if response_text:
            print(f"    Response text: {response_text[:300]}")

        # Screenshot with response
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "ai_assistant_02_response.png"))
        print("    Screenshot: ai_assistant_02_response.png")

        # Also grab all visible text in the panel
        panel = page.locator("[class*='absolute right-0 top-0']")
        if panel.count() > 0:
            full = panel.first.inner_text()
            print(f"\n    Full panel text:\n{full[:600]}")

        print("\n[DONE]")
        browser.close()

if __name__ == "__main__":
    try:
        test_ai_assistant()
    except Exception as exc:  # noqa: BLE001 - surface live-test failures clearly
        print(f"\n[ERROR] AI Assistant live test failed: {exc}")
        sys.exit(1)
