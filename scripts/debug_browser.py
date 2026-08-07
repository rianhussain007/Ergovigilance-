"""Quick screenshot to see what the page looks like after navigation."""

from playwright.sync_api import sync_playwright
import time
import os

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:3000", wait_until="networkidle")
    time.sleep(2)
    page.screenshot(path=os.path.join(SCREENSHOT_DIR, "debug_page.png"))
    print("URL:", page.url)
    print("Title:", page.title())
    # Print all input elements
    inputs = page.locator("input").all()
    for i, inp in enumerate(inputs):
        print(f"Input {i}: type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")
    # Print all buttons
    buttons = page.locator("button").all()
    for i, btn in enumerate(buttons):
        txt = btn.text_content().strip()[:50]
        print(f"Button {i}: {txt}")
    browser.close()
