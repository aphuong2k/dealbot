"""Module kiểm tra trạng thái đăng nhập Facebook từ Cookie độc lập qua Playwright."""
import sys, json, time, os

def check_cookie(cookie_file: str) -> dict:
    if not os.path.exists(cookie_file):
        return {"success": False, "message": "File cookie không tồn tại", "checkpoint": True}

    raw = json.load(open(cookie_file, encoding="utf-8"))
    cookies = []
    for c in raw:
        ck = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".facebook.com"),
            "path": c.get("path", "/"),
            "secure": True
        }
        ss = {"no_restriction": "None", "lax": "Lax", "strict": "Strict"}.get(str(c.get("sameSite", "")).lower())
        if ss:
            ck["sameSite"] = ss
        cookies.append(ck)

    if not cookies:
        return {"success": False, "message": "File cookie trống!", "checkpoint": True}

    c_user = next((c["value"] for c in cookies if c["name"] == "c_user"), None)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=25000)
            time.sleep(3)

            final_url = page.url
            title = page.title()
            current_cookies = ctx.cookies()
            has_c_user_live = any(ck["name"] == "c_user" for ck in current_cookies)
            has_login_form = False
            try:
                has_login_form = page.locator('input[name="email"], input[name="pass"], #login_form, a[data-testid="open-registration-form-button"]').count() > 0
            except Exception:
                pass

            is_guest = any(k in final_url.lower() for k in ("checkpoint", "login", "two_step")) or not has_c_user_live or has_login_form

            browser.close()

        if is_guest:
            return {
                "success": False,
                "c_user": c_user,
                "url": final_url,
                "title": title,
                "checkpoint": True,
                "message": f"❌ Cookie Facebook đã hết hạn hoặc bị đăng xuất! (UID: {c_user or 'Không rõ'}). Vui lòng đăng nhập lại Facebook trên trình duyệt và copy lại cookie mới."
            }
        else:
            return {
                "success": True,
                "c_user": c_user,
                "url": final_url,
                "title": title,
                "checkpoint": False,
                "message": f"✅ Kết nối Facebook thành công! Nick đang online ổn định (UID: {c_user})."
            }
    except Exception as e:
        return {
            "success": False,
            "c_user": c_user,
            "checkpoint": True,
            "message": f"Lỗi khi mở trình duyệt: {str(e)}"
        }

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "message": "Thiếu tham số file cookie"}, ensure_ascii=False))
        sys.exit(1)
    
    result = check_cookie(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))

