"""Module 3b: Đăng bài tự động lên nhóm Facebook qua Playwright bằng cookie.
Kế thừa kiến trúc chuẩn và bộ selector tối ưu từ auto-aff:
- Chống bot bằng args `--disable-blink-features=AutomationControlled` và Chrome Desktop User-Agent
- Thẩm định quyền đăng bài trước khi thao tác (phát hiện nhóm đóng, chưa join, chờ duyệt, admin-only)
- Mở popup soạn bài đa selector (Bạn viết gì đi, Bạn đang nghĩ gì, Tạo bài viết, Write something, Inline Composer)
- Quét tìm đúng dialog đang hiển thị thực tế (bỏ qua dialog ẩn chat/thông báo)
- Gõ nội dung an toàn bằng insert_text (hỗ trợ 100% tiếng Việt UTF-8 và Emoji siêu tốc, không bị rớt chữ)
- Đính kèm ảnh banner Flash Sale chuẩn xác
- Chờ nút Đăng hết disabled (aria-disabled != 'true') rồi mới click (Khắc phục triệt để lỗi bấm ảo không ăn)
- Phát hiện bài chờ admin duyệt vs bài đăng thành công trực tiếp
- Hỗ trợ chu trình Đăng Bài Tuần Tự (Gradual Posting) có nhịp nghỉ an toàn chống spam và đếm ngược thời gian thực
- Tự động khớp Deal thông minh theo ngành hàng của từng nhóm Facebook
"""
import os, sys, json, time, random, re, logging, threading
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from notify import tg
from playwright.sync_api import sync_playwright

import db
from . import deals as dealmod
from .affiliate import extract_group_tag, build_subid_link
from .category_mapping import CategoryMatcher

logger = logging.getLogger("FacebookPoster")
logger.setLevel(logging.INFO)

# Trạng thái tiến trình đăng bài dần toàn cục (Gradual Posting State)
gradual_posting_state: Dict[str, Any] = {
    "is_running": False,
    "total_target": 0,
    "completed": 0,
    "current_group": "",
    "current_deal": "",
    "current_account": "",
    "next_post_time": None,
    "remaining_delay": 0,
    "delay_seconds": 60,
    "status": "IDLE",
    "last_result": None,
    "history": []
}

def _load_cookies(path_or_str: Any) -> List[Dict]:
    """Tải và chuẩn hóa cookies từ file JSON hoặc chuỗi cookie raw."""
    if not path_or_str:
        return []

    # 1. Nếu là list dict sẵn
    if isinstance(path_or_str, list):
        out = []
        for c in path_or_str:
            if isinstance(c, dict) and "name" in c and "value" in c:
                ck = {
                    "name": c["name"],
                    "value": str(c["value"]),
                    "domain": c.get("domain", ".facebook.com"),
                    "path": c.get("path", "/"),
                    "secure": True
                }
                ss = {"no_restriction": "None", "lax": "Lax", "strict": "Strict"}.get(str(c.get("sameSite", "")).lower())
                if ss:
                    ck["sameSite"] = ss
                out.append(ck)
        return out

    # 2. Nếu là chuỗi cookie dạng 'c_user=...; xs=...'
    text = str(path_or_str).strip()
    if text.startswith("c_user=") or "; xs=" in text:
        cookies = []
        for item in text.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies.append({
                    "name": k.strip(),
                    "value": v.strip(),
                    "domain": ".facebook.com",
                    "path": "/",
                    "secure": True
                })
        return cookies

    # 3. Nếu là file JSON
    path = text
    if not os.path.isabs(path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cands = [
            os.path.join(base_dir, path),
            os.path.join(base_dir, "dealbot", path),
            os.path.join(base_dir, "cookies", os.path.basename(path)),
            os.path.join(base_dir, "dealbot", "cookies", os.path.basename(path))
        ]
        for c in cands:
            if os.path.exists(c):
                path = c
                break

    if not os.path.exists(path):
        return []

    try:
        raw = json.load(open(path, "r", encoding="utf-8"))
        if isinstance(raw, list):
            return _load_cookies(raw)
    except Exception as e:
        logger.warning(f"Lỗi đọc file cookie {path}: {e}")
        return []

    return []


class AccountSession:
    """Phiên làm việc trình duyệt Playwright mô phỏng người dùng thật."""
    def __init__(self, pw, acc: Dict, headless: bool = True):
        self.acc = acc
        self.browser = pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.ctx = self.browser.new_context(
            locale="vi-VN",
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        cks = _load_cookies(acc.get("cookie_file") or acc.get("cookie") or acc.get("cookie_data"))
        if not cks:
            raise FileNotFoundError(f"Chưa có file cookie hợp lệ cho nick '{acc.get('name')}' ({acc.get('cookie_file')}).")
        self.ctx.add_cookies(cks)
        self.page = self.ctx.new_page()

    def healthy(self) -> bool:
        """Kiểm tra tài khoản còn đăng nhập được Facebook hay dính checkpoint."""
        try:
            self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2, 4))
            u = self.page.url.lower()
            return not any(k in u for k in ("checkpoint", "login", "two_step", "disabled"))
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra session healthy: {e}")
            return False

    def post(self, group_url: str, caption: str, comment: Optional[str] = None, dry_run: bool = False, image_path: Optional[str] = None) -> Dict:
        """
        Đăng bài viết thực tế vào nhóm Facebook bằng Playwright chuẩn mực:
        - Thẩm định quyền đăng
        - Gõ nội dung bằng insert_text
        - Đính ảnh
        - Chờ nút Đăng hết disabled trước khi click
        - Trả về permalink bài viết hoặc ghi nhận trạng thái pending_approval
        """
        pg = self.page
        logger.info(f"🌐 Đang truy cập nhóm Facebook: {group_url}")
        pg.goto(group_url, wait_until="domcontentloaded", timeout=40000)
        pg.wait_for_timeout(3500)

        # 0. Kiểm tra Checkpoint / Đăng xuất
        if any(k in pg.url.lower() for k in ("checkpoint", "login", "disabled")):
            raise RuntimeError("CHECKPOINT: Tài khoản bị đăng xuất hoặc dính kiểm tra danh tính (Checkpoint).")

        body_text = pg.locator("body").inner_text() or ""
        body_lower = body_text.lower()

        # 1. Thẩm định quyền đăng bài & tình trạng nhóm
        if "nội dung này hiện không khả dụng" in body_lower or "this content isn't available" in body_lower:
            raise RuntimeError("NHÓM_KHÔNG_KHẢ_DỤNG: Nhóm Facebook không tồn tại, đã đóng cửa hoặc tài khoản bị chặn xem.")

        has_join_btn = (
            pg.locator("div[aria-label='Tham gia nhóm'], div[aria-label='Join group'], div[role='button']:has-text('Tham gia nhóm'), div[role='button']:has-text('Join group')").count() > 0 
            or ("tham gia nhóm" in body_lower and "đã tham gia" not in body_lower)
        )
        if has_join_btn:
            raise RuntimeError("CHƯA_THAM_GIA_NHÓM: Tài khoản chưa gia nhập hoặc chưa được duyệt vào nhóm này.")

        has_cancel_btn = (
            pg.locator("div[aria-label='Hủy yêu cầu'], div[aria-label='Cancel request'], div[role='button']:has-text('Hủy yêu cầu'), div[role='button']:has-text('Cancel request')").count() > 0 
            or "hủy yêu cầu" in body_lower
        )
        if has_cancel_btn:
            raise RuntimeError("ĐANG_CHỜ_DUYỆT_JOIN: Yêu cầu tham gia nhóm vẫn đang ở trạng thái chờ Admin duyệt.")

        is_admin_only = any(term in body_lower for term in [
            "chỉ quản trị viên mới có thể đăng bài",
            "chỉ quản trị viên mới có quyền đăng",
            "only admins can post",
            "bạn đã bị hạn chế đăng bài",
            "bạn không thể đăng bài",
            "quyền đăng bài của bạn đã bị tạm dừng",
            "nhóm này hiện không chấp nhận bài viết mới"
        ])
        if is_admin_only:
            raise RuntimeError("NHÓM_CHỈ_CHO_ADMIN_ĐĂNG: Nhóm chỉ cho phép Quản trị viên đăng bài hoặc tài khoản bị hạn chế.")

        _scroll(pg)

        # 2. Tìm nút bấm kích hoạt khung tạo bài viết
        trigger_selectors = [
            "div[role='button']:has-text('Bạn viết gì đi')",
            "div[role='button']:has-text('Bạn đang viết gì thế')",
            "div[role='button']:has-text('Bạn đang nghĩ gì')",
            "div[role='button']:has-text('Bạn đang nghĩ gì thế')",
            "div[role='button']:has-text('Write something')",
            "div[role='button']:has-text('Tạo bài viết')",
            "div[role='button']:has-text('Tạo bài viết công khai')",
            "div[role='button']:has-text('on your mind')",
            "div[aria-label*='Tạo bài viết']",
            "div[aria-label*='Bạn đang nghĩ gì']",
            "div[aria-label*='Bạn viết gì đi']",
            "div[aria-label*='Write something']",
            "div[aria-label*='on your mind']",
            "span:has-text('Bạn viết gì đi')",
            "span:has-text('Bạn đang viết gì thế')",
            "span:has-text('Bạn đang nghĩ gì')",
            "span:has-text('Write something')",
            "span:has-text('on your mind')"
        ]

        trigger = None
        for sel in trigger_selectors:
            try:
                loc = pg.locator(sel).first
                if loc.is_visible(timeout=1500):
                    trigger = loc
                    break
            except Exception:
                pass

        if not trigger:
            raise RuntimeError("KHÔNG_TÌM_THẤY_Ô_TẠO_BÀI: Không tìm thấy nút đăng bài (có thể nhóm bắt buộc duyệt hoặc chưa load xong giao diện).")

        trigger.click()
        pg.wait_for_timeout(2500)

        # 3. Tìm popup hộp thoại soạn bài đang hiển thị thực tế (tránh dialog ẩn)
        dialog = None
        for _ in range(8):
            candidates = pg.locator("div[role='dialog']").all()
            for d in candidates:
                try:
                    if d.is_visible():
                        d_text = (d.inner_text() or "").lower()
                        if any(k in d_text for k in ["tạo bài viết", "create post", "bài viết", "thêm vào bài", "đăng"]):
                            dialog = d
                            break
                        elif not dialog:
                            dialog = d
                except Exception:
                    pass
            if dialog and dialog.is_visible():
                break
            pg.wait_for_timeout(500)

        # Nếu không có dialog, kiểm tra inline composer trực tiếp trên bảng tin
        if not dialog or not dialog.is_visible():
            inline_textbox = pg.locator("div[data-pagelet='GroupInlineComposer'] div[role='textbox'], div[role='main'] div[role='textbox']").first
            if inline_textbox.is_visible():
                dialog = pg.locator("div[data-pagelet='GroupInlineComposer'], div[role='main']").first

        if not dialog or not dialog.is_visible():
            raise RuntimeError("KHÔNG_MỞ_ĐƯỢC_POPUP: Popup soạn bài không hiển thị sau khi bấm.")

        # 4. Tìm ô nhập văn bản và chèn nội dung bài viết
        textbox = dialog.locator("div[role='textbox'], div[contenteditable='true']").first
        if not textbox.is_visible(timeout=3000):
            textbox = pg.locator("div[role='dialog'] div[role='textbox'], div[contenteditable='true']").first

        if not textbox.is_visible(timeout=2000):
            raise RuntimeError("KHÔNG_TÌM_THẤY_Ô_NHẬP_LIỆU: Không tìm thấy textbox để gõ nội dung bài viết.")

        textbox.click()
        pg.wait_for_timeout(600)

        # Sử dụng insert_text: Tốc độ tức thì, 100% giữ nguyên dấu tiếng Việt và emoji
        pg.keyboard.insert_text(caption)
        pg.wait_for_timeout(1500)

        # 5. Đính kèm hình ảnh sản phẩm (nếu có)
        image_attached = False
        if image_path:
            image_attached = self._attach(dialog, image_path)

        # 6. Xử lý Chạy Thử (Dry Run)
        if dry_run:
            logger.info(f"[DRY RUN] Đã soạn xong bài trên nhóm {group_url}. Hủy đăng do bật Dry Run.")
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(1000)
            return {
                "status": "dry_run",
                "comment_status": "none",
                "post_url": None,
                "has_image": image_attached,
                "message": "Chạy thử (Dry Run) hoàn tất: Soạn bài thành công nhưng không bấm nút Đăng."
            }

        # 7. Tìm nút 'Đăng' / 'Post'
        submit_selectors = [
            "div[aria-label='Đăng']",
            "div[aria-label='Post']",
            "div[role='button']:has-text('Đăng')",
            "div[role='button']:has-text('Post')",
            "button:has-text('Đăng')",
            "button:has-text('Post')"
        ]

        submit_btn = None
        for s in submit_selectors:
            btn = dialog.locator(s).first
            if btn.is_visible(timeout=1000):
                submit_btn = btn
                break

        if not submit_btn:
            raise RuntimeError("KHÔNG_TÌM_THẤY_NÚT_ĐĂNG: Không tìm thấy nút Đăng trong hộp thoại bài viết.")

        # QUAN TRỌNG NHẤT: Đợi nút Đăng hết bị disabled (Facebook xử lý text & ảnh mất 1-3s)
        for _ in range(14):
            is_disabled = submit_btn.get_attribute("aria-disabled")
            if is_disabled != "true":
                break
            pg.wait_for_timeout(500)

        logger.info(f"🚀 Bấm nút Đăng bài trên nhóm {group_url}...")
        submit_btn.click()
        pg.wait_for_timeout(4500)

        # 8. Kiểm tra kết quả: Có bị đưa vào hàng chờ Admin duyệt không
        body_after = pg.locator("body").inner_text().lower()
        is_pending = any(term in body_after for term in [
            "chờ phê duyệt", "pending approval", "đã được gửi đến quản trị viên", "bài viết của bạn đã được gửi"
        ])

        if is_pending:
            logger.info(f"⏳ Bài viết tại {group_url} đang chờ Admin duyệt.")
            return {
                "status": "pending_approval",
                "comment_status": "pending_approval",
                "post_url": None,
                "has_image": image_attached,
                "message": "Bài viết đã gửi thành công nhưng đang chờ Quản trị viên nhóm phê duyệt."
            }

        # 9. Đăng bình luận kèm link Affiliate (nếu có yêu cầu comment)
        comment_status = "none"
        if comment:
            cmt_ok = self._comment_latest(comment)
            comment_status = "done" if cmt_ok else "failed"

        # 10. Trích xuất permalink link bài viết vừa đăng
        post_url = self._extract_latest_post_url(group_url)

        return {
            "status": "done",
            "comment_status": comment_status,
            "post_url": post_url or group_url,
            "has_image": image_attached,
            "message": "Đã đăng bài viết công khai thành công lên nhóm Facebook!"
        }

    def _extract_latest_post_url(self, group_url: str) -> Optional[str]:
        """Trích xuất permalink của bài viết vừa đăng lên Facebook."""
        pg = self.page
        try:
            time.sleep(2)
            links = pg.locator('a[href*="/posts/"], a[href*="/permalink/"]').all()
            for l in links[:6]:
                try:
                    href = l.get_attribute("href") or ""
                    m = re.search(r"facebook\.com/groups/([^/?#]+)/(posts|permalink)/(\d+)", href)
                    if m:
                        return f"https://www.facebook.com/groups/{m.group(1)}/posts/{m.group(3)}/"
                    if "/posts/" in href or "/permalink/" in href:
                        clean_url = href.split("?")[0]
                        if not clean_url.startswith("http"):
                            clean_url = f"https://www.facebook.com{clean_url}"
                        return clean_url
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Không lấy được permalink: {e}")
        return None

    def _attach(self, dlg, image_path: str) -> bool:
        """Đính kèm ảnh vào bài viết Facebook an toàn và tin cậy."""
        pg = self.page
        if not image_path or not str(image_path).strip():
            return False

        image_path = str(image_path).strip()
        if not os.path.isabs(image_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cand1 = os.path.join(base_dir, image_path)
            cand2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), image_path)
            if os.path.exists(cand1):
                image_path = cand1
            elif os.path.exists(cand2):
                image_path = cand2

        if not os.path.exists(image_path):
            logger.warning(f"⚠️ File ảnh không tồn tại: {image_path}")
            return False

        try:
            # 1. Tìm input upload trực tiếp trong dialog
            file_input = dlg.locator("input[type='file'][accept*='image'], input[type='file']").first
            if file_input.count() == 0:
                # 2. Nếu chưa render, click nút Ảnh/video để mở input
                photo_btn_selectors = [
                    "div[aria-label*='Ảnh/video']",
                    "div[aria-label*='Photo/video']",
                    "div[role='button']:has-text('Ảnh/video')",
                    "div[role='button']:has-text('Photo/video')",
                    "div[aria-label*='Thêm vào bài viết của bạn'] div[role='button']",
                    "span:has-text('Ảnh/video')"
                ]
                for p_sel in photo_btn_selectors:
                    p_btn = dlg.locator(p_sel).first
                    if p_btn.is_visible(timeout=1000):
                        p_btn.click()
                        pg.wait_for_timeout(1200)
                        break

            file_input = dlg.locator("input[type='file'][accept*='image'], input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(str(image_path))
                pg.wait_for_timeout(3500)
                logger.info(f"📸 Đã đính kèm ảnh thành công: {os.path.basename(image_path)}")
                return True
            else:
                logger.warning("Không tìm thấy input file upload ảnh trên Facebook.")
                return False
        except Exception as e:
            logger.warning(f"Lỗi đính kèm ảnh: {e}")
            return False

    def _comment_latest(self, comment: str) -> bool:
        """Đăng bình luận vào bài viết vừa đăng trên group."""
        pg = self.page
        _pause(2.5, 4.5)
        try:
            cmt_btn = pg.get_by_role("button", name=re.compile(r"^(Bình luận|Comment)$", re.I)).first
            if cmt_btn.is_visible():
                cmt_btn.click()
                _pause(1, 2)

            cmt_box = pg.locator(
                'div[role="textbox"][aria-label*="Bình luận"], div[role="textbox"][aria-label*="Comment"], div[role="textbox"][aria-label*="Viết bình luận"]'
            ).first

            if cmt_box.is_visible():
                cmt_box.click()
                _pause(0.5, 1)
                pg.keyboard.insert_text(comment)
                _pause(1, 1.5)
                pg.keyboard.press("Enter")
                _pause(3, 4)
                logger.info("💬 Đã đăng comment link thành công!")
                return True
            else:
                logger.warning("Không tìm thấy ô nhập comment trực tiếp.")
                return False
        except Exception as e:
            logger.warning(f"Lỗi khi đăng comment: {e}")
            return False

    def retry_comment_on_post(self, group_url: str, caption_snippet: str, comment: str) -> bool:
        """Mở lại group tìm bài đã được duyệt và bình luận bổ sung link."""
        pg = self.page
        pg.goto(group_url, wait_until="domcontentloaded", timeout=40000)
        _pause(4, 7)
        if any(k in pg.url for k in ("checkpoint", "login")):
            raise RuntimeError("CHECKPOINT")

        _scroll(pg)
        clean_snippet = caption_snippet.split("\n")[0][:25].strip()
        loc = pg.locator(f"text={clean_snippet}").first

        try:
            if loc.is_visible():
                loc.scroll_into_view_if_needed()
                _pause(1, 2)
                return self._comment_latest(comment)
        except Exception as e:
            logger.warning(f"Lỗi retry comment: {e}")
        return False

    def warmup(self):
        """Nuôi nick nhẹ: lướt newsfeed, đọc bài, thả tim ngẫu nhiên."""
        pg = self.page
        pg.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=40000)
        _pause(3, 6)
        if any(k in pg.url for k in ("checkpoint", "login")):
            raise RuntimeError("CHECKPOINT")

        logger.info(f"[WARMUP] Bắt đầu lướt feed cho nick {self.acc.get('name')}...")
        for _ in range(random.randint(4, 8)):
            pg.mouse.wheel(0, random.randint(300, 700))
            _pause(3, 7)

        try:
            like_buttons = pg.locator('div[role="button"][aria-label="Thích"], div[role="button"][aria-label="Like"]').all()
            if like_buttons:
                target_btn = random.choice(like_buttons[:4])
                if target_btn.is_visible():
                    target_btn.scroll_into_view_if_needed()
                    _pause(1, 2)
                    target_btn.click()
                    logger.info(f"[WARMUP] Đã thả tim 1 bài viết tự nhiên cho nick {self.acc.get('name')}.")
                    _pause(2, 4)
        except Exception as e:
            logger.debug(f"[WARMUP LIKE NOTICE]: {e}")

    def close(self):
        try:
            self.page.close()
        except Exception:
            pass
        try:
            self.ctx.close()
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass


def _pause(a, b):
    time.sleep(random.uniform(a, b))

def _scroll(pg):
    for _ in range(random.randint(1, 3)):
        pg.mouse.wheel(0, random.randint(300, 900))
        _pause(0.8, 1.8)


# =============================================================================
# MATCHING & PREPARATION HELPERS
# =============================================================================

def find_best_deal_for_group(group: Dict, convert_aff: bool = False) -> Optional[Dict]:
    """Tìm deal chuẩn nhất cho nhóm Facebook theo ngành hàng."""
    matcher = CategoryMatcher()
    deal = matcher.find_best_deal_for_group(group, db)
    if deal and convert_aff:
        deal["aff_url"] = dealmod.ensure_deal_aff_link(deal)
    return deal

def get_group_matched_deals() -> Dict[str, Any]:
    """Lấy danh sách deal tương ứng cho toàn bộ các nhóm Facebook chuyên Đăng bài."""
    groups = db.q("SELECT * FROM groups WHERE status IN ('joined', 'approved', 'candidate') AND (target_type IS NULL OR target_type='posting')")
    result = {}
    for g in groups:
        d = find_best_deal_for_group(dict(g))
        if d:
            result[g["url"]] = {
                "id": d["id"],
                "title": d["title"],
                "price": d["price"],
                "orig_price": d.get("orig_price"),
                "discount": d.get("discount"),
                "image": d.get("image") or d.get("image_path"),
                "niche": d.get("niche"),
                "aff_url": d.get("aff_url") or d.get("url")
            }
    return result

def compose_post_for_deal(deal: Dict, group: Dict, account_name: str, cfg: Dict, link_in_comment: Optional[bool] = None) -> Tuple[str, Optional[str], Optional[str]]:
    """Tạo caption, comment và đường dẫn ảnh tối ưu cho bài đăng.
    - link_in_comment = False (Mặc định): Chèn link Shopee Affiliate trực tiếp trong bài viết, comment = None.
    - link_in_comment = True: Để link ở bình luận 1, caption không chứa link.
    """
    p_cfg = cfg.get("posting", {})
    if link_in_comment is None:
        link_in_comment = p_cfg.get("link_in_comment", False)

    aff_url, sub_id = build_subid_link(
        deal.get("aff_url") or deal.get("url") or "",
        account=account_name,
        group_url=group.get("url", ""),
        item_id=deal.get("id", ""),
        angle="deal"
    )

    price_str = f"{int(deal.get('price', 0)):,}đ" if deal.get("price") else "giá sốc"
    orig_str = f"{int(deal.get('orig_price', 0)):,}đ" if deal.get("orig_price") else ""
    discount_str = f"-{int(deal.get('discount', 0))}%" if deal.get("discount") else ""

    cap = (
        f"🔥 DEAL HOT GIẢM SỐC HÔM NAY!\n"
        f"⚡ {deal.get('title')}\n"
        f"💰 Giá sale chỉ: {price_str} {f'(Gốc {orig_str} {discount_str})' if orig_str else ''}\n"
        f"⭐ Đánh giá: {deal.get('rating', 5.0)}★ • Đã bán {deal.get('sold', 0):,} lượt\n\n"
        f"Nhanh tay săn ngay trong khung giờ vàng kẻo hết ưu đãi nha cả nhà! 👇"
    )

    funnel_cta = (cfg.get("funnel") or {}).get("cta_text", "👉 Tham gia nhóm săn sale Telegram để nhận voucher sớm nhất: {invite_link}")
    t_invite = (cfg.get("funnel") or {}).get("telegram_invite", "")
    if "{invite_link}" in funnel_cta and t_invite:
        funnel_cta = funnel_cta.replace("{invite_link}", t_invite)

    comment = None
    if link_in_comment:
        # Luồng 2: Để link ở bình luận
        comment = f"👉 Link mua săn deal chính hãng Shopee: {aff_url}"
        if funnel_cta and (cfg.get("funnel") or {}).get("include_in_comment", True):
            comment += f"\n{funnel_cta}"
    else:
        # Luồng 1 (Mặc định): Chèn link trực tiếp vào bài viết, KHÔNG COMMENT
        cap += f"\n\n👉 Link mua chính hãng Shopee tại đây: {aff_url}"
        if funnel_cta and (cfg.get("funnel") or {}).get("include_in_caption", False):
            cap += f"\n{funnel_cta}"
        comment = None

    # Lấy đường dẫn ảnh
    image_path = deal.get("image_path")
    if not image_path or not os.path.exists(image_path):
        image_path = deal.get("image")

    return cap, comment, image_path


# =============================================================================
# GRADUAL / SEQUENTIAL POSTING ENGINE
# =============================================================================

def get_gradual_posting_status() -> Dict:
    """Lấy trạng thái chu trình đăng bài dần."""
    return gradual_posting_state

def stop_gradual_posting():
    """Yêu cầu dừng chu trình đăng bài dần ngay lập tức."""
    global gradual_posting_state
    gradual_posting_state["is_running"] = False
    gradual_posting_state["status"] = "STOPPED"
    logger.info("Đã gửi tín hiệu dừng chu trình đăng bài dần theo yêu cầu người dùng.")
    return {"success": True, "message": "Đã gửi tín hiệu dừng chu trình đăng bài dần."}

def run_gradual_posting(
    cfg: Dict,
    group_urls: Optional[List[str]] = None,
    delay_seconds: int = 60,
    account_name: Optional[str] = None,
    dry_run: bool = False,
    link_in_comment: Optional[bool] = None
) -> List[Dict]:
    """
    Chu trình đăng bài tuần tự vào danh sách nhóm Facebook có nhịp nghỉ an toàn chống spam.
    Cập nhật countdown và trạng thái theo thời gian thực để UI hiển thị.
    Chỉ đăng vào các nhóm Đăng Bài (target_type='posting' hoặc NULL).
    """
    global gradual_posting_state
    gradual_posting_state["is_running"] = True
    gradual_posting_state["completed"] = 0
    gradual_posting_state["status"] = "RUNNING"
    gradual_posting_state["delay_seconds"] = delay_seconds
    gradual_posting_state["history"] = []

    # 1. Thu thập danh sách nhóm mục tiêu (CHỈ LẤY NHÓM ĐĂNG BÀI BÁN HÀNG)
    if group_urls and len(group_urls) > 0:
        placeholders = ",".join(["?"] * len(group_urls))
        rows = db.q(f"SELECT * FROM groups WHERE url IN ({placeholders}) AND (target_type IS NULL OR target_type='posting')", tuple(group_urls))
        target_groups = [dict(r) for r in rows]
    else:
        rows = db.q("""
            SELECT * FROM groups 
            WHERE status IN ('joined', 'approved')
            AND (target_type IS NULL OR target_type='posting')
            ORDER BY 
                CASE WHEN last_posted_at IS NULL OR last_posted_at = 0 THEN 0 ELSE 1 END,
                last_posted_at ASC,
                priority_score DESC
        """)
        target_groups = [dict(r) for r in rows]

    total_target = len(target_groups)
    gradual_posting_state["total_target"] = total_target

    if not target_groups:
        gradual_posting_state["is_running"] = False
        gradual_posting_state["status"] = "NO_GROUPS"
        return []

    accs_list = cfg.get("accounts", [])
    if not accs_list:
        gradual_posting_state["is_running"] = False
        gradual_posting_state["status"] = "NO_ACCOUNTS"
        return []

    results = []
    with sync_playwright() as pw:
        sessions: Dict[str, AccountSession] = {}

        for idx, group in enumerate(target_groups, 1):
            if not gradual_posting_state["is_running"]:
                break

            g_url = group["url"]
            g_name = group.get("name") or extract_group_tag(g_url)

            # Chọn nick: Nếu chọn cố định thì dùng nick đó, nếu không thì xoay tua hoặc dùng nick gán
            if account_name:
                cur_acc_name = account_name
            elif group.get("account"):
                cur_acc_name = group["account"]
            else:
                cur_acc_name = accs_list[(idx - 1) % len(accs_list)]["name"]

            acc_dict = next((a for a in accs_list if a["name"] == cur_acc_name), accs_list[0])

            gradual_posting_state["current_group"] = g_name
            gradual_posting_state["current_account"] = cur_acc_name

            # Khớp deal chuẩn ngành
            deal = find_best_deal_for_group(group, convert_aff=True)
            deal_title = deal.get("title", "Bài săn sale tổng hợp") if deal else "Săn deal Shopee"
            gradual_posting_state["current_deal"] = deal_title[:35]

            logger.info(f"\n--- [{idx}/{total_target}] Đăng bài nhóm '{g_name}' bằng nick '{cur_acc_name}' ---")

            res_item: Dict[str, Any] = {
                "group_url": g_url,
                "group_name": g_name,
                "account": cur_acc_name,
                "deal_id": deal.get("id") if deal else None,
                "deal_title": deal_title,
                "time": datetime.now().strftime("%H:%M:%S")
            }

            try:
                if cur_acc_name not in sessions:
                    sessions[cur_acc_name] = AccountSession(pw, acc_dict, headless=True)
                    if not sessions[cur_acc_name].healthy():
                        raise RuntimeError("CHECKPOINT: Tài khoản hết hạn cookie hoặc bị checkpoint.")

                caption, comment, image_path = compose_post_for_deal(deal or {}, group, cur_acc_name, cfg, link_in_comment=link_in_comment)

                post_res = sessions[cur_acc_name].post(
                    group_url=g_url,
                    caption=caption,
                    comment=comment,
                    dry_run=dry_run,
                    image_path=image_path
                )

                status = post_res.get("status", "done")
                c_status = post_res.get("comment_status", "none")
                post_url = post_res.get("post_url")
                now_ts = time.time()

                res_item["status"] = status
                res_item["post_url"] = post_url
                res_item["comment_status"] = c_status
                res_item["message"] = post_res.get("message", "Thành công")

                if not dry_run:
                    # Ghi nhận lịch sử bài đăng
                    c_retry_at = (now_ts + 45 * 60) if c_status == "pending_approval" else 0
                    db.x("""
                        INSERT INTO posts (deal_id, group_url, account, caption, comment, image_path, kind, status, comment_status, comment_retry_at, scheduled_at, posted_at, post_url)
                        VALUES (?, ?, ?, ?, ?, ?, 'deal', ?, ?, ?, ?, ?, ?)
                    """, (
                        deal.get("id") if deal else "",
                        g_url,
                        cur_acc_name,
                        caption,
                        comment or "",
                        image_path or "",
                        status,
                        c_status,
                        c_retry_at,
                        now_ts,
                        now_ts,
                        post_url
                    ))

                    # Cập nhật thông số nhóm: Phân biệt rõ đăng thẳng thành công vs bài bị giữ lại chờ duyệt
                    if status == "done":
                        db.x("""
                            UPDATE groups SET 
                                last_posted_at=?, 
                                success_count=success_count+1, 
                                consecutive_fails=0, 
                                priority_score=MIN(200.0, priority_score + 5.0) 
                            WHERE url=?
                        """, (now_ts, g_url))
                    elif status == "pending_approval":
                        db.x("""
                            UPDATE groups SET 
                                last_posted_at=?, 
                                priority_score=MAX(20.0, priority_score - 10.0), 
                                last_error='⏳ Bài viết bị đưa vào hàng chờ Admin duyệt (Pending)' 
                            WHERE url=?
                        """, (now_ts, g_url))

                    if deal and deal.get("id"):
                        db.x("UPDATE deals SET status='posted', posted_count=COALESCE(posted_count, 0)+1, last_posted_at=? WHERE id=?", (now_ts, deal["id"]))

            except Exception as e:
                err_msg = str(e)
                logger.error(f"❌ Lỗi đăng nhóm {g_name}: {err_msg}")
                res_item["status"] = "failed"
                res_item["error"] = err_msg
                res_item["message"] = f"Lỗi: {err_msg}"

                if not dry_run:
                    db.x("""
                        UPDATE groups SET 
                            fail_count=fail_count+1, 
                            consecutive_fails=consecutive_fails+1, 
                            priority_score=MAX(10.0, priority_score - 20.0), 
                            last_error=? 
                        WHERE url=?
                    """, (err_msg[:200], g_url))

            results.append(res_item)
            gradual_posting_state["completed"] += 1
            gradual_posting_state["last_result"] = res_item
            gradual_posting_state["history"].append(res_item)

            # Áp dụng nhịp nghỉ an toàn (Delay) nếu chưa phải nhóm cuối
            if idx < total_target and gradual_posting_state["is_running"]:
                eff_delay = delay_seconds if delay_seconds > 0 else 60
                next_t = datetime.fromtimestamp(time.time() + eff_delay).strftime("%H:%M:%S")
                gradual_posting_state["next_post_time"] = next_t
                gradual_posting_state["remaining_delay"] = eff_delay
                logger.info(f"⏳ [NHỊP NGHỈ AN TOÀN]: Nghỉ {eff_delay}s chống spam Facebook. Nhóm tiếp theo sẽ đăng lúc {next_t}...")

                slept = 0
                while slept < eff_delay and gradual_posting_state["is_running"]:
                    time.sleep(1)
                    slept += 1
                    gradual_posting_state["remaining_delay"] = max(0, eff_delay - slept)

        for s in sessions.values():
            s.close()

    gradual_posting_state["is_running"] = False
    gradual_posting_state["remaining_delay"] = 0
    gradual_posting_state["status"] = "FINISHED"
    logger.info(f"🎉 Hoàn thành phiên đăng bài dần: {len(results)}/{total_target} nhóm.")
    return results


def post_single_group(
    cfg: Dict,
    group_url: str,
    deal_id: Optional[str] = None,
    account_name: Optional[str] = None,
    dry_run: bool = False,
    custom_caption: Optional[str] = None,
    link_in_comment: Optional[bool] = None
) -> Dict:
    """Đăng bài ngay lập tức vào một nhóm Facebook cụ thể (Chỉ dành cho nhóm Đăng Bài)."""
    g_row = db.q("SELECT * FROM groups WHERE url=?", (group_url,), one=True)
    if not g_row:
        return {"success": False, "message": f"Không tìm thấy nhóm '{group_url}' trong CSDL."}

    group = dict(g_row)
    if group.get("target_type") == "lazada_hunter":
        return {
            "success": False,
            "message": f"Nhóm '{group.get('name') or group_url}' là nhóm chuyên Dùng Để Quét Giá Thị Trường Lazada (target_type='lazada_hunter'). Hệ thống tách biệt hoàn toàn và không cho phép đăng bài bán hàng vào nhóm này!"
        }

    accs_list = cfg.get("accounts", [])
    if not accs_list:
        return {"success": False, "message": "Chưa có tài khoản Facebook nào được cấu hình trong hệ thống."}

    cur_acc_name = account_name or group.get("account") or accs_list[0]["name"]
    acc_dict = next((a for a in accs_list if a["name"] == cur_acc_name), accs_list[0])

    # Lấy deal
    if deal_id:
        d_row = db.q("SELECT * FROM deals WHERE id=?", (deal_id,), one=True)
        deal = dict(d_row) if d_row else None
    else:
        deal = find_best_deal_for_group(group, convert_aff=True)

    with sync_playwright() as pw:
        sess = None
        try:
            sess = AccountSession(pw, acc_dict, headless=True)
            if not sess.healthy():
                return {"success": False, "message": f"Tài khoản '{cur_acc_name}' hết hạn cookie hoặc bị checkpoint."}

            if custom_caption:
                caption = custom_caption
                comment = None
                image_path = deal.get("image_path") if deal else None
            else:
                caption, comment, image_path = compose_post_for_deal(deal or {}, group, cur_acc_name, cfg, link_in_comment=link_in_comment)

            post_res = sess.post(
                group_url=group_url,
                caption=caption,
                comment=comment,
                dry_run=dry_run,
                image_path=image_path
            )

            status = post_res.get("status", "done")
            c_status = post_res.get("comment_status", "none")
            post_url = post_res.get("post_url")
            now_ts = time.time()

            if not dry_run:
                c_retry_at = (now_ts + 45 * 60) if c_status == "pending_approval" else 0
                db.x("""
                    INSERT INTO posts (deal_id, group_url, account, caption, comment, image_path, kind, status, comment_status, comment_retry_at, scheduled_at, posted_at, post_url)
                    VALUES (?, ?, ?, ?, ?, ?, 'deal', ?, ?, ?, ?, ?, ?)
                """, (
                    deal.get("id") if deal else "",
                    group_url,
                    cur_acc_name,
                    caption,
                    comment or "",
                    image_path or "",
                    status,
                    c_status,
                    c_retry_at,
                    now_ts,
                    now_ts,
                    post_url
                ))

                if status == "done":
                    db.x("""
                        UPDATE groups SET 
                            last_posted_at=?, 
                            success_count=success_count+1, 
                            consecutive_fails=0, 
                            priority_score=MIN(200.0, priority_score + 5.0) 
                        WHERE url=?
                    """, (now_ts, group_url))
                elif status == "pending_approval":
                    db.x("""
                        UPDATE groups SET 
                            last_posted_at=?, 
                            priority_score=MAX(20.0, priority_score - 10.0), 
                            last_error='⏳ Bài viết bị đưa vào hàng chờ Admin duyệt (Pending)' 
                        WHERE url=?
                    """, (now_ts, group_url))

                if deal and deal.get("id"):
                    db.x("UPDATE deals SET status='posted', posted_count=COALESCE(posted_count, 0)+1, last_posted_at=? WHERE id=?", (now_ts, deal["id"]))

            return {
                "success": True,
                "status": status,
                "comment_status": c_status,
                "post_url": post_url,
                "account": cur_acc_name,
                "deal_title": deal.get("title") if deal else "Tổng hợp",
                "message": post_res.get("message") or f"Đã đăng thành công lên nhóm '{group.get('name')}'!"
            }
        except Exception as e:
            err = str(e)
            logger.error(f"Lỗi đăng nhóm {group_url}: {err}")
            return {"success": False, "message": f"Lỗi khi đăng bài: {err}"}
        finally:
            if sess:
                sess.close()


# =============================================================================
# BACKWARD COMPATIBLE EXPORTS
# =============================================================================

def run_due(cfg: Dict):
    """Đăng các bài đến giờ hẹn trong bảng posts."""
    now = time.time()
    p = cfg["posting"]
    due = db.q("SELECT * FROM posts WHERE status='queued' AND scheduled_at<=? ORDER BY scheduled_at LIMIT 3", (now,))
    pending_cmts = db.q("SELECT * FROM posts WHERE comment_status='pending_approval' AND comment_retry_at<=? AND comment_retries<3 LIMIT 2", (now,))

    if not due and not pending_cmts:
        return

    accs = {a["name"]: a for a in cfg["accounts"]}
    with sync_playwright() as pw:
        sessions: Dict[str, AccountSession] = {}

        for post in due:
            name = post["account"]
            a = db.q("SELECT * FROM accounts WHERE name=?", (name,), one=True)
            if a and a["paused_until"] > now:
                continue

            done_today = db.q("SELECT COUNT(*) c FROM posts WHERE account=? AND status='done' AND posted_at>?",
                              (name, db.today_start()), one=True)["c"]
            if done_today >= p["max_posts_per_account_per_day"]:
                continue

            if post["kind"] == "deal":
                deal = db.q("SELECT * FROM deals WHERE id=?", (post["deal_id"],), one=True)
                if not dealmod.still_valid(deal):
                    db.x("UPDATE posts SET status='skipped', error='deal expired' WHERE id=?", (post["id"],))
                    continue

            try:
                if name not in sessions:
                    sessions[name] = AccountSession(pw, accs[name])
                    if not sessions[name].healthy():
                        raise RuntimeError("CHECKPOINT")

                res = sessions[name].post(
                    post["group_url"], post["caption"], post["comment"], 
                    cfg.get("dry_run", False), post["image_path"]
                )

                if not cfg.get("dry_run", False):
                    c_status = res.get("comment_status", "none")
                    post_url = res.get("post_url")
                    c_retry_at = (now + 45 * 60) if c_status == "pending_approval" else 0
                    
                    db.x("""UPDATE posts SET status='done', posted_at=?, post_url=?, comment_status=?, comment_retry_at=? 
                            WHERE id=?""", (now, post_url, c_status, c_retry_at, post["id"]))

                    if post.get("kind") == "deal" and post.get("deal_id"):
                        db.x("""UPDATE deals SET 
                                status='posted', 
                                posted_count=COALESCE(posted_count, 0) + 1, 
                                last_posted_at=? 
                                WHERE id=?""", (now, post["deal_id"]))

                    if res.get("status") == "done":
                        db.x("""UPDATE groups SET 
                                last_posted_at=?, 
                                success_count=success_count+1, 
                                consecutive_fails=0, 
                                priority_score=MIN(200.0, priority_score + 5.0) 
                                WHERE url=?""", (now, post["group_url"]))
                    elif res.get("status") == "pending_approval":
                        db.x("""UPDATE groups SET 
                                last_posted_at=?, 
                                priority_score=MAX(20.0, priority_score - 10.0), 
                                last_error='⏳ Bài viết bị đưa vào hàng chờ Admin duyệt (Pending)' 
                                WHERE url=?""", (now, post["group_url"]))

                _pause(10, 20)

            except Exception as e:
                msg = str(e)
                db.x("UPDATE posts SET status='failed', error=? WHERE id=?", (msg[:300], post["id"]))
                db.x("""UPDATE groups SET 
                        fail_count=fail_count+1, 
                        consecutive_fails=consecutive_fails+1, 
                        priority_score=MAX(10.0, priority_score - 20.0), 
                        last_error=? 
                        WHERE url=?""", (msg[:200], post["group_url"]))

        for post in pending_cmts:
            name = post["account"]
            if name not in sessions:
                sessions[name] = AccountSession(pw, accs[name])
                if not sessions[name].healthy():
                    continue

            ok = sessions[name].retry_comment_on_post(post["group_url"], post["caption"], post["comment"])
            retries = (post["comment_retries"] or 0) + 1
            if ok:
                db.x("UPDATE posts SET comment_status='done', comment_retry_at=0, comment_retries=? WHERE id=?", (retries, post["id"]))
                tg(f"💬 Group {extract_group_tag(post['group_url'])}: Bài đã được duyệt, bot đã bổ sung comment link aff thành công!")
            else:
                if retries < 3:
                    db.x("UPDATE posts SET comment_retries=?, comment_retry_at=? WHERE id=?", (retries, now + 60 * 60, post["id"]))
                else:
                    db.x("UPDATE posts SET comment_status='failed', comment_retries=? WHERE id=?", (retries, post["id"]))

        for s in sessions.values():
            s.close()


def post_single(cfg: Dict, post: Dict) -> Dict:
    """Thực thi đăng ngay 1 bài từ hàng đợi posts."""
    now = time.time()
    name = post["account"]
    accs = {a["name"]: a for a in cfg.get("accounts", [])}
    if name not in accs:
        return {"success": False, "message": f"Tài khoản '{name}' không có trong cấu hình accounts."}

    with sync_playwright() as pw:
        sess = None
        try:
            sess = AccountSession(pw, accs[name])
            if not sess.healthy():
                db.x("INSERT OR REPLACE INTO accounts(name,paused_until) VALUES(?,?)", (name, now + 3 * 86400))
                return {"success": False, "message": f"Tài khoản {name} dính checkpoint hoặc hết hạn cookie Facebook."}

            res = sess.post(
                post["group_url"], post["caption"], post["comment"],
                cfg.get("dry_run", False), post["image_path"]
            )

            status = res.get("status", "done")
            c_status = res.get("comment_status", "none")
            post_url = res.get("post_url")
            c_retry_at = (now + 45 * 60) if c_status == "pending_approval" else 0

            db.x("""UPDATE posts SET status=?, posted_at=?, post_url=?, comment_status=?, comment_retry_at=?
                    WHERE id=?""", (status, now, post_url, c_status, c_retry_at, post["id"]))

            if status == "done":
                db.x("""UPDATE groups SET last_posted_at=?, success_count=success_count+1, consecutive_fails=0,
                        priority_score=MIN(200.0, priority_score + 5.0) WHERE url=?""", (now, post["group_url"]))

                if post.get("kind") == "deal" and post.get("deal_id"):
                    db.x("UPDATE deals SET status='posted', posted_count=COALESCE(posted_count, 0)+1, last_posted_at=? WHERE id=?", (now, post["deal_id"]))
            elif status == "pending_approval":
                db.x("""UPDATE groups SET last_posted_at=?, priority_score=MAX(20.0, priority_score - 10.0),
                        last_error='⏳ Bài viết bị đưa vào hàng chờ Admin duyệt (Pending)' WHERE url=?""", (now, post["group_url"]))

            return {
                "success": True,
                "status": status,
                "comment_status": c_status,
                "post_url": post_url,
                "message": f"Đã đăng bài #{post['id']} thành công ({status})!"
            }
        except Exception as e:
            err = str(e)
            db.x("UPDATE posts SET status='failed', error=? WHERE id=?", (err[:300], post["id"]))
            return {"success": False, "message": f"Lỗi khi đăng bài: {err}"}
        finally:
            if sess:
                sess.close()


def test_post(cfg: Dict, account_name: str, group_url: str, caption: str, comment: str = "", dry_run: bool = False, image_path: str = None) -> dict:
    """Thử nghiệm đăng bài trực tiếp bằng Playwright và trả về kết quả kèm link bài đăng."""
    accs = {a["name"]: a for a in cfg.get("accounts", [])}
    if account_name not in accs:
        return {"success": False, "message": f"Tài khoản '{account_name}' không tồn tại trong cấu hình."}

    acc = accs[account_name]
    with sync_playwright() as pw:
        sess = None
        try:
            sess = AccountSession(pw, acc)
            if not sess.healthy():
                return {"success": False, "message": f"Tài khoản '{account_name}' dính checkpoint hoặc hết hạn cookie Facebook."}

            res = sess.post(
                group_url=group_url,
                caption=caption,
                comment=comment,
                dry_run=dry_run,
                image_path=image_path
            )

            status = res.get("status", "done")
            c_status = res.get("comment_status", "none")
            post_url = res.get("post_url")

            msg = "Đăng bài thành công!" if not dry_run else "Chạy thử (Dry Run) hoàn tất (không tạo bài thật)!"
            return {
                "success": True,
                "status": status,
                "comment_status": c_status,
                "post_url": post_url,
                "dry_run": dry_run,
                "message": msg
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi trong quá trình đăng thử nghiệm: {str(e)}"}
        finally:
            if sess:
                sess.close()


def warmup_accounts(cfg: Dict):
    """Thực hiện phiên nuôi nick nhẹ nhàng."""
    now = time.time()
    accs = cfg.get("accounts", [])
    with sync_playwright() as pw:
        for acc in accs:
            row = db.q("SELECT * FROM accounts WHERE name=?", (acc["name"],), one=True)
            if row and row["paused_until"] > now:
                continue
            if row and (now - (row["last_warmup_at"] or 0) < 14400):
                continue

            try:
                sess = AccountSession(pw, acc)
                if sess.healthy():
                    sess.warmup()
                    db.x("INSERT OR REPLACE INTO accounts(name,last_warmup_at) VALUES(?,?)", (acc["name"], now))
                sess.close()
            except Exception as e:
                logger.warning(f"[WARMUP ERROR] Nick {acc['name']}: {e}")
