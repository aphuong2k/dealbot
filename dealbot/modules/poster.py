"""Module 3b: đăng bài qua Playwright bằng cookie.
Hỗ trợ:
- Kiểm tra checkpoint & tự động tạm dừng nick
- Tự động comment link sau khi đăng bài
- Phát hiện bài chờ admin duyệt -> đưa vào hàng đợi retry comment sau 30-60 phút
- Tự học & chấm điểm chất lượng nhóm (hạ điểm khi lỗi, tạm dừng khi dính 3 lỗi liên tiếp)
- Chế độ nuôi nick tự động nhẹ (lướt feed, thả tim)
"""
import json, time, random, re, db
from . import deals as dealmod
from .affiliate import extract_group_tag
from notify import tg
from playwright.sync_api import sync_playwright

class AccountSession:
    def __init__(self, pw, acc):
        self.acc = acc
        self.browser = pw.chromium.launch(headless=False)           # headless=False ít bị nghi ngờ hơn
        self.ctx = self.browser.new_context(locale="vi-VN", viewport={"width": 1280, "height": 800})
        self.ctx.add_cookies(_load_cookies(acc["cookie_file"]))
        self.page = self.ctx.new_page()

    def healthy(self):
        self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        time.sleep(random.uniform(2, 4))
        u = self.page.url
        return not any(k in u for k in ("checkpoint", "login", "two_step"))

    def post(self, group_url, caption, comment=None, dry_run=True, image_path=None):
        """
        Đăng bài vào group Facebook.
        Trả về: dict(status="done"|"pending_approval"|"dry_run", comment_status=...)
        """
        pg = self.page
        pg.goto(group_url, wait_until="domcontentloaded"); _pause(3, 6)
        if any(k in pg.url for k in ("checkpoint", "login")):
            raise RuntimeError("CHECKPOINT")
        
        _scroll(pg)
        box = pg.get_by_role("button", name=re.compile(r"(Bạn viết gì đi|Write something|Viết bài|Create (a )?public post)", re.I)).first
        box.click(); _pause(1.5, 3)
        dlg = pg.get_by_role("dialog").first
        txt = dlg.get_by_role("textbox").first
        txt.click()
        
        if image_path:
            self._attach(dlg, image_path)
            
        pg.keyboard.type(caption, delay=random.randint(40, 110)); _pause(1.5, 3)
        
        if dry_run:
            print(f"[DRY] {group_url}\n{caption}\nComment: {comment}\n---")
            pg.keyboard.press("Escape")
            return {"status": "dry_run", "comment_status": "none"}

        # Bấm nút Đăng
        dlg.get_by_role("button", name=re.compile(r"^(Đăng|Post)$", re.I)).click()
        _pause(5, 9)

        # Phát hiện bài có bị đưa vào danh sách chờ admin duyệt hay không
        pending_match = pg.locator("text=/chờ phê duyệt|pending approval|đã được gửi đến quản trị viên|bài viết của bạn đã được gửi/i")
        is_pending = False
        try:
            if pending_match.count() > 0 and pending_match.first.is_visible():
                is_pending = True
        except Exception:
            pass

        if is_pending:
            print(f"[PENDING] Bài viết tại {group_url} đang chờ admin duyệt. Hẹn giờ retry comment sau.")
            return {"status": "pending_approval", "comment_status": "pending_approval"}

        # Nếu đăng thành công trực tiếp và có comment
        comment_status = "none"
        if comment:
            cmt_ok = self._comment_latest(comment)
            comment_status = "done" if cmt_ok else "pending_approval"

        return {"status": "done", "comment_status": comment_status}

    def _attach(self, dlg, image_path):
        """Đính ảnh vào bài viết."""
        pg = self.page
        with pg.expect_file_chooser(timeout=15000) as fc:
            dlg.get_by_role("button", name=re.compile(r"(Ảnh/video|Photo/video)", re.I)).first.click()
        fc.value.set_files(image_path); _pause(3, 6)
        dlg.get_by_role("textbox").first.click()

    def _comment_latest(self, comment):
        """Thực hiện bình luận vào bài viết vừa đăng trên group."""
        pg = self.page; _pause(3, 6)
        try:
            # 1. Tìm nút 'Bình luận' / 'Comment' trên bài viết nếu ô nhập chưa mở sẵn
            cmt_btn = pg.get_by_role("button", name=re.compile(r"^(Bình luận|Comment)$", re.I)).first
            if cmt_btn.is_visible():
                cmt_btn.click(); _pause(1, 2)

            # 2. Tìm ô nhập comment
            cmt_box = pg.locator(
                'div[role="textbox"][aria-label*="Bình luận"], div[role="textbox"][aria-label*="Comment"], div[role="textbox"][aria-label*="Viết bình luận"]'
            ).first

            if cmt_box.is_visible():
                cmt_box.click(); _pause(0.8, 1.5)
                pg.keyboard.type(comment, delay=random.randint(35, 85))
                _pause(1, 2)
                pg.keyboard.press("Enter")
                _pause(3, 5)
                print("[COMMENT] Đã đăng comment link thành công!")
                return True
            else:
                print("[COMMENT] Không tìm thấy ô nhập comment trực tiếp.")
                return False
        except Exception as e:
            print("[COMMENT ERROR]", e)
            return False

    def retry_comment_on_post(self, group_url, caption_snippet, comment):
        """Mở lại group tìm bài đã được duyệt và bình luận bổ sung."""
        pg = self.page
        pg.goto(group_url, wait_until="domcontentloaded"); _pause(4, 7)
        if any(k in pg.url for k in ("checkpoint", "login")):
            raise RuntimeError("CHECKPOINT")
        
        _scroll(pg)
        clean_snippet = caption_snippet.split("\n")[0][:25].strip()
        loc = pg.locator(f"text={clean_snippet}").first
        
        try:
            if loc.is_visible():
                loc.scroll_into_view_if_needed(); _pause(1, 2)
                return self._comment_latest(comment)
        except Exception as e:
            print("[RETRY COMMENT ERROR]", e)
        return False

    def warmup(self):
        """Nuôi nick nhẹ: lướt newsfeed, đọc bài, thả tim ngẫu nhiên."""
        pg = self.page
        pg.goto("https://www.facebook.com/", wait_until="domcontentloaded"); _pause(3, 6)
        if any(k in pg.url for k in ("checkpoint", "login")):
            raise RuntimeError("CHECKPOINT")

        print(f"[WARMUP] Bắt đầu lướt feed cho nick {self.acc['name']}...")
        for _ in range(random.randint(4, 8)):
            pg.mouse.wheel(0, random.randint(300, 700))
            _pause(3, 7)

        # Thử thả 1 like nhẹ nhàng vào bài viết bất kỳ trên newfeed
        try:
            like_buttons = pg.locator('div[role="button"][aria-label="Thích"], div[role="button"][aria-label="Like"]').all()
            if like_buttons:
                target_btn = random.choice(like_buttons[:4])
                if target_btn.is_visible():
                    target_btn.scroll_into_view_if_needed(); _pause(1, 2)
                    target_btn.click()
                    print(f"[WARMUP] Đã thả tim 1 bài viết tự nhiên cho nick {self.acc['name']}.")
                    _pause(2, 4)
        except Exception as e:
            print("[WARMUP LIKE NOTICE]", e)

    def close(self):
        try: self.browser.close()
        except Exception: pass

def _load_cookies(path):
    raw = json.load(open(path, encoding="utf-8"))
    out = []
    for c in raw:
        ck = {"name": c["name"], "value": c["value"], "domain": c.get("domain", ".facebook.com"),
              "path": c.get("path", "/"), "secure": True}
        ss = {"no_restriction": "None", "lax": "Lax", "strict": "Strict"}.get(str(c.get("sameSite", "")).lower())
        if ss: ck["sameSite"] = ss
        out.append(ck)
    return out

def _pause(a, b): time.sleep(random.uniform(a, b))
def _scroll(pg):
    for _ in range(random.randint(1, 3)):
        pg.mouse.wheel(0, random.randint(300, 900)); _pause(0.8, 2)

def run_due(cfg):
    """
    Gọi mỗi ~5 phút:
    1. Đăng các bài đến giờ
    2. Cập nhật điểm uy tín group (tự học)
    3. Xử lý retry comment cho các bài đã được duyệt
    """
    now = time.time(); p = cfg["posting"]
    due = db.q("SELECT * FROM posts WHERE status='queued' AND scheduled_at<=? ORDER BY scheduled_at LIMIT 3", (now,))
    
    # Kiểm tra xem có comment nào đang cần retry duyệt không
    pending_cmts = db.q("""SELECT * FROM posts 
                           WHERE comment_status='pending_approval' AND comment_retry_at<=? AND comment_retries<3 
                           LIMIT 2""", (now,))
    
    if not due and not pending_cmts:
        return

    accs = {a["name"]: a for a in cfg["accounts"]}
    with sync_playwright() as pw:
        sessions = {}

        # 1. Xử lý đăng bài đến giờ
        for post in due:
            name = post["account"]
            a = db.q("SELECT * FROM accounts WHERE name=?", (name,), one=True)
            if a and a["paused_until"] > now:
                continue

            done_today = db.q("SELECT COUNT(*) c FROM posts WHERE account=? AND status='done' AND posted_at>?",
                              (name, db.today_start()), one=True)["c"]
            if done_today >= p["max_posts_per_account_per_day"]:
                continue

            # Kiểm tra deal còn hợp lệ / còn hàng hay không
            if post["kind"] == "deal":
                deal = db.q("SELECT * FROM deals WHERE id=?", (post["deal_id"],), one=True)
                if not dealmod.still_valid(deal):
                    db.x("UPDATE posts SET status='skipped', error='deal expired' WHERE id=?", (post["id"],))
                    print(f"[SKIP] Bỏ qua bài {post['id']} do deal đã hết hạn/hết hàng.")
                    continue

            try:
                if name not in sessions:
                    sessions[name] = AccountSession(pw, accs[name])
                    if not sessions[name].healthy():
                        raise RuntimeError("CHECKPOINT")

                res = sessions[name].post(
                    post["group_url"], post["caption"], post["comment"], 
                    cfg["dry_run"], post["image_path"]
                )

                if not cfg["dry_run"]:
                    c_status = res.get("comment_status", "none")
                    # Nếu bài chờ admin duyệt, đặt lịch hẹn kiểm tra comment sau 45 phút
                    c_retry_at = (now + 45 * 60) if c_status == "pending_approval" else 0
                    
                    db.x("""UPDATE posts SET status='done', posted_at=?, comment_status=?, comment_retry_at=? 
                            WHERE id=?""", (now, c_status, c_retry_at, post["id"]))

                    # TỰ HỌC: Cộng điểm uy tín cho group và reset chuỗi lỗi
                    db.x("""UPDATE groups SET 
                            last_posted_at=?, 
                            success_count=success_count+1, 
                            consecutive_fails=0, 
                            priority_score=MIN(200.0, priority_score + 5.0) 
                            WHERE url=?""", (now, post["group_url"]))

                _pause(20, 50)

            except Exception as e:
                msg = str(e)
                db.x("UPDATE posts SET status='failed', error=? WHERE id=?", (msg[:300], post["id"]))

                # TỰ HỌC: Trừ điểm và theo dõi lỗi liên tiếp
                g_row = db.q("SELECT consecutive_fails, priority_score FROM groups WHERE url=?", (post["group_url"],), one=True)
                cf = ((g_row["consecutive_fails"] or 0) + 1) if g_row else 1
                curr_score = g_row["priority_score"] if g_row else 100.0
                new_score = max(10.0, curr_score - 25.0)
                new_status = "cooling_down" if cf >= 3 else "joined"

                db.x("""UPDATE groups SET 
                        fail_count=fail_count+1, 
                        consecutive_fails=?, 
                        priority_score=?, 
                        status=?, 
                        last_error=? 
                        WHERE url=?""", (cf, new_score, new_status, msg[:200], post["group_url"]))

                if cf >= 3:
                    tg(f"⚠️ Group {post['group_url']} lỗi {cf} lần liên tiếp -> Tự động chuyển 'cooling_down' (tạm dừng 7 ngày).")

                if "CHECKPOINT" in msg:
                    # Nick dính checkpoint -> dừng nick 3 ngày, báo Telegram
                    db.x("INSERT OR REPLACE INTO accounts(name,paused_until) VALUES(?,?)", (name, now + 3 * 86400))
                    tg(f"⚠️ Nick {name} dính checkpoint/đăng xuất. Đã tạm dừng 3 ngày.")

        # 2. Xử lý retry comment cho các bài đã được admin duyệt
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

def warmup_accounts(cfg):
    """Thực hiện phiên nuôi nick nhẹ nhàng trong tuần đầu hoặc định kỳ hàng ngày."""
    now = time.time()
    accs = cfg["accounts"]
    with sync_playwright() as pw:
        for acc in accs:
            row = db.q("SELECT * FROM accounts WHERE name=?", (acc["name"],), one=True)
            if row and row["paused_until"] > now:
                continue
            # Nếu vừa tương tác trong vòng 4 tiếng thì bỏ qua
            if row and (now - (row["last_warmup_at"] or 0) < 14400):
                continue

            try:
                sess = AccountSession(pw, acc)
                if sess.healthy():
                    sess.warmup()
                    db.x("INSERT OR REPLACE INTO accounts(name,last_warmup_at) VALUES(?,?)", (acc["name"], now))
                sess.close()
            except Exception as e:
                print(f"[WARMUP ERROR] Nick {acc['name']}:", e)


def post_single(cfg, post):
    """Thực hiện đăng ngay lập tức 1 bài viết theo yêu cầu."""
    now = time.time()
    name = post["account"]
    accs = {a["name"]: a for a in cfg["accounts"]}
    if name not in accs:
        return {"success": False, "message": f"Tài khoản '{name}' không có trong cấu hình accounts."}

    with sync_playwright() as pw:
        sess = None
        try:
            sess = AccountSession(pw, accs[name])
            if not sess.healthy():
                db.x("INSERT OR REPLACE INTO accounts(name,paused_until) VALUES(?,?)", (name, now + 3 * 86400))
                return {"success": False, "message": f"Tài khoản {name} dính checkpoint hoặc hết hạn cookie. Đã tạm dừng 3 ngày."}

            res = sess.post(
                post["group_url"], post["caption"], post["comment"],
                cfg.get("dry_run", False), post["image_path"]
            )

            status = res.get("status", "done")
            c_status = res.get("comment_status", "none")
            c_retry_at = (now + 45 * 60) if c_status == "pending_approval" else 0

            db.x("""UPDATE posts SET status=?, posted_at=?, comment_status=?, comment_retry_at=?
                    WHERE id=?""", (status, now, c_status, c_retry_at, post["id"]))

            if status == "done":
                db.x("""UPDATE groups SET last_posted_at=?, success_count=success_count+1, consecutive_fails=0,
                        priority_score=MIN(200.0, priority_score + 5.0) WHERE url=?""", (now, post["group_url"]))

            return {
                "success": True,
                "status": status,
                "comment_status": c_status,
                "message": f"Đã đăng bài #{post['id']} thành công ({status})!"
            }
        except Exception as e:
            err = str(e)
            db.x("UPDATE posts SET status='failed', error=? WHERE id=?", (err[:300], post["id"]))
            return {"success": False, "message": f"Lỗi khi đăng bài: {err}"}
        finally:
            if sess:
                sess.close()
