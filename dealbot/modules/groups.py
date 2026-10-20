"""Module 1: sinh từ khóa theo ngành + gom group ứng viên + Quản lý Danh Sách Đen (Blacklist / Auto-Leave)."""
import os, sys, re, json, csv, time, random, logging, subprocess, datetime, requests, anthropic, db

logger = logging.getLogger("groups")

def get_account_cookie_path(account_name: str) -> str:
    """Xác định đường dẫn tuyệt đối đến file cookie của tài khoản."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_file = os.path.join(base_dir, "config.yaml")
    if os.path.exists(cfg_file):
        try:
            import yaml
            with open(cfg_file, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            for a in cfg.get("accounts", []):
                if a.get("name") == account_name and a.get("cookie_file"):
                    cp = a["cookie_file"]
                    return cp if os.path.isabs(cp) else os.path.join(base_dir, cp)
        except Exception:
            pass
    return os.path.join(base_dir, "cookies", f"{account_name}.json")


def get_any_valid_account_cookie() -> tuple:
    """Trả về (account_name, cookie_path) của nick hợp lệ đầu tiên có file cookie tồn tại."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_file = os.path.join(base_dir, "config.yaml")
    if os.path.exists(cfg_file):
        try:
            import yaml
            with open(cfg_file, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            for a in cfg.get("accounts", []):
                acc_name = a.get("name")
                cp = a.get("cookie_file") or f"cookies/{acc_name}.json"
                full_cp = cp if os.path.isabs(cp) else os.path.join(base_dir, cp)
                if os.path.exists(full_cp):
                    return acc_name, full_cp
        except Exception:
            pass
    p = os.path.join(base_dir, "cookies", "nick_a.json")
    if os.path.exists(p):
        return "nick_a", p
    return "", ""


def gen_keywords(niche, n=15):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            cli = anthropic.Anthropic(api_key=api_key)
            msg = cli.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=800,
                messages=[{"role": "user", "content":
                    f"Liệt kê {n} cụm từ khóa tiếng Việt mà admin hay đặt tên group Facebook về ngách '{niche}' "
                    "(review, hội mua sắm, săn sale, kinh nghiệm...). Chỉ trả JSON array các chuỗi."}])
            return json.loads(re.search(r"\[.*\]", msg.content[0].text, re.S).group(0))
        except Exception as e:
            print("[groups] Claude API keyword generation notice:", type(e).__name__)

    # Từ khóa mồi mặc định
    return [
        f"hội {niche}", f"review {niche}", f"săn sale {niche}", f"kinh nghiệm {niche}",
        f"thanh lý {niche}", f"mua bán {niche} giá rẻ", f"nghiện {niche}"
    ][:n]


def search_groups(keyword, pages=2):
    """Dùng Google Custom Search API (hợp lệ, ổn định hơn cào Google)."""
    key, cx = os.getenv("GOOGLE_CSE_KEY"), os.getenv("GOOGLE_CSE_CX")
    if not (key and cx):
        print("Thiếu GOOGLE_CSE_KEY/CX"); return []
    out = []
    for p in range(pages):
        r = requests.get("https://www.googleapis.com/customsearch/v1", params={
            "key": key, "cx": cx, "q": f"site:facebook.com/groups {keyword}", "start": 1 + p * 10}, timeout=20)
        for it in r.json().get("items", []):
            m = re.search(r"facebook\.com/groups/([\w.\-]+)", it["link"])
            if m:
                out.append((f"https://www.facebook.com/groups/{m.group(1)}", it["title"].split("|")[0].strip()))
    return out


def discover(niches, dealhunt_niches=()):
    found = 0
    for niche in list(niches) + list(dealhunt_niches):
        kind = 'dealhunt' if niche in dealhunt_niches else 'niche'
        for kw in gen_keywords(niche):
            for url, name in search_groups(kw):
                # BẢO VỆ DS ĐEN: Nếu đã tồn tại trong DB (kể cả candidate, joined hay banned) thì tuyệt đối không thêm lại
                if not db.q("SELECT 1 FROM groups WHERE url=?", (url,), one=True):
                    db.x("INSERT INTO groups(url,name,niche,kind) VALUES(?,?,?,?)", (url, name, niche, kind))
                    found += 1
    export_csv()
    return found


def export_csv(path="groups_review.csv"):
    """Xuất để bạn duyệt tay: điền status=joined/skip, allow_link=0/1 rồi import lại."""
    rows = db.q("SELECT * FROM groups WHERE status IN ('candidate', 'cooling_down') ORDER BY priority_score DESC")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "name", "niche", "kind", "status", "allow_link", "priority_score", "fail_count"])
        for r in rows:
            w.writerow([r["url"], r["name"], r["niche"], r["kind"], r["status"], r["allow_link"], r["priority_score"], r["fail_count"]])


def import_reviewed(path="groups_review.csv"):
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            st = r.get("status", "candidate")
            existing = db.q("SELECT status FROM groups WHERE url=?", (r["url"],), one=True)
            # Không cho phép import ghi đè làm sống lại nhóm đã bị banned
            if existing and existing["status"] == "banned":
                continue

            if st in ("joined", "approved"):
                db.x("""UPDATE groups SET status=?, allow_link=?, consecutive_fails=0 
                        WHERE url=?""", (st, int(r.get("allow_link") or 1), r["url"]))
            else:
                db.x("UPDATE groups SET status=?, allow_link=? WHERE url=?", 
                     (st, int(r.get("allow_link") or 1), r["url"]))


def reset_cooling_down_groups(cooldown_days=7):
    """Tự động cho group cooling_down thêm cơ hội sau 7 ngày thử thách."""
    threshold = time.time() - cooldown_days * 86400
    db.x("""UPDATE groups SET status='joined', consecutive_fails=0, priority_score=75.0 
            WHERE status='cooling_down' AND last_posted_at<?""", (threshold,))


def assign_accounts(account_names):
    """Mỗi group gắn cố định 1 nick (sticky) để không có 2 nick cùng xuất hiện trong 1 group."""
    gs = db.q("SELECT url FROM groups WHERE status IN ('joined','approved') AND (account IS NULL OR account='')")
    for i, g in enumerate(gs):
        db.x("UPDATE groups SET account=? WHERE url=?", (account_names[i % len(account_names)], g["url"]))


# =========================================================================
# --- HỆ THỐNG DANH SÁCH ĐEN & TỰ ĐỘNG OUT NHÓM (BLACKLIST / AUTO-LEAVE) ---
# =========================================================================

def find_bad_groups(max_consecutive_fails: int = 3, max_pending_count: int = 2) -> list:
    """
    Rà soát toàn bộ nhóm Facebook trong hệ thống (ngoại trừ nhóm đã bị 'banned')
    để phát hiện các nhóm vi phạm:
    1. Lỗi nghiêm trọng do nhóm cấm / hạn chế đăng bài / đóng cửa
    2. Lỗi liên tiếp >= max_consecutive_fails
    3. Nhóm bị 'Pending Approval Hell': Các bài đăng gần nhất bị đưa vào hàng chờ duyệt liên tiếp
    4. Điểm uy tín quá thấp (priority_score <= 25.0 kèm fail_count >= 3)
    """
    rows = db.q("""
        SELECT * FROM groups 
        WHERE status IN ('joined', 'approved', 'cooling_down', 'candidate')
        ORDER BY priority_score ASC, consecutive_fails DESC
    """)

    bad_groups = []
    hard_block_keywords = [
        "chỉ quản trị viên", "nhóm_chỉ_cho_admin_đăng", "only admins can post",
        "hạn chế đăng bài", "không thể đăng bài", "quyền đăng bài của bạn đã bị tạm dừng",
        "nhóm_không_khả_dụng", "không tồn tại", "đã đóng cửa",
        "nội dung này hiện không khả dụng", "this content isn't available",
        "chưa_tham_gia_nhóm"
    ]

    for r in rows:
        g = dict(r)
        url = g["url"]
        last_err = (g.get("last_error") or "").lower()
        consec_fails = g.get("consecutive_fails") or 0
        score = g.get("priority_score") or 100.0
        fail_cnt = g.get("fail_count") or 0

        reasons = []

        # 1. Kiểm tra Hard Block
        matched_kw = next((kw for kw in hard_block_keywords if kw in last_err), None)
        if matched_kw:
            reasons.append(f"Nhóm cấm đăng / hạn chế quyền hoặc không tồn tại ({matched_kw})")

        # 2. Kiểm tra chuỗi lỗi liên tiếp
        if consec_fails >= max_consecutive_fails:
            reasons.append(f"Đăng bài thất bại {consec_fails} lần liên tiếp (ngưỡng tối đa {max_consecutive_fails})")

        # 3. Kiểm tra Pending Approval Hell (Bắt duyệt bài liên tục)
        recent_posts = db.q("""
            SELECT status, posted_at, scheduled_at 
            FROM posts 
            WHERE group_url=? AND status IN ('done', 'pending_approval', 'failed')
            ORDER BY scheduled_at DESC, id DESC LIMIT 4
        """, (url,))

        if recent_posts:
            pending_streak = 0
            has_done_recent = False
            for p in recent_posts:
                if p["status"] == "pending_approval":
                    pending_streak += 1
                elif p["status"] == "done":
                    has_done_recent = True
                    break
                else:
                    break

            if pending_streak >= max_pending_count and not has_done_recent:
                reasons.append(f"Admin giữ bài chờ duyệt {pending_streak} lần liên tiếp (Pending Approval, không có bài được duyệt)")
            elif "chờ admin duyệt" in last_err and pending_streak >= 1 and consec_fails >= 2:
                reasons.append("Bài viết liên tục bị đưa vào hàng chờ Admin duyệt không công khai")

        # 4. Kiểm tra điểm uy tín quá thấp
        if score <= 25.0 and fail_cnt >= 3:
            reasons.append(f"Điểm chất lượng nhóm chạm đáy ({score:.0f}/200) kèm {fail_cnt} lần lỗi")

        if reasons:
            g["reason"] = " • ".join(reasons)
            bad_groups.append(g)

    return bad_groups


def leave_and_blacklist_group(group_url: str, reason: str = "Tự động thanh lọc nhóm vi phạm", auto_leave_fb: bool = True, account: str = None) -> dict:
    """
    Đưa một nhóm vào Danh Sách Đen (Blacklist / Banned), đồng thời tự động rời nhóm trên Facebook (Leave Group).
    Cập nhật status='banned' trong cơ sở dữ liệu để tuyệt đối không bao giờ join lại.
    """
    group_row = db.q("SELECT * FROM groups WHERE url=?", (group_url,), one=True)
    g_name = group_row["name"] if group_row else "Group Facebook"
    assigned_acc = account or (group_row["account"] if group_row else None)

    fb_result = {"success": True, "message": "Chỉ cập nhật DB (không rời FB)"}

    if auto_leave_fb:
        cookie_path = ""
        acc_used = assigned_acc
        if acc_used:
            cookie_path = get_account_cookie_path(acc_used)
        if not cookie_path or not os.path.exists(cookie_path):
            acc_used, cookie_path = get_any_valid_account_cookie()

        if cookie_path and os.path.exists(cookie_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            scanner_script = os.path.join(base_dir, "modules", "fb_groups_scanner.py")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            try:
                proc = subprocess.run(
                    [sys.executable, scanner_script, "leave", cookie_path, "--group-url", group_url],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=env,
                    timeout=75
                )
                if proc.stdout.strip():
                    fb_result = json.loads(proc.stdout.strip())
                else:
                    fb_result = {"success": False, "message": proc.stderr.strip() or "Tiến trình rời nhóm không có phản hồi"}
            except Exception as e:
                fb_result = {"success": False, "message": f"Lỗi ngoại lệ khi rời nhóm: {str(e)}"}
        else:
            fb_result = {"success": False, "message": "Không tìm thấy file cookie hợp lệ để out nhóm"}

    # CẬP NHẬT DATABASE: CHUYỂN SANG BANNED ĐỂ VĨNH VIỄN KHÔNG JOIN LẠI
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    full_error_msg = f"🚫 ĐÃ RỜI NHÓM & VÀO DS ĐEN [{now_str}]: {reason}"

    if group_row:
        db.x("""
            UPDATE groups SET 
                status='banned', 
                priority_score=0.0, 
                consecutive_fails=MAX(consecutive_fails, 3),
                last_error=? 
            WHERE url=?
        """, (full_error_msg, group_url))
    else:
        db.x("""
            INSERT INTO groups(url, name, status, priority_score, consecutive_fails, last_error)
            VALUES(?, ?, 'banned', 0.0, 3, ?)
        """, (group_url, g_name, full_error_msg))

    return {
        "success": True,
        "url": group_url,
        "name": g_name,
        "reason": reason,
        "fb_leave": fb_result,
        "status": "banned"
    }


def batch_scan_and_clean_blacklist(auto_leave_fb: bool = True, max_groups: int = 5, cfg: dict = None) -> dict:
    """
    Quét lọc và dọn dẹp các nhóm vi phạm:
    1. Rà soát danh sách nhóm vi phạm
    2. Tự động rời nhóm trên Facebook (giới hạn an toàn max_groups mỗi đợt)
    3. Đưa vào trạng thái 'banned' vĩnh viễn không join lại
    """
    if cfg is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_file = os.path.join(base_dir, "config.yaml")
        if os.path.exists(cfg_file):
            try:
                import yaml
                with open(cfg_file, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                cfg = {}
        else:
            cfg = {}

    bl_cfg = cfg.get("group_blacklist", {})
    max_consec = bl_cfg.get("consecutive_fails_threshold", 3)
    max_pending = bl_cfg.get("pending_approval_threshold", 2)
    max_groups_per_run = min(max_groups, bl_cfg.get("max_leaves_per_run", 5))

    bad_groups = find_bad_groups(max_consecutive_fails=max_consec, max_pending_count=max_pending)

    cleaned_details = []
    target_candidates = bad_groups[:max_groups_per_run]

    for idx, bg in enumerate(target_candidates):
        url = bg["url"]
        reason = bg.get("reason", "Vi phạm tiêu chí hoạt động nhóm")
        acc = bg.get("account")

        res = leave_and_blacklist_group(
            group_url=url,
            reason=reason,
            auto_leave_fb=auto_leave_fb,
            account=acc
        )
        cleaned_details.append(res)

        if idx < len(target_candidates) - 1 and auto_leave_fb:
            time.sleep(random.uniform(5.0, 10.0))

    return {
        "success": True,
        "total_bad_found": len(bad_groups),
        "cleaned_count": len(cleaned_details),
        "max_limit": max_groups_per_run,
        "remaining_bad": max(0, len(bad_groups) - len(cleaned_details)),
        "details": cleaned_details
    }


def unban_group(group_url: str, new_status: str = "candidate") -> dict:
    """Mở khóa một nhóm khỏi danh sách đen, đưa về candidate để xem xét lại."""
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.x("""
        UPDATE groups SET 
            status=?, 
            consecutive_fails=0, 
            priority_score=75.0, 
            last_error=? 
        WHERE url=?
    """, (new_status, f"Đã mở khóa khỏi DS đen [{now_str}]", group_url))
    return {"success": True, "message": f"Đã mở khóa nhóm {group_url} thành công."}


def is_blacklisted(group_url: str) -> bool:
    """Kiểm tra xem nhóm có nằm trong danh sách đen (banned) hay không."""
    row = db.q("SELECT status FROM groups WHERE url=?", (group_url,), one=True)
    return bool(row and row.get("status") == "banned")


