"""Module 2a: lấy deal từ nguồn chính thức + chấm điểm."""
import os, math, time, requests, db
from . import images

class Source:
    def fetch(self, niche): raise NotImplementedError

class AccessTrade(Source):
    """Chỉnh endpoint/field theo tài liệu Accesstrade bạn đang dùng."""
    def fetch(self, niche):
        tok = os.getenv("ACCESSTRADE_TOKEN")
        if not tok: return []
        try:
            r = requests.get("https://api.accesstrade.vn/v1/datafeeds",
                             headers={"Authorization": f"Token {tok}"},
                             params={"merchant": "shopee", "keywords": niche, "limit": 50}, timeout=30)
            out = []
            for d in r.json().get("data", []):
                out.append(dict(id=str(d.get("sku") or d.get("id")), niche=niche, title=d["name"],
                                price=d.get("price"), orig_price=d.get("discount_price") or d.get("price"),
                                discount=d.get("discount_rate") or 0, commission=d.get("commission_rate") or 0,
                                rating=d.get("rating") or 0, sold=d.get("sold") or 0,
                                url=d["url"], aff_url=d.get("aff_link") or d["url"], image=d.get("image")))
            return out
        except Exception:
            return []

class ShopeeSource(Source):
    """Cào deal trực tiếp từ Shopee theo từ khóa ngách."""
    def fetch(self, niche):
        from . import shopee
        return shopee.crawl_shopee_deals_by_keyword(niche, limit=25)

SOURCES = [ShopeeSource(), AccessTrade()]


def score(d):
    s  = min(d["discount"], 70) / 70 * 40
    s += max(0, (d["rating"] - 4.0)) / 1.0 * 20
    s += min(math.log10(d["sold"] + 1) / 4, 1) * 20
    s += min(d["commission"], 12) / 12 * 20
    if d.get("is_vip") or d.get("is_mall"):
        s = min(100.0, s + 10.0)
    return round(s, 1)

def ensure_deal_aff_link(deal):
    """Đảm bảo deal luôn có link affiliate chuẩn Shopee (Publisher ID hoặc s.shopee.vn)."""
    aff_url = (deal.get("aff_url") or deal.get("url") or "").strip()
    if not aff_url:
        return ""
    if "s.shopee.vn" in aff_url or "aff_id=" in aff_url:
        return aff_url
    try:
        from . import shopee_aff_converter
        raw_url = deal.get("url") or aff_url
        res = shopee_aff_converter.convert_to_shopee_aff_link(raw_url, sub_ids=["deallist"])
        if res.get("success") and res.get("short_link"):
            return res["short_link"]
    except Exception as e:
        print(f"[deals] Lỗi convert link affiliate cho deal {deal.get('id')}: {e}")
    return aff_url

def convert_all_deals_to_aff():
    """Chuyển đổi toàn bộ deal đang có trong database sang link affiliate Shopee."""
    rows = db.q("SELECT id, url, aff_url FROM deals")
    updated = 0
    from . import shopee_aff_converter
    for r in rows:
        aff = (r["aff_url"] or "").strip()
        if "aff_id=" not in aff and "s.shopee.vn" not in aff:
            raw_url = r["url"] or aff
            res = shopee_aff_converter.convert_to_shopee_aff_link(raw_url, sub_ids=["deallist"])
            if res.get("success") and res.get("short_link"):
                db.x("UPDATE deals SET aff_url=? WHERE id=?", (res["short_link"], r["id"]))
                updated += 1
    return updated

def refresh(cfg, target_niche=None):
    from . import shopee
    c = cfg.get("deals", {})
    added = 0
    updated = 0

    # 1. Thu thập ứng viên deals
    candidates = []

    # 1a. Cào Flash Sale chất lượng cao trên Shopee kèm phân loại ngách tự động & nhận diện VIP
    fs_deals = shopee.crawl_shopee_flash_sale(limit=80, target_niche=target_niche)
    candidates.extend(fs_deals)

    # 1b. Cào từ các nguồn theo ngách chỉ định hoặc toàn bộ ngách cấu hình
    if target_niche and target_niche.lower() not in ("all", "tất cả", ""):
        niches_to_crawl = [target_niche.strip()]
    else:
        niches_to_crawl = cfg.get("niches", [])

    for niche in niches_to_crawl:
        for src in SOURCES:
            try:
                candidates.extend(src.fetch(niche))
            except Exception as e:
                print(f"[deals] Lỗi fetch nguồn {src.__class__.__name__} ngách '{niche}':", e)

    now = time.time()
    seen_ids = set()

    for d in candidates:
        deal_id = d.get("id")
        if not deal_id or deal_id in seen_ids:
            continue
        seen_ids.add(deal_id)

        is_vip = int(d.get("is_vip") or 0)
        is_mall = int(d.get("is_mall") or 0)
        brand = str(d.get("brand") or "").strip()

        # Lọc ngưỡng
        if (d["discount"] < c.get("min_discount", 15) or 
            d["rating"] < c.get("min_rating", 4.0) or 
            d["sold"] < c.get("min_sold", 30)):
            continue

        d["score"] = score(d)
        if d["score"] < c.get("min_score", 45):
            continue

        # Đảm bảo link affiliate chuẩn xác cho Publisher
        aff_link = ensure_deal_aff_link(d)
        d["aff_url"] = aff_link

        existing = db.q("SELECT id, aff_url FROM deals WHERE id=?", (deal_id,), one=True)
        if existing:
            current_aff = (existing["aff_url"] or "").strip()
            if "aff_id=" not in current_aff and "s.shopee.vn" not in current_aff:
                current_aff = aff_link
            # Cập nhật giá, điểm số mới và kích hoạt lại deal còn hạn
            db.x("""UPDATE deals SET price=?, orig_price=?, discount=?, rating=?, sold=?, score=?, is_valid=1, last_checked_at=?, is_vip=?, is_mall=?, brand=?, aff_url=?
                    WHERE id=?""", (d["price"], d["orig_price"], d["discount"], d["rating"], d["sold"], d["score"], now, is_vip, is_mall, brand, current_aff, deal_id))
            updated += 1
        else:
            # Thêm mới deal vào kho với link affiliate chuẩn
            db.x("""INSERT INTO deals(id,niche,title,price,orig_price,discount,commission,rating,sold,url,aff_url,image,score,created_at,is_valid,last_checked_at,is_vip,is_mall,brand)
                    VALUES(:id,:niche,:title,:price,:orig_price,:discount,:commission,:rating,:sold,:url,:aff_url,:image,:score,:t,1,:t,:is_vip,:is_mall,:brand)""",
                 {**d, "t": now, "is_vip": is_vip, "is_mall": is_mall, "brand": brand})
            added += 1
            p = images.prepare_deal_image(d)
            if p:
                db.x("UPDATE deals SET image_path=? WHERE id=?", (p, deal_id))

    return added, updated

def still_valid(deal):
    """Kiểm tra lại giá/còn hàng ngay trước khi đăng thật.
    Xác minh link sản phẩm không bị 404, không bị xóa sản phẩm hay báo hết hàng.
    """
    if not deal:
        return False
    
    deal = dict(deal)
    deal_id = deal.get("id")
    url_to_check = deal.get("url") or deal.get("aff_url")
    if not url_to_check:
        return False


    now = time.time()
    # Nếu deal đã được kiểm tra hợp lệ trong vòng 15 phút trước thì tái sử dụng kết quả
    if deal.get("last_checked_at") and (now - deal["last_checked_at"] < 900) and deal.get("is_valid") == 1:
        return True

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
    }

    try:
        # Gửi request kiểm tra trang đích
        res = requests.get(url_to_check, headers=headers, timeout=10, allow_redirects=True)
        if res.status_code in (404, 410):
            print(f"[deals] Deal {deal_id} không còn tồn tại (HTTP {res.status_code})")
            db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
            return False

        final_url = res.url.lower()
        if "error" in final_url or "not_found" in final_url or "404" in final_url:
            print(f"[deals] Deal {deal_id} bị chuyển hướng đến trang lỗi: {final_url}")
            db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
            return False

        # Kiểm tra nội dung văn bản tìm các dấu hiệu hết hàng / đã xóa
        content_lower = res.text.lower()
        not_available_signals = [
            "sản phẩm không tồn tại",
            "sản phẩm này không tồn tại",
            "sản phẩm đã bị xóa",
            "không tìm thấy sản phẩm",
            "mặt hàng này đã hết hàng"
        ]
        for signal in not_available_signals:
            if signal in content_lower:
                print(f"[deals] Deal {deal_id} báo hết hàng/không tồn tại: '{signal}'")
                db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
                return False

        # Deal còn tốt
        db.x("UPDATE deals SET is_valid=1, last_checked_at=? WHERE id=?", (now, deal_id))
        return True

    except requests.RequestException as e:
        print(f"[deals] Lỗi mạng khi kiểm tra deal {deal_id} ({e}), tạm thời giữ nguyên hợp lệ.")
        return True


def cleanup_expired_deals(cfg=None, delete_from_db: bool = True, min_discount: float = 10.0) -> dict:
    """
    Quét lại toàn bộ các deal đang lưu trong cơ sở dữ liệu:
    1. Kiểm tra đối chiếu với danh sách Flash Sale hiện thời của Shopee.
    2. Gửi request kiểm tra link, phát hiện sản phẩm bị xóa, hết hàng, hoặc trang lỗi.
    3. Kiểm tra thời hạn Flash Sale (các deal Flash sale quá 24h và không còn trong danh sách sale).
    4. Nếu hết sale / hết hàng / lỗi: Tự động loại bỏ và xóa khỏi database (kèm ảnh cache).
    """
    now = time.time()
    all_deals = db.q("SELECT * FROM deals ORDER BY created_at DESC")
    if not all_deals:
        return {
            "success": True,
            "total_checked": 0,
            "still_valid_count": 0,
            "removed_count": 0,
            "removed_deals": [],
            "message": "Hiện không có deal nào trong kho dữ liệu để dọn dẹp."
        }

    # 1. Thu thập danh sách Flash Sale hiện thời từ Shopee để so sánh nhanh
    live_fs_map = {}
    try:
        from . import shopee
        fs_items = shopee.crawl_shopee_flash_sale(limit=100)
        for it in fs_items:
            live_fs_map[it["id"]] = it
    except Exception as e:
        print("[deals] Không thể lấy live flash sale để đối chiếu:", e)

    valid_deals = []
    removed_deals = []

    headers = {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
        "Accept-Language": "vi-VN,vi;q=0.9"
    }

    one_day_ago = now - 24 * 3600

    for d in all_deals:
        d_dict = dict(d)
        deal_id = d_dict["id"]
        title = d_dict.get("title") or "Deal Shopee"
        url_to_check = d_dict.get("url") or d_dict.get("aff_url")
        created_at = d_dict.get("created_at") or 0
        is_fs_deal = deal_id.startswith("sp_fs_")

        # Trường hợp 1: Deal đang nằm trong Live Flash Sale Shopee -> Chắc chắn còn Sale!
        if deal_id in live_fs_map:
            fs_info = live_fs_map[deal_id]
            # Cập nhật giá mới nhất nếu có
            db.x("""UPDATE deals SET price=?, orig_price=?, discount=?, rating=?, sold=?, is_valid=1, last_checked_at=?
                    WHERE id=?""", (fs_info["price"], fs_info["orig_price"], fs_info["discount"], fs_info["rating"], fs_info["sold"], now, deal_id))
            valid_deals.append(d_dict)
            continue

        # Trường hợp 2: Deal là Flash Sale nhưng đã quá 24h và không còn trong danh sách Flash Sale
        if is_fs_deal and created_at > 0 and created_at < one_day_ago:
            reason = "Hết đợt Flash Sale (đã qua hơn 24h)"
            removed_deals.append({"id": deal_id, "title": title, "reason": reason})
            if delete_from_db:
                db.x("DELETE FROM deals WHERE id=?", (deal_id,))
                db.x("DELETE FROM posts WHERE deal_id=? AND status='queued'", (deal_id,))
                if d_dict.get("image_path") and os.path.exists(d_dict["image_path"]):
                    try:
                        os.remove(d_dict["image_path"])
                    except Exception:
                        pass
            else:
                db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
            continue

        # Trường hợp 3: Kiểm tra link thực tế
        if not url_to_check:
            reason = "Không có đường dẫn sản phẩm"
            removed_deals.append({"id": deal_id, "title": title, "reason": reason})
            if delete_from_db:
                db.x("DELETE FROM deals WHERE id=?", (deal_id,))
                db.x("DELETE FROM posts WHERE deal_id=? AND status='queued'", (deal_id,))
            continue

        try:
            res = requests.get(url_to_check, headers=headers, timeout=8, allow_redirects=True)
            
            # Check mã lỗi HTTP
            if res.status_code in (404, 410):
                reason = f"Link sản phẩm không tồn tại (HTTP {res.status_code})"
                removed_deals.append({"id": deal_id, "title": title, "reason": reason})
                if delete_from_db:
                    db.x("DELETE FROM deals WHERE id=?", (deal_id,))
                    db.x("DELETE FROM posts WHERE deal_id=? AND status='queued'", (deal_id,))
                    if d_dict.get("image_path") and os.path.exists(d_dict["image_path"]):
                        try:
                            os.remove(d_dict["image_path"])
                        except Exception:
                            pass
                else:
                    db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
                continue

            final_url = res.url.lower()
            if any(k in final_url for k in ("error", "traffic/error", "verify", "not_found")):
                reason = "Trang bị chặn hoặc chuyển hướng lỗi"
                removed_deals.append({"id": deal_id, "title": title, "reason": reason})
                if delete_from_db:
                    db.x("DELETE FROM deals WHERE id=?", (deal_id,))
                    db.x("DELETE FROM posts WHERE deal_id=? AND status='queued'", (deal_id,))
                    if d_dict.get("image_path") and os.path.exists(d_dict["image_path"]):
                        try:
                            os.remove(d_dict["image_path"])
                        except Exception:
                            pass
                else:
                    db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
                continue

            # Check meta og:title xem sản phẩm có bị Shopee xóa về trang chủ không
            og_match = re.search(r'property="og:title"\s+content="([^"]+)"', res.text, re.I)
            og_title = og_match.group(1) if og_match else ""
            if "Shopee Việt Nam | Mua và Bán" in og_title and len(og_title) < 70:
                reason = "Sản phẩm đã bị xóa hoặc ngừng kinh doanh trên sàn"
                removed_deals.append({"id": deal_id, "title": title, "reason": reason})
                if delete_from_db:
                    db.x("DELETE FROM deals WHERE id=?", (deal_id,))
                    db.x("DELETE FROM posts WHERE deal_id=? AND status='queued'", (deal_id,))
                    if d_dict.get("image_path") and os.path.exists(d_dict["image_path"]):
                        try:
                            os.remove(d_dict["image_path"])
                        except Exception:
                            pass
                else:
                    db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
                continue

            # Check văn bản tìm dấu hiệu hết hàng
            content_lower = res.text.lower()
            not_available_signals = [
                "sản phẩm không tồn tại", "sản phẩm này không tồn tại",
                "sản phẩm đã bị xóa", "không tìm thấy sản phẩm",
                "mặt hàng này đã hết hàng"
            ]
            has_signal = any(sig in content_lower for sig in not_available_signals)
            if has_signal:
                reason = "Báo hết hàng hoặc không tìm thấy mặt hàng"
                removed_deals.append({"id": deal_id, "title": title, "reason": reason})
                if delete_from_db:
                    db.x("DELETE FROM deals WHERE id=?", (deal_id,))
                    db.x("DELETE FROM posts WHERE deal_id=? AND status='queued'", (deal_id,))
                    if d_dict.get("image_path") and os.path.exists(d_dict["image_path"]):
                        try:
                            os.remove(d_dict["image_path"])
                        except Exception:
                            pass
                else:
                    db.x("UPDATE deals SET is_valid=0, status='expired', last_checked_at=? WHERE id=?", (now, deal_id))
                continue

            # Deal vẫn hợp lệ
            db.x("UPDATE deals SET is_valid=1, last_checked_at=? WHERE id=?", (now, deal_id))
            valid_deals.append(d_dict)

        except Exception as e:
            # Lỗi mạng tạm thời, giữ nguyên deal
            print(f"[deals] Kiểm tra deal {deal_id} gặp lỗi mạng ({e}), tạm giữ lại.")
            valid_deals.append(d_dict)

    action_text = "đã tự động xóa bỏ" if delete_from_db else "đã đánh dấu hết hạn"
    return {
        "success": True,
        "total_checked": len(all_deals),
        "still_valid_count": len(valid_deals),
        "removed_count": len(removed_deals),
        "removed_deals": removed_deals,
        "message": f"Hoàn tất quét {len(all_deals)} deal: Giữ lại {len(valid_deals)} deal còn sale, {action_text} {len(removed_deals)} deal hết hạn/hết hàng."
    }


