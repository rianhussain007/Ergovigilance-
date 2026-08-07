# -*- coding: utf-8 -*-
"""Inspect ExportsCenter rendered DOM — alignment + JSON export check."""
import sys, os, json
sys.path.insert(0, "C:/GGS_intership/posture_analysis/backend_api")
os.environ["PYTHONIOENCODING"] = "utf-8"

from playwright.sync_api import sync_playwright
from app.core.security import create_access_token, AuthenticatedUser

FRONTEND = "http://localhost:5173"
TOKEN = create_access_token(AuthenticatedUser(id=4, email='admin@example.local', role='admin'))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # Inject auth into localStorage in the format AuthProvider expects
    import json as _json
    auth_data = _json.dumps({
        "token": TOKEN,
        "user": {"email": "admin@example.local", "role": "admin"},
    })
    page.add_init_script(
        "window.localStorage.setItem('ergovigilance_auth', " + _json.dumps(auth_data) + ");"
        "window.sessionStorage.setItem('sesh_id', 'SESH-2026-07-17_11-45-23');"
    )

    page.goto(f"{FRONTEND}/monitoring", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)

    # Dump URL in case of redirect
    print(f"Current URL: {page.url}")

    # Try clicking Export Data
    for sel in ["button:has-text('Export Data')", "button:has-text('Export')"]:
        btn = page.locator(sel)
        if btn.count() > 0:
            print(f"Clicked: {sel}")
            btn.first.click()
            break
    else:
        print("NO EXPORT BUTTON FOUND")
        page.screenshot(path="C:\\GGS_intership\\posture_analysis\\no_export_btn.png")
        browser.close()
        exit(1)

    page.wait_for_timeout(1500)
    page.screenshot(path="C:\\GGS_intership\\posture_analysis\\exports_modal.png")

    # ---- Inspect buttons ----
    btns = page.locator(".fixed.inset-0.z-50 button.w-full")
    count = btns.count()
    print(f"\n=== Found {count} export buttons ===\n")

    data = []
    for i in range(count):
        b = btns.nth(i)
        box = b.bounding_box()
        label = b.locator("p").first.text_content()
        icon = b.locator(".w-9\\.h-9")
        icon_box = icon.bounding_box() if icon.count() > 0 else None
        dot = b.locator(".w-2\\.h-2")
        dot_box = dot.bounding_box() if dot.count() > 0 else None
        check = b.locator(".w-4\\.h-4.text-green-400")
        check_box = check.bounding_box() if check.count() > 0 else None
        has_star = b.locator("text=*").count() > 0
        text_div = b.locator("div.flex-1")
        fs = text_div.evaluate("el => getComputedStyle(el).fontSize") if text_div.count() > 0 else "?"
        lh = text_div.evaluate("el => getComputedStyle(el).lineHeight") if text_div.count() > 0 else "?"

        entry = {
            "i": i, "label": label.strip() if label else f"btn{i}",
            "box": box, "icon": icon_box, "dot": dot_box, "check": check_box,
            "has_star": has_star, "fontSize": fs, "lineHeight": lh,
        }
        data.append(entry)

        print(f"Button {i}: \"{entry['label']}\"")
        print(f"  pos=({box['x']:.0f},{box['y']:.0f}) size={box['width']:.0f}x{box['height']:.0f}")
        if icon_box:
            print(f"  icon  @ ({icon_box['x']:.0f},{icon_box['y']:.0f}) {icon_box['width']:.0f}x{icon_box['height']:.0f}  offsetFromButton=({icon_box['x']-box['x']:.0f},{icon_box['y']-box['y']:.0f})")
        if entry['has_star']:
            print(f"  MARKER: * (placeholder)")
        if dot_box:
            print(f"  dot   @ ({dot_box['x']:.0f},{dot_box['y']:.0f}) {dot_box['width']:.0f}x{dot_box['height']:.0f}")
        if check_box:
            print(f"  check @ ({check_box['x']:.0f},{check_box['y']:.0f}) {check_box['width']:.0f}x{check_box['height']:.0f}")

    # ---- Consistency analysis ----
    widths = [d['box']['width'] for d in data if d['box']]
    heights = [d['box']['height'] for d in data if d['box']]
    icon_tops = [d['icon']['y'] - d['box']['y'] for d in data if d['icon'] and d['box']]
    dot_tops = [d['dot']['y'] - d['box']['y'] for d in data if d['dot'] and d['box']]

    print(f"\n=== CONSISTENCY ===")
    print(f"Widths : {[f'{w:.0f}' for w in widths]}  diff={max(widths)-min(widths):.0f}px")
    print(f"Heights: {[f'{h:.0f}' for h in heights]}  diff={max(heights)-min(heights):.0f}px")
    if max(widths)-min(widths) > 1:
        print("⚠️ WIDTH INCONSISTENCY")
    if max(heights)-min(heights) > 1:
        print("⚠️ HEIGHT INCONSISTENCY")
    if icon_tops and max(icon_tops)-min(icon_tops) > 1:
        print(f"⚠️ ICON VERTICAL MISALIGNMENT (offsets: {[f'{t:.0f}' for t in icon_tops]})")
    if dot_tops and max(dot_tops)-min(dot_tops) > 1:
        print(f"⚠️ DOT VERTICAL MISALIGNMENT (offsets: {[f'{t:.0f}' for t in dot_tops]})")

    # ---- Test JSON export ----
    print(f"\n=== JSON EXPORT TEST ===")
    json_btn = page.locator("button:has-text('Export as JSON')")
    if json_btn.count() > 0:
        has_place = json_btn.locator("text=*").count()
        print(f"Placeholder marker (*): {' YES' if has_place > 0 else ' NO (REAL)'}")

        # Hook to capture download
        with page.expect_download(timeout=5000) as dl_info:
            json_btn.click()
        dl = dl_info.value
        print(f"Download triggered: {dl.suggested_filename}")

        # Also check no toast appeared
        toast = page.locator("[role='alert'], .toast, .fixed")
        if toast.count() > 0:
            txt = toast.first.text_content()
            if 'coming soon' in txt.lower() or 'placeholder' in txt.lower():
                print(f"⚠️ GOT PLACEHOLDER TOAST: {txt}")
            else:
                print(f"Toast (expected success): {txt}")
        else:
            print("No toast — export completed silently (expected for working export)")
    else:
        print("JSON button not found!")

    browser.close()
