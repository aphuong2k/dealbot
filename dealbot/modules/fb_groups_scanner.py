"""Module quét danh sách group Facebook đã join và rời nhóm qua Playwright.
Dùng cookie của từng tài khoản để quét trang 'Groups > Your groups' trên Facebook,
trích xuất tên + URL group, và hỗ trợ rời nhóm (leave group).
"""
import sys, json, time, os, re, urllib.parse

def _load_cookies_from_file(cookie_file: str) -> list:
    """Đọc và chuẩn hóa cookies từ file JSON sang định dạng tương thích với Playwright."""
    if not os.path.exists(cookie_file):
        return []
    try:
        raw = json.load(open(cookie_file, encoding="utf-8"))
    except Exception:
        return []
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
    return cookies

def classify_group_niche(group_name: str, fallback_niche: str = "săn sale") -> tuple:
    """Tự động phân loại nhóm ngành & kind từ tên của group Facebook."""
    name_l = (group_name or "").lower()
    
    if any(k in name_l for k in ["mỹ phẩm", "skincare", "làm đẹp", "son môi", "chăm sóc da", "trang điểm", "beauty", "dưỡng da"]):
        return "mỹ phẩm", "niche"
    if any(k in name_l for k in ["gia dụng", "yêu bếp", "nghiện nhà", "nội thất", "bếp", "đời sống", "decor", "nhà cửa", "tiện ích"]):
        return "gia dụng", "niche"
    if any(k in name_l for k in ["mẹ và bé", "mẹ & bé", "bỉm sữa", "nuôi con", "trẻ em", "ăn dặm", "mẹ bé", "sơ sinh"]):
        return "mẹ và bé", "niche"
    if any(k in name_l for k in ["công nghệ", "tin học", "phụ kiện", "tai nghe", "laptop", "pc", "gaming", "điện thoại", "ios", "android"]):
        return "đồ công nghệ giá rẻ", "niche"
    if any(k in name_l for k in ["thời trang nam", "nam giới", "men fashion"]):
        return "Thời Trang Nam", "niche"
    if any(k in name_l for k in ["thời trang nữ", "váy", "đầm", "outfit nữ", "hội chị em"]):
        return "Thời Trang Nữ", "niche"
    if any(k in name_l for k in ["thời trang", "quần áo", "outfit", "phối đồ", "sneaker", "giày dép", "thanh lý đồ", "style"]):
        return "thời trang", "niche"
    if any(k in name_l for k in ["săn sale", "săn deal", "voucher", "mã giảm giá", "shopee", "lazada", "tiki", "khuyến mãi", "deal hời"]):
        return "săn sale shopee", "dealhunt"
        
    return fallback_niche, "dealhunt" if ("sale" in fallback_niche or "deal" in fallback_niche) else "niche"

def parse_group_card_metadata(text: str) -> dict:
    """Bóc tách thông tin loại nhóm (công khai/riêng tư), số thành viên, và tần suất bài đăng từ thẻ nhóm."""
    text_clean = text.replace("\xa0", " ").strip()
    t_lower = text_clean.lower()
    
    # 1. Loại nhóm
    privacy = "public"
    if any(k in t_lower for k in ["nhóm riêng tư", "private group", "riêng tư", "private"]):
        privacy = "private"
    elif any(k in t_lower for k in ["nhóm công khai", "public group", "công khai", "public"]):
        privacy = "public"

    # 2. Số lượng thành viên
    members = 0
    mem_m = re.search(r"([\d.,]+)\s*([kKmM]|triệu|nghìn|ngàn)?\s*(?:thành viên|members?|người tham gia)", text_clean, re.I)
    if mem_m:
        raw_val = mem_m.group(1).strip()
        unit = (mem_m.group(2) or "").lower()
        try:
            if unit in ("k", "nghìn", "ngàn"):
                clean_num = float(raw_val.replace(",", "."))
                members = int(clean_num * 1000)
            elif unit in ("m", "triệu"):
                clean_num = float(raw_val.replace(",", "."))
                members = int(clean_num * 1000000)
            else:
                digits_only = re.sub(r"[^\d]", "", raw_val)
                members = int(digits_only) if digits_only else 0
        except Exception:
            members = 0

    # 3. Tần suất bài viết hàng ngày
    posts_per_day = 0.0
    activity_text = ""
    
    p_day = re.search(r"(\d+)\+?\s*(?:bài viết|bài|posts?)\s*(?:mỗi\s*ngày|/ngày|một\s*ngày|a\s*day|per\s*day|/day)", text_clean, re.I)
    p_week = re.search(r"(\d+)\+?\s*(?:bài viết|bài|posts?)\s*(?:mỗi\s*tuần|/tuần|một\s*tuần|a\s*week|per\s*week)", text_clean, re.I)
    p_month = re.search(r"(\d+)\+?\s*(?:bài viết|bài|posts?)\s*(?:mỗi\s*tháng|/tháng|một\s*tháng|a\s*month|per\s*month)", text_clean, re.I)

    if p_day:
        val = int(p_day.group(1))
        posts_per_day = float(val)
        activity_text = f"{val}+ bài viết/ngày"
    elif p_week:
        val = int(p_week.group(1))
        posts_per_day = round(val / 7.0, 1)
        activity_text = f"{val} bài viết/tuần (~{posts_per_day}/ngày)"
    elif p_month:
        val = int(p_month.group(1))
        posts_per_day = round(val / 30.0, 1)
        activity_text = f"{val} bài viết/tháng (~{posts_per_day}/ngày)"
    else:
        if "bài viết mới hôm nay" in t_lower:
            m_today = re.search(r"(\d+)\+?\s*bài viết mới hôm nay", text_clean, re.I)
            if m_today:
                posts_per_day = float(m_today.group(1))
                activity_text = f"{int(posts_per_day)} bài viết mới hôm nay"
        if not activity_text:
            activity_text = "Chưa rõ tần suất"

    return {
        "privacy": privacy,
        "members": members,
        "posts_per_day": posts_per_day,
        "activity_text": activity_text
    }

def scan_joined_groups(cookie_file: str, max_scroll: int = 15) -> dict:
    """Quét danh sách group Facebook mà tài khoản đã tham gia.
    
    Mở trang https://www.facebook.com/groups/joins/ bằng Playwright,
    cuộn xuống để load hết, rồi trích xuất tên + URL group.
    """
    if not os.path.exists(cookie_file):
        return {"success": False, "message": "File cookie không tồn tại", "groups": []}

    cookies = _load_cookies_from_file(cookie_file)
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
                        auto_niche, auto_kind = classify_group_niche(name)
                        groups_found.append({
                            "url": group_url,
                            "name": name,
                            "slug": group_slug,
                            "niche": auto_niche,
                            "kind": auto_kind
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


def join_group(cookie_file: str, group_url: str) -> dict:
    """Tự động tham gia một group Facebook bằng Playwright."""
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

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 850},
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

            # 1. Kiểm tra xem đã là thành viên chưa
            joined_selectors = [
                'div[aria-label="Đã tham gia"]',
                'div[aria-label="Joined"]',
                'div[role="button"]:has-text("Đã tham gia")',
                'div[role="button"]:has-text("Joined")',
                'a[role="button"]:has-text("Đã tham gia")'
            ]
            for sel in joined_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=1000):
                        browser.close()
                        return {"success": True, "status": "joined", "message": "Tài khoản đã là thành viên của nhóm này rồi."}
                except Exception:
                    continue

            # 2. Kiểm tra xem có đang chờ duyệt không
            pending_selectors = [
                'div[role="button"]:has-text("Đang chờ phê duyệt")',
                'div[role="button"]:has-text("Đang chờ duyệt")',
                'div[role="button"]:has-text("Pending")',
                'div[role="button"]:has-text("Hủy yêu cầu")'
            ]
            for sel in pending_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=1000):
                        browser.close()
                        return {"success": True, "status": "pending_approval", "message": "Yêu cầu tham gia đang chờ admin phê duyệt."}
                except Exception:
                    continue

            # 3. Tìm nút "Tham gia nhóm" / "Join group"
            join_selectors = [
                'div[role="button"]:has-text("Tham gia nhóm")',
                'div[role="button"]:has-text("Tham gia")',
                'div[role="button"]:has-text("Join group")',
                'div[role="button"]:has-text("Join Group")',
                'div[aria-label="Tham gia nhóm"]',
                'div[aria-label="Join group"]',
                'a[role="button"]:has-text("Tham gia nhóm")',
                'span:has-text("Tham gia nhóm")'
            ]
            join_btn = None
            for sel in join_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=1500):
                        join_btn = btn
                        break
                except Exception:
                    continue

            if not join_btn:
                browser.close()
                return {"success": False, "message": "Không tìm thấy nút 'Tham gia nhóm' (nhóm có thể bị ẩn, cấm hoặc đường dẫn không hợp lệ)."}

            try:
                join_btn.scroll_into_view_if_needed()
                join_btn.click()
                time.sleep(2.5)
            except Exception as e:
                browser.close()
                return {"success": False, "message": f"Lỗi khi bấm nút tham gia nhóm: {e}"}

            # 4. Xử lý popup quy tắc nhóm / câu hỏi nếu có
            try:
                dlg = page.locator('div[role="dialog"]').first
                if dlg.is_visible(timeout=2000):
                    # Tick các checkbox đồng ý quy tắc nếu có
                    checkboxes = dlg.locator('input[type="checkbox"], div[role="checkbox"]').all()
                    for cb in checkboxes:
                        try:
                            if not cb.is_checked():
                                cb.click()
                                time.sleep(0.4)
                        except Exception:
                            pass

                    # Tìm nút Gửi / Hoàn tất / Submit
                    submit_selectors = [
                        'div[role="button"]:has-text("Gửi")',
                        'div[role="button"]:has-text("Submit")',
                        'div[role="button"]:has-text("Hoàn tất")',
                        'div[role="button"]:has-text("Xác nhận")',
                        'div[role="button"]:has-text("Đồng ý")'
                    ]
                    for s_sel in submit_selectors:
                        s_btn = dlg.locator(s_sel).first
                        if s_btn.is_visible(timeout=1000):
                            s_btn.click()
                            time.sleep(2)
                            break
            except Exception:
                pass

            time.sleep(2)

            # 5. Xác minh trạng thái sau khi bấm
            status = "joined"
            msg = "Đã tham gia nhóm Facebook thành công!"
            for sel in pending_selectors:
                btn = page.locator(sel).first
                try:
                    if btn.is_visible(timeout=1000):
                        status = "pending_approval"
                        msg = "Yêu cầu đã được gửi! Đang chờ admin nhóm phê duyệt."
                        break
                except Exception:
                    continue

            browser.close()
            return {"success": True, "status": status, "message": msg}

    except Exception as e:
        return {"success": False, "message": f"Lỗi khi mở trình duyệt: {str(e)}"}


def search_facebook_groups(
    cookie_file: str,
    keyword: str,
    niche: str = "",
    min_members: int = 5000,
    min_posts_per_day: float = 3.0,
    only_public: bool = True,
    max_scroll: int = 6,
    auto_join: bool = False,
    max_results: int = 15
) -> dict:
    """Tìm kiếm nhóm Facebook theo từ khóa/ngành, soi số thành viên & bài viết/ngày, và tự động join nếu đạt chuẩn."""
    if not os.path.exists(cookie_file):
        return {"success": False, "message": "File cookie không tồn tại", "groups": []}

    cookies = _load_cookies_from_file(cookie_file)
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

            encoded_kw = urllib.parse.quote(keyword)
            search_url = f"https://www.facebook.com/search/groups/?q={encoded_kw}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Kiểm tra checkpoint & đăng nhập
            current_cookies = ctx.cookies()
            has_c_user = any(ck["name"] == "c_user" for ck in current_cookies)
            if any(k in page.url.lower() for k in ("checkpoint", "login", "two_step")) or not has_c_user:
                browser.close()
                return {
                    "success": False,
                    "message": "Cookie nick Facebook đã hết hạn hoặc dính checkpoint! Vui lòng cập nhật Cookie mới.",
                    "groups": []
                }

            # Cuộn trang để tải thêm các thẻ nhóm
            for _ in range(max_scroll):
                page.mouse.wheel(0, random.randint(800, 1400))
                time.sleep(random.uniform(1.2, 2.0))

            # Trích xuất các liên kết group
            raw_links = page.locator('a[href*="/groups/"]').all()
            seen_slugs = set()
            groups_evaluated = []

            for link in raw_links:
                try:
                    href = link.get_attribute("href") or ""
                    m = re.search(r"facebook\.com/groups/([\w.\-]+)", href)
                    if not m:
                        continue
                    slug = m.group(1)
                    if slug in ("joins", "feed", "discover", "create", "notifications", "settings", "search"):
                        continue
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    group_url = f"https://www.facebook.com/groups/{slug}"

                    # Lấy text container bao bọc link nhóm để đọc thông tin thành viên, bài viết/ngày
                    card_text = ""
                    try:
                        card_text = link.evaluate(
                            """el => {
                                let cur = el;
                                for (let i = 0; i < 5; i++) {
                                    if (cur.parentElement) cur = cur.parentElement;
                                }
                                return cur.innerText || '';
                            }"""
                        )
                    except Exception:
                        pass

                    if not card_text:
                        try:
                            card_text = link.inner_text() or ""
                        except Exception:
                            pass

                    # Tên nhóm (thường là inner text của link hoặc dòng đầu tiên)
                    name = ""
                    try:
                        name = link.inner_text().strip()
                    except Exception:
                        pass
                    if not name or len(name) > 200:
                        lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                        name = lines[0] if lines else slug
                    name = name.split("\n")[0].strip()

                    # Bóc tách thông tin: thành viên, bài/ngày, loại nhóm
                    meta = parse_group_card_metadata(card_text)
                    members = meta["members"]
                    posts_per_day = meta["posts_per_day"]
                    privacy = meta["privacy"]
                    activity_text = meta["activity_text"]

                    # Phân loại nhóm ngành
                    final_niche = niche
                    final_kind = "niche"
                    if not final_niche:
                        final_niche, final_kind = classify_group_niche(name)
                    else:
                        final_kind = "dealhunt" if ("sale" in final_niche.lower() or "deal" in final_niche.lower()) else "niche"

                    # Kiểm tra trạng thái tham gia hiện tại trên Facebook
                    t_low = card_text.lower()
                    if any(k in t_low for k in ["đã tham gia", "joined"]):
                        status = "joined"
                    elif any(k in t_low for k in ["đang chờ phê duyệt", "pending"]):
                        status = "pending_approval"
                    else:
                        status = "candidate"

                    # ĐÁNH GIÁ TIÊU CHÍ (Soi thành viên, bài đăng hàng ngày, quyền riêng tư)
                    meets_members = members >= min_members
                    meets_activity = posts_per_day >= min_posts_per_day
                    meets_privacy = (not only_public) or (privacy == "public")
                    is_qualified = bool(meets_members and meets_activity and meets_privacy)

                    # Lý do đánh giá
                    reasons = []
                    if not meets_members:
                        reasons.append(f"Thành viên ({members:,}) < {min_members:,}")
                    if not meets_activity:
                        reasons.append(f"Tần suất ({posts_per_day} bài/ngày) < {min_posts_per_day}")
                    if not meets_privacy:
                        reasons.append("Nhóm riêng tư (yêu cầu nhóm công khai)")

                    evaluation_note = "✅ Đạt chuẩn" if is_qualified else ("❌ Chưa đạt: " + ", ".join(reasons))

                    # Tính điểm ưu tiên (priority_score)
                    score = round(
                        50.0 + min(50.0, members / 2000.0) + min(40.0, posts_per_day * 2.0) + (10.0 if privacy == "public" else 0.0),
                        1
                    )

                    group_item = {
                        "url": group_url,
                        "name": name,
                        "slug": slug,
                        "niche": final_niche,
                        "kind": final_kind,
                        "members": members,
                        "posts_per_day": posts_per_day,
                        "privacy": privacy,
                        "activity_text": activity_text,
                        "status": status,
                        "is_qualified": is_qualified,
                        "evaluation_note": evaluation_note,
                        "priority_score": score
                    }

                    groups_evaluated.append(group_item)
                    if len(groups_evaluated) >= max_results:
                        break

                except Exception:
                    continue

            browser.close()

        # Nếu có tùy chọn auto_join: Tự động join các nhóm đạt chuẩn đang ở status candidate
        joined_count = 0
        if auto_join:
            qualified_candidates = [g for g in groups_evaluated if g["is_qualified"] and g["status"] == "candidate"]
            for g in qualified_candidates[:5]:  # Giới hạn an toàn tối đa 5 nhóm mỗi đợt
                res_join = join_group(cookie_file, g["url"])
                if res_join.get("success"):
                    g["status"] = res_join.get("status", "joined")
                    g["join_message"] = res_join.get("message", "Đã gửi yêu cầu join")
                    joined_count += 1
                time.sleep(random.uniform(4.0, 7.0))

        qualified_total = sum(1 for g in groups_evaluated if g["is_qualified"])
        msg = f"Tìm thấy {len(groups_evaluated)} nhóm: {qualified_total} nhóm đạt chuẩn tiêu chí (TV >= {min_members:,}, >= {min_posts_per_day} bài/ngày)."
        if auto_join and joined_count > 0:
            msg += f" Đã tự động gửi yêu cầu tham gia {joined_count} nhóm đạt chuẩn!"

        return {
            "success": True,
            "message": msg,
            "keyword": keyword,
            "niche": niche,
            "groups": groups_evaluated,
            "qualified_count": qualified_total
        }

    except Exception as e:
        return {"success": False, "message": f"Lỗi khi tìm kiếm nhóm: {str(e)}", "groups": []}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["scan", "leave", "join", "search"])
    parser.add_argument("cookie_file")
    parser.add_argument("--group-url", default="")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--niche", default="")
    parser.add_argument("--min-members", type=int, default=5000)
    parser.add_argument("--min-posts", type=float, default=3.0)
    parser.add_argument("--only-public", action="store_true")
    parser.add_argument("--auto-join", action="store_true")
    parser.add_argument("--max-results", type=int, default=15)
    parser.add_argument("--max-scroll", type=int, default=15)
    args = parser.parse_args()

    if args.action == "scan":
        result = scan_joined_groups(args.cookie_file, args.max_scroll)
    elif args.action == "leave":
        if not args.group_url:
            result = {"success": False, "message": "Thiếu --group-url"}
        else:
            result = leave_group(args.cookie_file, args.group_url)
    elif args.action == "join":
        if not args.group_url:
            result = {"success": False, "message": "Thiếu --group-url"}
        else:
            result = join_group(args.cookie_file, args.group_url)
    elif args.action == "search":
        if not args.keyword:
            result = {"success": False, "message": "Thiếu --keyword"}
        else:
            result = search_facebook_groups(
                args.cookie_file,
                keyword=args.keyword,
                niche=args.niche,
                min_members=args.min_members,
                min_posts_per_day=args.min_posts,
                only_public=args.only_public,
                max_scroll=args.max_scroll,
                auto_join=args.auto_join,
                max_results=args.max_results
            )
    
    print(json.dumps(result, ensure_ascii=False))
