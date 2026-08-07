"""Live browser test for the AI Assistant panel — extended wait for streaming."""

from playwright.sync_api import sync_playwright
import time
import os

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

def test_ai_assistant():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        print("[1] Navigating...")
        page.goto("http://localhost:3000", wait_until="networkidle")
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
    test_ai_assistant()
