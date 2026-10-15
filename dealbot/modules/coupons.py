"""Module 4: Tổng hợp mã giảm giá + sự kiện hằng ngày -> bản tin đăng vào group săn deal.
Tự động đồng bộ các Voucher Shopee VIP, link lưu mã toàn sàn, mã Live/Video, Freeship
và gắn trực tiếp link Shopee Affiliate của người dùng.
"""
import os, time, hashlib, datetime, requests, yaml, json, re
import db
from . import images, shopee_aff_converter

def get_daily_shopee_vouchers():
    """
    Sinh và tổng hợp danh sách Mã Giảm Giá & Link Lưu Voucher Shopee trong ngày.
    Tất cả link lưu mã đều được tự động chuyển đổi sang Link Affiliate của người dùng.
    """
    now = time.time()
    today_str = datetime.date.today().strftime("%d/%m")
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    # Hiệu lực trong 2 ngày tới
    today_end = datetime.datetime.now().replace(hour=23, minute=59, second=59).timestamp() + 86400 * 2

    vouchers_template = [
        # --- 1. MÃ TOÀN SÀN & SIÊU VOUCHER ---
        {
            "code": "GIAM50K",
            "title": f"Voucher Giảm 50K Toàn Sàn ({today_str})",
            "detail": "Giảm 50K cho đơn hàng từ 250K toàn sàn Shopee. Lưu sớm trên banner.",
            "category": "toan_san",
            "save_url": "https://shopee.vn/m/ma-giam-gia"
        },
        {
            "code": "HOANXU15",
            "title": f"Mã Hoàn Xu 15% Tối Đa 50K Xu ({today_str})",
            "detail": "Hoàn 15% xu tối đa 50.000 Shopee Xu cho mọi đơn hàng từ 150K.",
            "category": "toan_san",
            "save_url": "https://shopee.vn/m/ma-giam-gia"
        },
        {
            "code": "VOUCHERXTRA100",
            "title": "Voucher Xtra Giảm Đến 100K Toàn Sàn",
            "detail": "Giảm 10% - 12% tối đa 100K - 500K cho toàn bộ sản phẩm gắn nhãn Voucher Xtra.",
            "category": "toan_san",
            "save_url": "https://shopee.vn/m/ma-giam-gia"
        },
        # --- 2. MÃ FREESHIP TOÀN SÀN ---
        {
            "code": "FREESHIP0D",
            "title": "Mã Miễn Phí Vận Chuyển Đơn 0Đ Toàn Sàn",
            "detail": "Freeship 0đ - Giảm tối đa 15K phí ship cho mọi đơn từ 0đ tại các khung giờ vàng.",
            "category": "freeship",
            "save_url": "https://shopee.vn/m/mien-phi-van-chuyen"
        },
        {
            "code": "FREESHIP70K",
            "title": "Freeship Xtra Giảm 70K Phí Vận Chuyển",
            "detail": "Freeship Xtra giảm đến 70K phí ship cho đơn từ 45K, giảm 300K cho đơn từ 100K.",
            "category": "freeship",
            "save_url": "https://shopee.vn/m/mien-phi-van-chuyen"
        },
        {
            "code": "FREESHIPHOATOC",
            "title": "Freeship Hỏa Tốc Giảm 30K Nhận Trong 2H",
            "detail": "Giảm 30K phí vận chuyển hỏa tốc nội thành Hà Nội & TP.HCM.",
            "category": "freeship",
            "save_url": "https://shopee.vn/m/mien-phi-van-chuyen"
        },
        # --- 3. MÃ SHOPEE LIVE & SHOPEE VIDEO ---
        {
            "code": "LIVE20",
            "title": "Voucher Shopee Live Giảm 20% Tối Đa 50K",
            "detail": "Áp dụng cho sản phẩm được gắn tag 'Shopee Live' hoặc thêm vào giỏ hàng từ Livestream.",
            "category": "live_video",
            "save_url": "https://shopee.vn/m/shopee-live"
        },
        {
            "code": "VIDEO50",
            "title": "Voucher Shopee Video Giảm 50% Tối Đa 30K",
            "detail": "Voucher độc quyền khi xem và bấm mua trực tiếp trên Shopee Video. Cực dễ trúng!",
            "category": "live_video",
            "save_url": "https://shopee.vn/m/shopee-video"
        },
        {
            "code": "LIVE100K",
            "title": "Voucher Live Giờ Vàng 12H & 20H Giảm Đến 100K",
            "detail": "Mã giảm giá khủng tung ra vào 12h trưa và 20h tối mỗi ngày trên các phiên Livestream.",
            "category": "live_video",
            "save_url": "https://shopee.vn/m/shopee-live"
        },
        # --- 4. KHUNG GIỜ FLASH SALE ---
        {
            "code": "FLASH_SALE",
            "title": "Flash Sale Shopee 6 Khung Giờ (0h - 9h - 12h - 15h - 18h - 21h)",
            "detail": "Hàng triệu sản phẩm xả kho đồng giá từ 1K, 9K và giảm sâu 50% cập nhật mỗi khung giờ.",
            "category": "flash_sale",
            "save_url": "https://shopee.vn/flash_sale"
        },
        # --- 5. VOUCHER SHOPEEPAY ---
        {
            "code": "SHOPEEPAY20",
            "title": "Voucher Thanh Toán Ví ShopeePay Giảm 20K",
            "detail": "Áp dụng khi chọn phương thức thanh toán bằng Ví ShopeePay hoặc liên kết ngân hàng.",
            "category": "shopeepay",
            "save_url": "https://shopee.vn/m/shopeepay"
        },
        # --- 6. VOUCHER THEO NGÀNH HÀNG ---
        {
            "code": "MALL_BEAUTY",
            "title": "Voucher Mỹ Phẩm & Làm Đẹp Shopee Mall Giảm 15%",
            "detail": "Áp dụng cho các thương hiệu chính hãng L'Oreal, Innisfree, La Roche-Posay, v.v.",
            "category": "nganh_hang",
            "save_url": "https://shopee.vn/m/shopee-beauty"
        },
        {
            "code": "TECH_ZONE",
            "title": "Voucher Công Nghệ & Phụ Kiện Điện Tử Giảm Đến 500K",
            "detail": "Áp dụng cho tai nghe, sạc dự phòng, chuột phím, điện thoại từ Ugreen, Baseus, Apple.",
            "category": "nganh_hang",
            "save_url": "https://shopee.vn/m/tech-zone"
        },
        {
            "code": "LIFE_HOME",
            "title": "Voucher Nhà Cửa Đời Sống & Gia Dụng Giảm 15%",
            "detail": "Áp dụng cho Lock&Lock, Tefal, Sunhouse, đồ bếp và nước giặt gia đình.",
            "category": "nganh_hang",
            "save_url": "https://shopee.vn/m/sieu-hoi-tieu-dung"
        },
        {
            "code": "FASHION20",
            "title": "Voucher Thời Trang & Phụ Kiện Giảm 20%",
            "detail": "Áp dụng cho quần áo, giày dép, túi ví thời trang hot trend.",
            "category": "nganh_hang",
            "save_url": "https://shopee.vn/m/shopee-fashion"
        }
    ]

    results = []
    aff_cache = {}

    for v in vouchers_template:
        save_link = v["save_url"]
        if save_link not in aff_cache:
            sub = v["category"]
            c_res = shopee_aff_converter.convert_to_shopee_aff_link(save_link, sub_ids=[sub])
            aff_cache[save_link] = c_res.get("short_link") or save_link

        aff_link = aff_cache[save_link]
        cid = hashlib.md5(f"shopee_{v['code']}_{today_str}".encode()).hexdigest()[:16]

        results.append({
            "id": cid,
            "merchant": "shopee",
            "title": v["title"],
            "code": v["code"],
            "detail": v["detail"],
            "category": v["category"],
            "start_at": today_start,
            "end_at": today_end,
            "url": save_link,
            "save_url": save_link,
            "aff_url": aff_link
        })

    return results

def fetch_accesstrade():
    """Lấy voucher từ Accesstrade nếu có token cấu hình."""
    tok = os.getenv("ACCESSTRADE_TOKEN")
    if not tok: return []
    try:
        r = requests.get("https://api.accesstrade.vn/v1/offers_informations",
                         headers={"Authorization": f"Token {tok}"},
                         params={"merchant": "shopee", "status": 1, "limit": 50}, timeout=15)
        out = []
        for o in r.json().get("data", []):
            coupon = (o.get("coupons") or [{}])[0] if o.get("coupons") else {}
            out.append(dict(id=hashlib.md5(f"at_{o.get('id')}".encode()).hexdigest()[:16],
                            merchant=o.get("merchant", "shopee"), title=o.get("name", ""),
                            code=coupon.get("coupon_code", ""), category="toan_san",
                            detail=o.get("content", "")[:120], start_at=_ts(o.get("start_time")),
                            end_at=_ts(o.get("end_time")), url=o.get("link", ""),
                            save_url=o.get("link", ""), aff_url=o.get("aff_link") or o.get("link", "")))
        return out
    except Exception:
        return []

def _ts(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z", "")).timestamp()
    except Exception: return time.time() + 86400

def manual_events(path="events.yaml"):
    """Lịch sự kiện cố định từ events.yaml (tự động gắn link aff nếu chưa có)."""
    if not os.path.exists(path): return []
    out = []
    try:
        for e in yaml.safe_load(open(path, encoding="utf-8")) or []:
            link = e.get("link", "")
            # Nếu link là placeholder hoặc chưa có aff, convert tự động
            if "DAN_LINK_AFF" in link or ("aff_id=" not in link and "s.shopee.vn" not in link):
                raw_target = link.split("?")[0] if link else "https://shopee.vn/flash_sale"
                c_res = shopee_aff_converter.convert_to_shopee_aff_link(raw_target, sub_ids=["event"])
                aff_url = c_res.get("short_link") or raw_target
            else:
                aff_url = link

            out.append(dict(id=hashlib.md5(f"ev_{e.get('title')}_{e.get('start')}".encode()).hexdigest()[:16],
                            merchant=e.get("merchant", "shopee"), title=e["title"], code=e.get("code", "SỰ KIỆN"),
                            category="flash_sale", detail=e.get("detail", ""), start_at=_ts(e["start"]),
                            end_at=_ts(e["end"]), url=link, save_url=link, aff_url=aff_url))
    except Exception as e:
        print("[coupons] Lỗi đọc events.yaml:", e)
    return out

def sync_active_events_yaml(path="events.yaml"):
    """Tự động đồng bộ các sự kiện sale hôm nay vào events.yaml để luôn có dữ liệu chuẩn."""
    from . import shopee
    campaigns = shopee.get_daily_sale_campaigns()
    now_dt = datetime.datetime.now()
    today_start_iso = now_dt.replace(hour=0, minute=0, second=0).isoformat()
    today_end_iso = (now_dt + datetime.timedelta(days=2)).replace(hour=23, minute=59, second=59).isoformat()

    event_items = []
    for c in campaigns:
        event_items.append({
            "title": c["title"].replace("🎉 ", "").replace("⚡ ", ""),
            "merchant": "shopee",
            "start": today_start_iso,
            "end": today_end_iso,
            "detail": f"{c['description']} • Khung giờ: {c['slot']}",
            "link": c["aff_url"] or c["url"]
        })

    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(event_items, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print("[coupons] Không thể ghi đè events.yaml:", e)

def refresh():
    """
    Quét và tổng hợp mới toàn bộ mã giảm giá & sự kiện trong ngày.
    1. Lấy danh sách Voucher Shopee chuẩn kèm link affiliate.
    2. Cập nhật các offer từ Accesstrade nếu có.
    3. Cập nhật events.yaml và nạp vào database.
    """
    # 1. Đồng bộ events.yaml với các chiến dịch sale hôm nay
    sync_active_events_yaml()

    # 2. Thu thập danh sách voucher từ tất cả các nguồn
    all_vouchers = get_daily_shopee_vouchers() + fetch_accesstrade() + manual_events()
    added = 0
    now = time.time()

    for c in all_vouchers:
        cid = c["id"]
        cat = c.get("category", "toan_san")
        save_url = c.get("save_url") or c.get("url")

        # Lưu hoặc cập nhật vào database
        existing = db.q("SELECT id FROM coupons WHERE id=?", (cid,), one=True)
        if existing:
            db.x("""UPDATE coupons SET merchant=?, title=?, code=?, detail=?, category=?, save_url=?,
                                       start_at=?, end_at=?, url=?, aff_url=? WHERE id=?""",
                 (c["merchant"], c["title"], c["code"], c["detail"], cat, save_url,
                  c["start_at"], c["end_at"], c["url"], c["aff_url"], cid))
        else:
            db.x("""INSERT INTO coupons(id,merchant,title,code,detail,category,save_url,start_at,end_at,url,aff_url,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (cid, c["merchant"], c["title"], c["code"], c["detail"], cat, save_url,
                  c["start_at"], c["end_at"], c["url"], c["aff_url"], now))
            added += 1

    return added

def active(limit=15):
    """Lấy danh sách mã giảm giá đang active trong thời gian này."""
    now = time.time()
    return db.q("SELECT * FROM coupons WHERE end_at>? AND start_at<=? ORDER BY category ASC, end_at ASC LIMIT ?", (now, now + 3600, limit))

def build_digest(merchant="shopee"):
    """
    Tạo bản tin săn sale hấp dẫn với đầy đủ link lưu mã Shopee Affiliate.
    Trả về: (ảnh card, danh sách 3 biến thể caption, comment chứa link affiliate).
    """
    cs = [dict(c) for c in active(limit=15) if c["merchant"] == merchant]
    if len(cs) < 2:
        # Nếu chưa có mã trong DB, tự động refresh nạp mã ngay
        refresh()
        cs = [dict(c) for c in active(limit=15) if c["merchant"] == merchant]

    if len(cs) < 2:
        return None

    today = datetime.date.today().strftime("%d/%m")
    lines = [((c["code"] or "VOUCHER"), c["title"] or c["detail"]) for c in cs[:8]]
    img = images.digest_card(f"Mã Giảm Giá Shopee {today}", lines, f"digest_{merchant}_{today.replace('/','')}")

    # Nhóm mã theo từng loại để tạo comment chuyên nghiệp
    freeship_links = [c["aff_url"] for c in cs if c.get("category") == "freeship"]
    live_links = [c["aff_url"] for c in cs if c.get("category") == "live_video"]
    toan_san_links = [c["aff_url"] for c in cs if c.get("category") == "toan_san"]
    flash_links = [c["aff_url"] for c in cs if c.get("category") == "flash_sale"]

    fs_link = freeship_links[0] if freeship_links else "https://shopee.vn/m/mien-phi-van-chuyen"
    live_link = live_links[0] if live_links else "https://shopee.vn/m/shopee-live"
    ts_link = toan_san_links[0] if toan_san_links else "https://shopee.vn/m/ma-giam-gia"
    fl_link = flash_links[0] if flash_links else "https://shopee.vn/flash_sale"

    caps = [
        f"🔥 TỔNG HỢP MÃ GIẢM GIÁ & DEAL SỐC SHOPEE HÔM NAY ({today}) cho cả nhà săn sale nhé! Có mã freeship 0đ, voucher Live 50% và hoàn xu toàn sàn. Link nhận mã mình để ở comment nha 👇",
        f"⚡ Cập nhật nhanh list Voucher Shopee VIP ({today}) mới lên sớm nay. Mọi người lưu mã trên banner sớm kẻo hết lượt nha, link chi tiết dưới bình luận nhé!",
        f"📢 Bản tin săn sale {today}: Tổng hợp mã freeship, voucher Shopee Live/Video giảm 20-50% và khung giờ Flash Sale săn deal 1k. Link lưu mã mình ghim ở comment nha!"
    ]

    comment = (
        f"🔥 LINK LƯU VOUCHER & SĂN SALE SHOPEE HÔM NAY ({today}):\n"
        f"🚚 Mã Freeship 0đ & Freeship Xtra: {fs_link}\n"
        f"🎬 Voucher Shopee Live & Shopee Video (-20% đến 50%): {live_link}\n"
        f"🎟 Siêu Voucher Toàn Sàn & Hoàn Xu: {ts_link}\n"
        f"⚡ Khung Giờ Flash Sale Săn Deal 1K: {fl_link}\n"
        f"👉 Mọi người vào sớm bấm Lưu Mã trên banner trước khi hết lượt nhé!"
    )

    return img, caps, comment
