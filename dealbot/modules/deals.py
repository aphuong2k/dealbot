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
    """Cào deal trực tiếp từ Shopee (Flash Sale & tìm kiếm theo ngách)."""
    def fetch(self, niche):
        from . import shopee
        out = []
        # 1. Cào deal sản phẩm theo từ khóa ngách
        niche_deals = shopee.crawl_shopee_deals_by_keyword(niche, limit=25)
        out.extend(niche_deals)
        # 2. Cào thêm deal Flash Sale hot trên Shopee
        fs_deals = shopee.crawl_shopee_flash_sale(limit=30)
        for d in fs_deals:
            d["niche"] = niche
        out.extend(fs_deals)
        return out

SOURCES = [ShopeeSource(), AccessTrade()]


def score(d):
    s  = min(d["discount"], 70) / 70 * 40
    s += max(0, (d["rating"] - 4.0)) / 1.0 * 20
    s += min(math.log10(d["sold"] + 1) / 4, 1) * 20
    s += min(d["commission"], 12) / 12 * 20
    return round(s, 1)

def refresh(cfg):
    c = cfg["deals"]; added = 0
    for niche in cfg["niches"]:
        for src in SOURCES:
            for d in src.fetch(niche):
                if d["discount"] < c["min_discount"] or d["rating"] < c["min_rating"] or d["sold"] < c["min_sold"]:
                    continue
                d["score"] = score(d)
                if d["score"] < c["min_score"]: continue
                if db.q("SELECT 1 FROM deals WHERE id=?", (d["id"],), one=True): continue
                db.x("""INSERT INTO deals(id,niche,title,price,orig_price,discount,commission,rating,sold,url,aff_url,image,score,created_at)
                        VALUES(:id,:niche,:title,:price,:orig_price,:discount,:commission,:rating,:sold,:url,:aff_url,:image,:score,:t)""",
                     {**d, "t": time.time()}); added += 1
                p = images.prepare_deal_image(d)
                if p: db.x("UPDATE deals SET image_path=? WHERE id=?", (p, d["id"]))
    return added

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

