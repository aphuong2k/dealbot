import json, os, time
from playwright.sync_api import sync_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "dealbot", "cookies", "shopee_aff_portal.json")
raw = json.load(open(COOKIE_FILE))
cookies = []
for c in raw:
    cookies.append({
        "name": c["name"],
        "value": c["value"],
        "domain": c.get("domain", ".shopee.vn"),
        "path": c.get("path", "/"),
        "secure": True
    })

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="vi-VN"
    )
    ctx.add_cookies(cookies)
    page = ctx.new_page()

    reqs = []
    page.on("request", lambda r: reqs.append((r.method, r.url)))

    print("Navigating to https://affiliate.shopee.vn ...")
    page.goto("https://affiliate.shopee.vn", wait_until="networkidle", timeout=30000)
    print("Current URL:", page.url)
    print("Title:", page.title())
    page.screenshot(path="portal_home.png")
    browser.close()
