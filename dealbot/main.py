"""dealbot - Vòng khép kín hàng ngày hoàn chỉnh.
Lịch chạy tự động:
- Thứ 2, 05:00: Sinh từ khóa AI, gom group qua Google CSE, xuất groups_review.csv
- 30 phút/lần: Nhập lại file bạn đã duyệt, gán group cho nick, kiểm tra phục hồi cooling_down
- 3 tiếng/lần: Cào deal, lọc ngưỡng, chấm điểm
- 06:00, 10:00, 16:00: Gom mã giảm giá & sự kiện
- 07:30: Lên lịch trong ngày: ghép deal + group + nick + gắn Sub-ID + phễu Telegram
- 5 phút/lần: Đăng bài đến giờ, kiểm tra deal còn hợp lệ, tự động retry comment duyệt bài
- 10:00 & 15:00: Nuôi nick tự động nhẹ (lướt feed, thả tim)
- 11:15 & 19:15: Đăng bản tin mã giảm giá lên Kênh Telegram chính thức
- 22:30: Báo cáo tổng kết ngày qua Telegram
"""
import sys, yaml, time, db

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from modules import groups, deals, planner, poster, coupons, images, telegram_channel, lazada_hunter
from notify import tg


load_dotenv()
db.init()
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
names = [a["name"] for a in cfg["accounts"]]

def job_discover():
    """Thứ 2, 5h: Sinh từ khóa bằng AI, gom group ứng viên, xuất file duyệt."""
    n = groups.discover(cfg["niches"], cfg.get("dealhunt_niches", []))
    groups.assign_accounts(names)
    tg(f"🔎 <b>[Groups]</b> Đã tìm được {n} group ứng viên mới.\n"
       f"Mở <code>groups_review.csv</code> để duyệt (đặt status=joined cho group đã vào).", parse_mode="HTML")

def job_import_review():
    """Mỗi 30 phút: Nhập file bạn đã duyệt, gán cố định nick, phục hồi nhóm cooling_down."""
    try:
        groups.import_reviewed()
        groups.assign_accounts(names)
        groups.reset_cooling_down_groups(cfg.get("learning", {}).get("cooldown_days_on_penalty", 7))
    except FileNotFoundError:
        pass

def job_deals():
    """Mỗi 3 tiếng: Cào deal, lọc ngưỡng, chấm điểm, tải ảnh & vẽ badge."""
    res = deals.refresh(cfg)
    added = res[0] if isinstance(res, tuple) else res
    if added > 0:
        tg(f"🛒 <b>[Deals]</b> Cào mới: +{added} deal đạt ngưỡng chất lượng.", parse_mode="HTML")

def job_coupons():
    """6h, 10h, 16h: Gom mã giảm giá từ API Accesstrade & events.yaml."""
    added = coupons.refresh()
    if added > 0:
        tg(f"🎟 <b>[Coupons]</b> Cập nhật: +{added} mã/sự kiện mới.", parse_mode="HTML")

def job_plan():
    """07h30: Lên lịch các bài đăng trong ngày, gắn Sub-ID và CTA phễu Telegram."""
    a = planner.plan_day(cfg)
    b = planner.plan_digests(cfg)
    tg(f"🗓 <b>[Planner]</b> Đã lên lịch thành công cho hôm nay:\n"
       f"• {a} bài deal ngách theo sản phẩm\n"
       f"• {b} bản tin mã giảm giá săn sale", parse_mode="HTML")
    images.cleanup()

def job_post():
    """Mỗi 5 phút: Đăng các bài đến giờ, kiểm tra deal còn hợp lệ, retry comment."""
    poster.run_due(cfg)

def job_warmup():
    """10h & 15h: Nuôi nick tự động nhẹ để giữ cookie tươi và tạo lịch sử tự nhiên."""
    poster.warmup_accounts(cfg)

def job_telegram_channel():
    """11h15 & 19h15: Đăng bản tin tổng hợp mã giảm giá lên Kênh Telegram riêng."""
    t_cfg = cfg.get("telegram_channel", {})
    if not t_cfg.get("enabled", False):
        return

    dg = coupons.build_digest("shopee")
    if dg:
        img_path, _, cmt = dg
        today_str = time.strftime("%d/%m")
        cs = coupons.active(limit=8)
        lines = [((c["code"] or "Ưu đãi"), c["title"] or c["detail"]) for c in cs]
        links = "\n".join(f"• {c['title'][:35]}: {c['aff_url']}" for c in cs if c["aff_url"])
        ok = telegram_channel.post_digest_to_channel(
            cfg, f"Bản Tin Mã Giảm Giá Shopee {today_str}", lines, img_path=img_path, links_text=links
        )
        if ok:
            tg(f"📢 <b>[Telegram Channel]</b> Đã đăng bản tin mã giảm giá {today_str} lên kênh chính thức.", parse_mode="HTML")

def job_lazada_hunter():
    """Mỗi 5 phút: Quét toàn bộ sản phẩm trên Lazada, so sánh giá FB và gửi alert Telegram nếu có deal hời."""
    res = lazada_hunter.run_lazada_hunter_cycle(batch_size=None)
    if res.get("deals_found", 0) > 0:
        print(f"[lazada_hunter] Đã phát hiện {res['deals_found']} kèo hời Lazada và gửi Telegram.")

def job_report():
    """22h30: Báo cáo tổng kết ngày qua Telegram."""
    start = db.today_start()
    posts = db.q("SELECT status, comment_status, COUNT(*) c FROM posts WHERE scheduled_at>? GROUP BY status, comment_status", (start,))
    
    summary = {}
    cmt_done = 0
    for r in posts:
        st = r["status"]
        summary[st] = summary.get(st, 0) + r["c"]
        if r["comment_status"] == "done":
            cmt_done += r["c"]

    # Thống kê trạng thái nick
    acc_status = []
    now = time.time()
    for acc in cfg["accounts"]:
        row = db.q("SELECT paused_until FROM accounts WHERE name=?", (acc["name"],), one=True)
        if row and row["paused_until"] > now:
            left_hours = int((row["paused_until"] - now) / 3600)
            acc_status.append(f"❌ {acc['name']}: Tạm dừng (còn {left_hours}h)")
        else:
            acc_status.append(f"✅ {acc['name']}: Bình thường")

    # Thống kê nhóm tốt & nhóm cooling_down
    groups_cooling = db.q("SELECT COUNT(*) c FROM groups WHERE status='cooling_down'", one=True)["c"]
    groups_active = db.q("SELECT COUNT(*) c FROM groups WHERE status IN ('joined','approved')", one=True)["c"]

    msg = (
        f"📊 <b>BÁO CÁO HOẠT ĐỘNG NGÀY {time.strftime('%d/%m/%Y')}</b>\n\n"
        f"<b>Bài đăng:</b>\n"
        f"• Đã đăng thành công: <b>{summary.get('done', 0)}</b> bài\n"
        f"• Chờ duyệt / Retry: <b>{summary.get('pending_approval', 0)}</b> bài\n"
        f"• Comment link aff thành công: <b>{cmt_done}</b>\n"
        f"• Bỏ qua (deal hết hạn): <b>{summary.get('skipped', 0)}</b> bài\n"
        f"• Thất bại: <b>{summary.get('failed', 0)}</b> bài\n\n"
        f"<b>Tài khoản:</b>\n" + "\n".join(acc_status) + "\n\n"
        f"<b>Hội nhóm:</b> {groups_active} đang chạy | {groups_cooling} cooling_down"
    )
    tg(msg, parse_mode="HTML")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "discover":
        job_discover()
    elif cmd in ("import", "import_groups"):
        job_import_review()
    elif cmd == "deals":
        job_deals()
    elif cmd == "coupons":
        job_coupons()
    elif cmd == "plan":
        job_plan()
    elif cmd == "post":
        job_post()
    elif cmd == "warmup":
        job_warmup()
    elif cmd in ("channel", "telegram_channel"):
        job_telegram_channel()
    elif cmd in ("lazada", "lazada_hunter"):
        job_lazada_hunter()
    elif cmd == "report":
        job_report()
    else:
        s = BlockingScheduler(timezone="Asia/Ho_Chi_Minh")
        # 1. Thứ 2, 05h00: Khám phá nhóm mới
        s.add_job(job_discover, "cron", day_of_week="mon", hour=5)
        # 2. Mỗi 30 phút: Nhập file duyệt & hồi phục cooling_down
        s.add_job(job_import_review, "interval", minutes=30)
        # 3. Mỗi 3 tiếng: Cào deal
        s.add_job(job_deals, "interval", hours=3)
        # 4. Gom voucher: 6h, 10h, 16h
        s.add_job(job_coupons, "cron", hour="6,10,16")
        # 5. 07h30: Lập lịch trong ngày
        s.add_job(job_plan, "cron", hour=7, minute=30)
        # 6. Mỗi 5 phút: Đăng bài đến giờ & retry comment
        s.add_job(job_post, "interval", minutes=5)
        # 7. Nuôi nick: 10h00 & 15h00
        s.add_job(job_warmup, "cron", hour="10,15", minute=0)
        # 8. Đăng Telegram Channel: 11h15 & 19h15
        s.add_job(job_telegram_channel, "cron", hour="11,19", minute=15)
        # 9. Mỗi 5 phút: Săn deal Lazada so sánh giá FB (LazMall / Tmall)
        s.add_job(job_lazada_hunter, "interval", minutes=5)
        # 10. 22h30: Báo cáo qua Telegram
        s.add_job(job_report, "cron", hour=22, minute=30)

        tg("🚀 <b>dealbot</b> đã khởi động với đầy đủ vòng chạy hàng ngày kèm Lazada Hunter 5p!", parse_mode="HTML")
        print("dealbot scheduler started. Press Ctrl+C to exit.")
        s.start()
