"""Module 3a: lập lịch hàng ngày -> chọn deal, ghép group + nick, sinh caption, gắn Sub-ID, đặt giờ ngẫu nhiên."""
import time, random, db
from . import captions, coupons, affiliate, telegram_channel

def plan_day(cfg):
    p = cfg["posting"]; names = [a["name"] for a in cfg["accounts"]]
    h0, h1 = p["active_hours"]
    seven_days_ago = time.time() - 7 * 86400
    deals = db.q("""SELECT * FROM deals 
                    WHERE (status='new' OR (status='posted' AND last_posted_at < ?))
                    AND is_valid=1 
                    ORDER BY score DESC, created_at DESC LIMIT ?""", 
                 (seven_days_ago, cfg["deals"]["top_per_day"]))
    cooldown = time.time() - p["group_cooldown_hours"] * 3600
    cursor = {n: max(time.time(), _today(h0)) for n in names}   # con trỏ thời gian riêng cho từng nick
    used_today = {n: 0 for n in names}
    planned = 0

    funnel_cta = telegram_channel.get_funnel_cta(cfg)
    funnel_in_cap = (cfg.get("funnel") or {}).get("include_in_caption", False)
    funnel_in_cmt = (cfg.get("funnel") or {}).get("include_in_comment", True)

    for d in deals:
        niche_term = (d.get("niche") or "").strip().lower()
        # Lọc group: Ưu tiên group cùng ngành hàng, hoặc group săn sale nếu deal điểm cao (>55)
        groups = db.q("""SELECT * FROM groups 
                         WHERE status IN ('joined','approved') 
                         AND (LOWER(niche)=? OR LOWER(niche) LIKE ? OR (kind='dealhunt' AND ?>=55.0))
                         AND last_posted_at<? AND fail_count<5 AND consecutive_fails<3 
                         ORDER BY priority_score DESC, RANDOM()""", 
                      (niche_term, f"%{niche_term}%", d.get("score", 0), cooldown))
        for g in groups:
            acc = g["account"]
            if not acc or used_today[acc] >= p["max_posts_per_account_per_day"]:
                continue

            # QUẢN TRỊ TRÙNG LẶP: Không đăng lại cùng 1 sản phẩm vào cùng 1 nhóm nếu chưa qua 7 ngày
            already_posted = db.q("""SELECT 1 FROM posts 
                                     WHERE deal_id=? AND group_url=? 
                                     AND status IN ('done','queued','pending_approval') 
                                     AND scheduled_at > ?""", 
                                  (d["id"], g["url"], seven_days_ago), one=True)
            if already_posted:
                continue

            caps = captions.variants(d, link_in_comment=p["link_in_comment"])
            cap = random.choice(caps)
            gap = random.randint(*p["min_gap_minutes"]) * 60
            cursor[acc] += gap + random.randint(0, 300)
            if cursor[acc] > _today(h1): continue

            # Gắn Sub-ID theo dõi chuyển đổi riêng cho nick + group + deal
            aff_url, sub_id = affiliate.build_subid_link(
                d["aff_url"], account=acc, group_url=g["url"], item_id=d["id"], angle="deal"
            )

            comment = f"Link mình để đây nha: {aff_url}" if p["link_in_comment"] else None
            if not p["link_in_comment"] or not g["allow_link"]:
                cap = cap + f"\n{aff_url}" if g["allow_link"] else cap

            # Gắn phễu Telegram CTA
            if funnel_cta:
                if funnel_in_cmt and comment:
                    comment += f"\n{funnel_cta}"
                if funnel_in_cap:
                    cap += f"\n{funnel_cta}"

            db.x("""INSERT INTO posts(deal_id,group_url,account,caption,comment,image_path,kind,scheduled_at,sub_id)
                    VALUES(?,?,?,?,?,?,'deal',?,?)""", 
                 (d["id"], g["url"], acc, cap, comment, d["image_path"], cursor[acc], sub_id))
            used_today[acc] += 1; planned += 1
            break   # 1 deal -> 1 group/ngày để không rải trùng
        db.x("UPDATE deals SET status='planned' WHERE id=?", (d["id"],))
    return planned

def _today(hour):
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, 0, 0, 0, 0, -1))


def plan_digests(cfg):
    """Mỗi ngày 1 bản tin mã giảm giá/sự kiện cho mỗi group săn deal, vào các khung giờ vàng."""
    p = cfg["posting"]; windows = cfg.get("digest_windows", [[11, 30, 12, 0], [19, 30, 20, 0]])
    dg = coupons.build_digest("shopee")
    if not dg: return 0
    img, caps, raw_comment = dg
    cutoff = time.time() - 20 * 3600
    groups = db.q("""SELECT * FROM groups 
                     WHERE status IN ('joined','approved') AND kind='dealhunt'
                     AND last_posted_at<? AND fail_count<5 AND consecutive_fails<3
                     ORDER BY priority_score DESC, RANDOM()""", (cutoff,))
    n = 0; used = {}

    funnel_cta = telegram_channel.get_funnel_cta(cfg)
    funnel_in_cmt = (cfg.get("funnel") or {}).get("include_in_comment", True)

    for g in groups:
        acc = g["account"]
        if not acc or used.get(acc, 0) >= 2: continue      # tối đa 2 bản tin/nick/ngày, vẫn nằm trong trần chung
        w = random.choice(windows)
        t = _today(w[0]) + random.randint(0, (w[2]-w[0])*3600 + (w[3]-w[1])*60)
        if t < time.time(): t = time.time() + random.randint(600, 1800)
        
        # Sub-id cho bản tin
        _, sub_id = affiliate.build_subid_link(
            "https://shopee.vn", account=acc, group_url=g["url"], item_id="digest", angle="digest"
        )

        c = raw_comment if g["allow_link"] else None
        if c and funnel_cta and funnel_in_cmt:
            c += f"\n{funnel_cta}"

        cap = random.choice(caps)
        db.x("""INSERT INTO posts(deal_id,group_url,account,caption,comment,image_path,kind,scheduled_at,sub_id)
                VALUES('digest',?,?,?,?,?,'digest',?,?)""", (g["url"], acc, cap, c, img, t, sub_id))
        used[acc] = used.get(acc, 0) + 1; n += 1
    return n

