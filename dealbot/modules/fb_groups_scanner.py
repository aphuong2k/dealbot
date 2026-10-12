"""Module quét danh sách group Facebook đã join và rời nhóm qua Playwright.
Dùng cookie của từng tài khoản để quét trang 'Groups > Your groups' trên Facebook,
trích xuất tên + URL group, và hỗ trợ rời nhóm (leave group).
"""
import sys, json, time, os, re

def scan_joined_groups(cookie_file: str, max_scroll: int = 15) -> dict:
    """Quét danh sách group Facebook mà tài khoản đã tham gia.
    
    Mở trang https://www.facebook.com/groups/joins/ bằng Playwright,
    cuộn xuống để load hết, rồi trích xuất tên + URL group.
    """
    if not os.path.exists(cookie_file):
        return {"success": False, "message": "File cookie không tồn tại", "groups": []}

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
        ss = {"no_restriction": "None", "lax": "Lax", "strict": "Strict"}.get(
            str(c.get("sameSite", "")).lower()
        )
        if ss:
            ck["sameSite"] = ss
        cookies.append(ck)

    if not cookies:
        return {"success": False, "message": "File cookie trống!", "groups": []}

    try:
        from playwright.sync_api import sync_playwright
        import random

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            ctx.add_cookies(cookies)
            page = ctx.new_page()

            # Mở trang danh sách group đã join
            page.goto("https://www.facebook.com/groups/joins/", wait_until="domcontentloaded", timeout=25000)
            time.sleep(3)

            # Kiểm tra đăng nhập & checkpoint
            current_cookies = ctx.cookies()
            has_c_user = any(ck["name"] == "c_user" for ck in current_cookies)
            has_login_form = False
            try:
                has_login_form = page.locator('input[name="email"], input[name="pass"], #login_form').count() > 0
            except Exception:
                pass

            if any(k in page.url.lower() for k in ("checkpoint", "login", "two_step")) or not has_c_user or has_login_form:
                browser.close()
                return {
                    "success": False,
                    "message": "Cookie nick Facebook đã hết hạn hoặc bị đăng xuất! Vui lòng vào Cài Đặt ➔ Cập nhật Cookie mới cho nick này.",
                    "groups": []
                }

            # Cuộn trang để load thêm group
            prev_count = 0
            for scroll_i in range(max_scroll):
                page.mouse.wheel(0, random.randint(800, 1500))
                time.sleep(random.uniform(1.5, 2.5))
                # Kiểm tra xem đã hết chưa
                links = page.locator('a[href*="/groups/"]').all()
                if len(links) == prev_count and scroll_i > 3:
                    break
                prev_count = len(links)

            # Trích xuất group từ trang
            groups_found = []
            seen_urls = set()
            
            all_links = page.locator('a[href*="/groups/"]').all()
            for link in all_links:
                try:
                    href = link.get_attribute("href") or ""
                    # Lọc chỉ lấy link group chính (không phải /groups/feed, /groups/joins, etc.)
                    m = re.search(r"facebook\.com/groups/([\w.\-]+)", href)
                    if not m:
                        continue
                    group_slug = m.group(1)
                    # Bỏ qua các đường dẫn hệ thống
                    if group_slug in ("joins", "feed", "discover", "create", "notifications", "settings"):
                        continue
                    
                    group_url = f"https://www.facebook.com/groups/{group_slug}"
                    if group_url in seen_urls:
                        continue
                    seen_urls.add(group_url)
                    
                    # Lấy tên group (text trong thẻ a hoặc con gần nhất)
                    name = ""
                    try:
                        name = link.inner_text(timeout=2000).strip()
                    except Exception:
                        pass
                    
                    if not name or len(name) > 200:
                        name = group_slug
                    
                    # Lọc bỏ text rác (chỉ lấy dòng đầu tiên nếu có nhiều dòng)
                    name = name.split("\n")[0].strip()
                    if name:
                        groups_found.append({
                            "url": group_url,
                            "name": name,
                            "slug": group_slug
                        })
                except Exception:
                    continue

            browser.close()

        return {
            "success": True,
            "message": f"Đã quét được {len(groups_found)} group đang tham gia.",
            "groups": groups_found
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Lỗi khi quét group: {str(e)}",
            "groups": []
        }


def leave_group(cookie_file: str, group_url: str) -> dict:
    """Rời khỏi một group Facebook bằng Playwright.
    
    Mở group, tìm nút menu '...' hoặc 'Joined' > 'Leave group'.
    """
    if not os.path.exists(cookie_file):
        return {"success": False, "message": "File cookie không tồn tại"}

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
        ss = {"no_restriction": "None", "lax": "Lax", "strict": "Strict"}.get(
            str(c.get("sameSite", "")).lower()
        )
        if ss:
            ck["sameSite"] = ss
        cookies.append(ck)

    try:
        from playwright.sync_api import sync_playwright
        import random

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            ctx.add_cookies(cookies)
            page = ctx.new_page()

            page.goto(group_url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(3)

            # Kiểm tra checkpoint / đăng nhập
            if any(k in page.url.lower() for k in ("checkpoint", "login", "two_step")):
                browser.close()
                return {"success": False, "message": "Cookie hết hạn hoặc tài khoản dính checkpoint!"}

            # Kiểm tra xem có đang ở trong group không (nếu thấy nút 'Tham gia nhóm' tức là chưa tham gia hoặc đã rời rồi)
            already_left_btn = page.locator(
                'div[role="button"]:has-text("Tham gia nhóm"), '
                'div[role="button"]:has-text("Join group"), '
                'div[aria-label="Tham gia nhóm"], '
                'div[aria-label="Join group"]'
            ).first
            try:
                if already_left_btn.is_visible(timeout=2000):
                    browser.close()
                    return {"success": True, "message": "Tài khoản hiện không còn là thành viên của nhóm này."}
            except Exception:
                pass

            # 1. Tìm nút "Đã tham gia" / "Joined" hoặc Menu group
            joined_btn = None
            joined_selectors = [
                'div[aria-label="Đã tham gia"]',
                'div[aria-label="Joined"]',
                'div[role="button"]:has-text("Đã tham gia")',
                'div[role="button"]:has-text("Joined")',
                'a[role="button"]:has-text("Đã tham gia")',
                'a[role="button"]:has-text("Joined")',
                'div[aria-label="Menu khác"]',
                'div[aria-label="More options"]',
                'div[aria-label="Thao tác khác"]',
                'div[aria-label="More"]',
                'div[role="button"][aria-haspopup="menu"]'
            ]
            for sel in joined_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=1500):
                        joined_btn = btn
                        break
                except Exception:
                    continue

            if not joined_btn:
                browser.close()
                return {"success": False, "message": "Không tìm thấy nút 'Đã tham gia' hoặc menu thao tác trên trang nhóm."}

            try:
                joined_btn.scroll_into_view_if_needed()
                joined_btn.click()
                time.sleep(2)
            except Exception as e:
                browser.close()
                return {"success": False, "message": f"Không thể bấm nút 'Đã tham gia': {e}"}

            # 2. Tìm và click "Rời nhóm" / "Rời khỏi nhóm" / "Leave group" trong menu thả xuống
            leave_btn = None
            leave_selectors = [
                'div[role="menuitem"]:has-text("Rời khỏi nhóm")',
                'div[role="menuitem"]:has-text("Rời nhóm")',
                'div[role="menuitem"]:has-text("Leave group")',
                'div[role="menuitem"]:has-text("Leave Group")',
                'div[role="menuitem"]:has-text("Leave")',
                'span:has-text("Rời khỏi nhóm")',
                'span:has-text("Rời nhóm")',
                'span:has-text("Leave group")',
                'span:has-text("Leave Group")',
                'div[role="menu"] div[role="button"]:has-text("Rời")'
            ]
            for sel in leave_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=1500):
                        leave_btn = btn
                        break
                except Exception:
                    continue

            if not leave_btn:
                browser.close()
                return {"success": False, "message": "Không tìm thấy tùy chọn 'Rời nhóm' trong menu tùy chọn."}

            try:
                leave_btn.scroll_into_view_if_needed()
                leave_btn.click()
                time.sleep(2.5)
            except Exception as e:
                browser.close()
                return {"success": False, "message": f"Không thể bấm tùy chọn 'Rời nhóm': {e}"}

            # 3. Xác nhận rời nhóm trên hộp thoại modal (Dialog)
            # Chờ hộp thoại modal xuất hiện
            dialog = None
            for d_sel in ['div[role="dialog"]', 'div[aria-modal="true"]']:
                d = page.locator(d_sel).last
                try:
                    if d.is_visible(timeout=2500):
                        dialog = d
                        break
                except Exception:
                    pass

            confirm_btn = None

            # Ưu tiên tìm trong hộp thoại modal dialog
            if dialog:
                confirm_selectors = [
                    'div[aria-label="Rời khỏi nhóm"]',
                    'div[aria-label="Rời nhóm"]',
                    'div[aria-label="Leave group"]',
                    'div[aria-label="Leave Group"]',
                    'div[aria-label="Leave"]',
                    'div[role="button"]:has-text("Rời khỏi nhóm")',
                    'div[role="button"]:has-text("Rời nhóm")',
                    'div[role="button"]:has-text("Leave group")',
                    'div[role="button"]:has-text("Leave Group")',
                    'div[role="button"]:has-text("Leave")',
                    'button:has-text("Rời khỏi nhóm")',
                    'button:has-text("Rời nhóm")',
                    'button:has-text("Leave")',
                    'span:has-text("Rời khỏi nhóm")',
                    'span:has-text("Rời nhóm")'
                ]
                for sel in confirm_selectors:
                    btn = dialog.locator(sel).first
                    try:
                        if btn.is_visible(timeout=1000):
                            confirm_btn = btn
                            break
                    except Exception:
                        continue

                # Nếu chưa bắt được bằng selector cụ thể, quét qua tất cả nút trong dialog
                if not confirm_btn:
                    try:
                        buttons = dialog.locator('div[role="button"], button').all()
                        for b in buttons:
                            try:
                                txt = (b.inner_text() or "").strip().lower()
                                label = (b.get_attribute("aria-label") or "").strip().lower()
                                combined = f"{txt} {label}"
                                # Bỏ qua nút Hủy / Cancel / Đóng
                                if any(c in combined for c in ("hủy", "cancel", "đóng", "close")):
                                    continue
                                if any(k in combined for k in ("rời", "leave")):
                                    confirm_btn = b
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

            # Fallback tìm trên toàn trang nếu không bắt được container dialog
            if not confirm_btn:
                global_confirm_selectors = [
                    'div[role="dialog"] div[aria-label="Rời khỏi nhóm"]',
                    'div[role="dialog"] div[aria-label="Rời nhóm"]',
                    'div[aria-label="Rời khỏi nhóm"]',
                    'div[aria-label="Rời nhóm"]',
                    'div[aria-label="Leave group"]',
                    'div[role="button"]:has-text("Rời khỏi nhóm")',
                    'div[role="button"]:has-text("Rời nhóm")',
                    'button:has-text("Rời khỏi nhóm")',
                    'button:has-text("Rời nhóm")'
                ]
                for sel in global_confirm_selectors:
                    btn = page.locator(sel).last
                    try:
                        if btn.is_visible(timeout=1200):
                            confirm_btn = btn
                            break
                    except Exception:
                        continue

            if confirm_btn:
                try:
                    confirm_btn.scroll_into_view_if_needed()
                    confirm_btn.click()
                    time.sleep(3)
                    browser.close()
                    return {"success": True, "message": f"Đã rời khỏi nhóm Facebook thành công!"}
                except Exception as e:
                    browser.close()
                    return {"success": False, "message": f"Lỗi khi bấm nút xác nhận rời nhóm: {e}"}
            else:
                # Chụp ảnh màn hình lưu vết nếu cần gỡ lỗi
                try:
                    page.screenshot(path="debug_leave_group_error.png")
                except Exception:
                    pass
                browser.close()
                return {"success": False, "message": "Không tìm thấy nút xác nhận rời nhóm trong hộp thoại xác nhận."}

    except Exception as e:
        return {"success": False, "message": f"Lỗi khi mở trình duyệt: {str(e)}"}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["scan", "leave"])
    parser.add_argument("cookie_file")
    parser.add_argument("--group-url", default="")
    parser.add_argument("--max-scroll", type=int, default=15)
    args = parser.parse_args()

    if args.action == "scan":
        result = scan_joined_groups(args.cookie_file, args.max_scroll)
    elif args.action == "leave":
        if not args.group_url:
            result = {"success": False, "message": "Thiếu --group-url"}
        else:
            result = leave_group(args.cookie_file, args.group_url)
    
    print(json.dumps(result, ensure_ascii=False))
