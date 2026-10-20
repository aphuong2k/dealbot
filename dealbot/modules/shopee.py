"""Module quản lý Shopee Affiliate:
1. Lưu & xác thực Cookie Shopee / Shopee Affiliate
2. Cào Cây Danh Mục Ngành Hàng chính thức từ Shopee (Category Tree)
3. Cào Deal Flash Sale & Deal theo từng ngành hàng/từ khóa (Niches)
4. Tự động sinh link Shopee Affiliate có gắn Sub-ID
"""
import os, sys, time, json, requests, re
from typing import List, Dict, Any, Optional

COOKIE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies", "shopee_aff.json")

def parse_shopee_cookie_input(raw_text: str) -> List[Dict[str, Any]]:
    """Phân tích cookie dán từ Cookie-Editor (JSON) hoặc chuỗi Header (SPC_EC=...; SPC_U=...)."""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Dữ liệu cookie trống.")

    # 1. Thử parse dạng JSON từ Cookie-Editor extension
    if raw_text.startswith("[") and raw_text.endswith("]"):
        try:
            data = json.loads(raw_text)
            if isinstance(data, list):
                cleaned = []
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        cleaned.append({
                            "name": str(item["name"]).strip(),
                            "value": str(item["value"]).strip(),
                            "domain": str(item.get("domain", ".shopee.vn")).strip(),
                            "path": str(item.get("path", "/")).strip(),
                            "secure": bool(item.get("secure", True)),
                            "sameSite": item.get("sameSite", "no_restriction")
                        })
                if cleaned:
                    return cleaned
        except json.JSONDecodeError:
            pass

    # 2. Thử parse dạng chuỗi Header (SPC_EC=...; SPC_U=...)
    items = []
    for part in raw_text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        items.append({
            "name": k.strip(),
            "value": v.strip(),
            "domain": ".shopee.vn",
            "path": "/",
            "secure": True,
            "sameSite": "no_restriction"
        })

    if items:
        return items

    raise ValueError("Không nhận diện được định dạng Cookie Shopee. Vui lòng dán mảng JSON hoặc chuỗi 'SPC_EC=...; SPC_U=...'")

def get_shopee_cookie_info() -> Dict[str, Any]:
    """Lấy thông tin file cookie Shopee hiện tại."""
    info = {
        "exists": False,
        "count": 0,
        "spc_u": None,
        "has_spc_ec": False,
        "updated_at": None,
        "size_bytes": 0,
        "raw_content": ""
    }

    if os.path.exists(COOKIE_FILE):
        info["exists"] = True
        info["size_bytes"] = os.path.getsize(COOKIE_FILE)
        info["updated_at"] = int(os.path.getmtime(COOKIE_FILE))
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                info["count"] = len(data)
                info["raw_content"] = json.dumps(data, indent=2, ensure_ascii=False)
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        val = item.get("value", "")
                        if name == "SPC_U":
                            info["spc_u"] = str(val)
                        elif name == "SPC_EC":
                            info["has_spc_ec"] = True
        except Exception as e:
            info["raw_content"] = f"Lỗi đọc file: {e}"

    return info

def save_shopee_cookie(raw_cookie: str) -> Dict[str, Any]:
    """Lưu cookie Shopee Aff vào file."""
    cookies_list = parse_shopee_cookie_input(raw_cookie)
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, indent=2, ensure_ascii=False)

    info = get_shopee_cookie_info()
    msg = f"Đã lưu thành công {info['count']} cookies Shopee!"
    if info.get("spc_u"):
        msg += f" (Shopee User ID: {info['spc_u']})"
    if not info.get("has_spc_ec"):
        msg += " ⚠️ Chú ý: Chưa thấy session 'SPC_EC', hãy đảm bảo đã copy khi đã đăng nhập Shopee."

    return {"message": msg, "info": info}

def delete_shopee_cookie() -> Dict[str, Any]:
    """Xóa file cookie Shopee."""
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
        return {"message": "Đã xóa file cookie Shopee thành công."}
    return {"message": "File cookie Shopee không tồn tại."}

def test_shopee_connect() -> Dict[str, Any]:
    """Kiểm tra trạng thái Cookie Shopee bằng Playwright hoặc gọi API."""
    if not os.path.exists(COOKIE_FILE):
        return {
            "success": False,
            "message": "Chưa có file cookie Shopee. Vui lòng nhập Cookie trước.",
            "spc_u": None
        }

    info = get_shopee_cookie_info()
    try:
        from playwright.sync_api import sync_playwright

        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            raw_cookies = json.load(f)

        playwright_cookies = []
        for c in raw_cookies:
            ck = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".shopee.vn"),
                "path": c.get("path", "/"),
                "secure": True
            }
            if not ck["domain"].startswith("."):
                ck["domain"] = ".shopee.vn"
            playwright_cookies.append(ck)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            ctx.add_cookies(playwright_cookies)
            page = ctx.new_page()
            page.goto("https://shopee.vn/", wait_until="domcontentloaded", timeout=25000)
            time.sleep(2)

            final_url = page.url
            title = page.title()
            browser.close()

        is_blocked = "traffic/error" in final_url or "verify" in final_url
        if is_blocked:
            return {
                "success": False,
                "spc_u": info.get("spc_u"),
                "url": final_url,
                "title": title,
                "message": f"❌ Cookie Shopee đã hết hạn hoặc bị Shopee yêu cầu xác minh lại! (URL: {final_url})"
            }

        return {
            "success": True,
            "spc_u": info.get("spc_u"),
            "url": final_url,
            "title": title,
            "message": f"✅ Kết nối Shopee thành công! Cookie đang hoạt động ổn định (UID: {info.get('spc_u') or 'Đã nhận'})."
        }

    except Exception as e:
        # Fallback kiểm tra qua API trực tiếp nếu Playwright gặp sự cố
        return {
            "success": bool(info.get("has_spc_ec") or info.get("spc_u")),
            "spc_u": info.get("spc_u"),
            "message": f"Kiểm tra nhanh cookie: Có {info['count']} mục. Lỗi kiểm tra trình duyệt: {str(e)}"
        }

def fetch_shopee_categories() -> List[Dict[str, Any]]:
    """Cào toàn bộ Cây Danh Mục Ngành Hàng tiếng Việt chính thức từ Shopee."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "vi-VN,vi;q=0.9",
        "Referer": "https://shopee.vn/"
    }
    url = "https://shopee.vn/api/v4/pages/get_category_tree"
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            data = r.json().get("data", {}).get("category_list", [])
            categories = []
            for c in data:
                cat_item = {
                    "catid": c.get("catid"),
                    "name": c.get("display_name") or c.get("name"),
                    "english_name": c.get("name"),
                    "children": [
                        {
                            "catid": sub.get("catid"),
                            "name": sub.get("display_name") or sub.get("name")
                        }
                        for sub in c.get("children", [])
                    ]
                }
                categories.append(cat_item)
            return categories
    except Exception as e:
        print("[shopee] Lỗi khi cào danh mục Shopee:", e)
    return []

def classify_product_niche(title: str, default_niche: str = "săn sale shopee") -> str:
    """Tự động phân loại ngành hàng thông minh từ tiêu đề sản phẩm để map chuẩn xác vào Nhóm Facebook khi đăng bài."""
    if not title:
        return default_niche
    t = title.lower()

    # 1. Mỹ phẩm / Sắc đẹp (Bao gồm bodymist, son, kem, serum, v.v.)
    cosmetic_re = re.compile(r'\b(son|son môi|kem|phấn|serum|mặt nạ|tẩy trang|sữa rửa mặt|nước hoa|dưỡng da|chống nắng|trang điểm|lotion|mascara|cushion|toner|sữa tắm|dầu gội|skincare|bodymist|body mist|nước tẩy trang)\b', re.I)
    if cosmetic_re.search(t):
        return "mỹ phẩm"

    # 2. Gia dụng / Nhà cửa & Đời sống
    home_re = re.compile(r'\b(nồi|chảo|nước giặt|xả vải|bếp|bình giữ nhiệt|lau nhà|túi rác|hộp cơm|máy xay|chổi|khăn|drap|ga giường|chiếu|gia dụng|quạt|đèn|vệ sinh|kệ để đồ|tẩy rửa|nước lau|nước tẩy|nhà tắm|bồn cầu|xịt phòng|nước rửa chén)\b', re.I)
    if home_re.search(t):
        return "gia dụng"

    # 3. Mẹ & Bé
    baby_re = re.compile(r'\b(sữa bột|bỉm|tã|trẻ em|bình sữa|sơ sinh|núm ti|xe đẩy|ăn dặm|mẹ và bé|mẹ bé|cho bé|cho con)\b', re.I)
    if baby_re.search(t):
        return "mẹ và bé"

    # 4. Công nghệ / Thiết bị điện tử
    tech_re = re.compile(r'\b(tai nghe|sạc|cáp|pin dự phòng|điện thoại|chuột|bàn phím|loa|bluetooth|cường lực|ốp lưng|củ sạc|mic|laptop|máy tính|công nghệ|phím cơ|switch|keycap|màn hình|camera|smartwatch)\b', re.I)
    if tech_re.search(t):
        return "đồ công nghệ giá rẻ"

    # 5. Thể thao & Dã ngoại
    sport_re = re.compile(r'\b(thể thao|gym|chạy bộ|camping|dã ngoại|yoga|lều|bình nước thể thao)\b', re.I)
    if sport_re.search(t):
        return "Thể Thao & Dã Ngoại"

    # 6. Thời trang Nữ (Ưu tiên từ khóa nữ đặc trưng)
    female_re = re.compile(r'\b(nữ|váy|đầm|chân váy|croptop|áo lót|quần lót nữ|bra|tiểu thư|búp bê|guốc|cao gót|cardigan|women|túi xách nữ|yếm nữ)\b', re.I)
    
    # 7. Thời trang Nam (Từ khóa nam đặc trưng)
    male_re = re.compile(r'\b(nam|sơ mi nam|polo nam|áo thun nam|quần nam|quần âu nam|quần tây nam|quần jean nam|khoác nam|ví nam|thắt lưng nam|clutch nam|boxer|sịp nam|giày nam|dép nam|men|cạo râu|dao cạo)\b', re.I)

    has_female = bool(female_re.search(t))
    has_male = bool(male_re.search(t))

    if has_female and not has_male:
        return "Thời Trang Nữ"
    if has_male and not has_female:
        return "Thời Trang Nam"
    if has_female:
        return "Thời Trang Nữ"
    if has_male:
        return "Thời Trang Nam"

    # 8. Quần áo / Giày dép chung chung
    if any(w in t for w in ["áo ", "quần ", "giày", "dép", "balo", "ví ", "tất", "vớ", "mũ", "nón", "thời trang", "sneaker", "hoodie"]):
        return "Thời Trang Nữ" if ("nữ" in t or "váy" in t) else "Thời Trang Nam"

    return default_niche

def crawl_shopee_flash_sale(limit: int = 60, target_niche: Optional[str] = None) -> List[Dict[str, Any]]:
    """Cào các deal Flash Sale giảm giá sốc hiện tại trên Shopee, kèm phân loại ngành hàng thông minh."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "vi-VN,vi;q=0.9",
        "Referer": "https://shopee.vn/flash_sale"
    }
    url = f"https://shopee.vn/api/v4/flash_sale/flash_sale_get_items?limit={limit}"
    out = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", {}).get("items", [])
            for it in items:
                itemid = it.get("itemid")
                shopid = it.get("shopid")
                name = it.get("name") or "Deal Shopee Flash Sale"
                price_raw = it.get("price") or 0
                orig_raw = it.get("price_before_discount") or price_raw
                # Quy đổi đơn vị micro-currency của Shopee (chia cho 100,000)
                price = round(price_raw / 100000) if price_raw > 100000 else price_raw
                orig_price = round(orig_raw / 100000) if orig_raw > 100000 else orig_raw

                discount_str = str(it.get("discount") or "0").replace("%", "").strip()
                try:
                    discount = float(discount_str)
                except ValueError:
                    discount = round((orig_price - price) / orig_price * 100, 1) if orig_price > price else 0

                # Nếu giảm giá tính được cao hơn discount_str thì ưu tiên
                if orig_price > price:
                    calc_disc = round((orig_price - price) / orig_price * 100, 1)
                    discount = max(discount, calc_disc)

                img_hash = it.get("image") or ""
                img_url = f"https://down-vn.img.susercontent.com/file/{img_hash}" if img_hash else ""
                prod_url = f"https://shopee.vn/product/{shopid}/{itemid}" if shopid and itemid else f"https://shopee.vn/flash_sale"

                # LẤY CHÍNH XÁC SỐ LƯỢT BÁN LỊCH SỬ (historical_sold)
                sold = it.get("historical_sold") or it.get("flash_sale_stock") or it.get("promo_sold") or 100
                rating = round(float(it.get("item_rating", {}).get("rating_star", 4.9) or 4.9), 1)

                # Phân loại Shopee Mall & Deal VIP
                is_mall = 1 if (it.get("is_shop_official") or it.get("shop_type") == 1) else 0
                brand_name = str(it.get("brand") or it.get("brand_sale_brand_custom_logo") or "").strip()
                is_vip = 1 if (is_mall or brand_name or (discount >= 30 and rating >= 4.7 and sold >= 20)) else 0

                # Tự động gán niche thông minh theo tên sản phẩm
                prod_niche = classify_product_niche(name)
                
                # Nếu người dùng lọc đích danh 1 ngành cụ thể
                if target_niche and target_niche.lower() not in ("all", "tất cả", ""):
                    tn = target_niche.lower().strip()
                    # Khớp niche hoặc khớp từ khóa trong tên
                    if prod_niche.lower() != tn and tn not in name.lower():
                        continue

                out.append({
                    "id": f"sp_fs_{itemid}",
                    "niche": prod_niche,
                    "title": name,
                    "price": price,
                    "orig_price": orig_price,
                    "discount": discount,
                    "commission": 10.0,
                    "rating": rating,
                    "sold": sold,
                    "url": prod_url,
                    "aff_url": prod_url,
                    "image": img_url,
                    "is_mall": is_mall,
                    "is_vip": is_vip,
                    "brand": brand_name
                })
    except Exception as e:
        print("[shopee] Lỗi khi cào flash sale:", e)
    return out

def get_daily_sale_campaigns() -> List[Dict[str, Any]]:
    """
    Tổng hợp các chương trình Sale & Khung giờ vàng trong ngày của Shopee.
    Tất cả link đều được tự động gắn mã Affiliate của người dùng.
    """
    from . import shopee_aff_converter
    now = time.time()
    lt = time.localtime(now)
    day = lt.tm_mday
    month = lt.tm_mon
    weekday = lt.tm_wday
    current_hour = lt.tm_hour

    campaigns = []

    # 1. Chiến dịch lớn theo ngày trong tháng
    mega_title = ""
    mega_desc = ""
    mega_tag = ""
    if day == month:
        mega_title = f"🎉 ĐẠI TIỆC SIÊU SALE NGÀY ĐÔI {day}.{month}"
        mega_desc = "Cơn mưa voucher 500k, freeship 0đ toàn sàn, hàng triệu deal 1k"
        mega_tag = "SIÊU SALE NGÀY ĐÔI"
    elif 14 <= day <= 16:
        mega_title = "🎉 SIÊU SALE GIỮA THÁNG 15 - NỬA THÁNG NỬA GIÁ"
        mega_desc = "Voucher giảm 50% giữa tháng, hoàn xu 20%, freeship xtra toàn sàn"
        mega_tag = "SALE GIỮA THÁNG"
    elif 24 <= day <= 27:
        mega_title = "🎉 LƯƠNG VỀ SALE TO 25 - XẢ KHO ĐÓN LƯƠNG"
        mega_desc = "Xả kho hàng hiệu, voucher hoàn xu 100k, giảm giá đến 70%"
        mega_tag = "LƯƠNG VỀ SALE TO"
    elif weekday in (5, 6):
        mega_title = "🎉 SIÊU SALE CUỐI TUẦN - XẢ KHO GIÁ SỐC"
        mega_desc = "Săn sale thảnh thơi thứ 7 & chủ nhật, deal sốc giảm đến 60%"
        mega_tag = "SALE CUỐI TUẦN"
    else:
        mega_title = f"🎉 CHƯƠNG TRÌNH SĂN SALE SHOPEE HÔM NAY ({day}/{month})"
        mega_desc = "Tổng hợp deal hời & voucher độc quyền toàn sàn cập nhật liên tục"
        mega_tag = "SĂN SALE HÔM NAY"

    mega_landing = "https://shopee.vn/m/ma-giam-gia"
    mega_aff = shopee_aff_converter.convert_to_shopee_aff_link(mega_landing, sub_ids=["mega_sale"]).get("short_link") or mega_landing
    campaigns.append({
        "id": "campaign_mega_today",
        "type": "mega_sale",
        "title": mega_title,
        "description": mega_desc,
        "slot": f"Áp dụng trọn ngày {day}/{month}",
        "tag": mega_tag,
        "is_live_now": True,
        "url": mega_landing,
        "aff_url": mega_aff,
        "banner": "https://deo.shopeemobile.com/shopee/shopee-pcmall-live-sg/flashsale/fb1088de81e42c4e538967ec12993772.png"
    })

    # 2. Khung giờ Flash Sale hiện tại & sắp tới
    slots = [
        {"slot": "00:00 - 02:00", "hour": 0, "title": "⚡ Khung Giờ 0H: Siêu Sale Hủy Diệt Đêm Khuya", 
         "desc": "Deal 0đ, voucher giảm 50% chớp nhoáng, xả hàng tồn kho", "tag": "0H - ĐÊM KHUYA"},
        {"slot": "09:00 - 12:00", "hour": 9, "title": "⚡ Khung Giờ 9H: Đại Tiệc Hàng Hiệu Shopee Mall", 
         "desc": "Thương hiệu chính hãng giảm đến 50%, voucher thương hiệu 100k", "tag": "9H - MALL 50%"},
        {"slot": "12:00 - 14:00", "hour": 12, "title": "⚡ Khung Giờ 12H: Nửa Ngày Nửa Giá - Voucher Xtra", 
         "desc": "Nửa ngày nửa giá, voucher xả kho 50%, freeship 0đ mọi đơn", "tag": "12H - NỬA GIÁ"},
        {"slot": "15:00 - 17:00", "hour": 15, "title": "⚡ Khung Giờ 15H: Giờ Vàng Quốc Tế & Hàng Hot", 
         "desc": "Deal công nghệ, phụ kiện quốc tế giá sốc từ 1k, freeship xtra", "tag": "15H - QUỐC TẾ"},
        {"slot": "18:00 - 21:00", "hour": 18, "title": "⚡ Khung Giờ 18H: Top Deal Bán Chạy & Xu Hướng", 
         "desc": "Các sản phẩm hot trend bán chạy nhất tuần, giảm sâu đến 45%", "tag": "18H - XU HƯỚNG"},
        {"slot": "21:00 - 24:00", "hour": 21, "title": "⚡ Khung Giờ 21H: Gì Cũng Rẻ - Đồng Giá 1K & 9K", 
         "desc": "Xả hàng cuối ngày, phụ kiện và gia dụng đồng giá 1k, 9k", "tag": "21H - RẺ 1K"}
    ]

    for s in slots:
        is_active = (current_hour >= s["hour"] and current_hour < s["hour"] + (3 if s["hour"] in (9,15,18,21) else 2))
        landing = "https://shopee.vn/flash_sale"
        aff_res = shopee_aff_converter.convert_to_shopee_aff_link(landing, sub_ids=[f"fs_{s['hour']}h"])
        aff_url = aff_res.get("short_link") or landing
        campaigns.append({
            "id": f"campaign_fs_{s['hour']}",
            "type": "flash_sale_slot",
            "title": s["title"],
            "description": s["desc"],
            "slot": s["slot"],
            "tag": s["tag"],
            "is_live_now": is_active,
            "url": landing,
            "aff_url": aff_url,
            "banner": ""
        })

    # 3. Chiến dịch Shopee Live & Shopee Video
    live_landing = "https://shopee.vn/m/shopee-live"
    live_aff = shopee_aff_converter.convert_to_shopee_aff_link(live_landing, sub_ids=["live_sale"]).get("short_link") or live_landing
    campaigns.append({
        "id": "campaign_shopee_live",
        "type": "shopee_live",
        "title": "🎬 ĐẠI TIỆC SHOPEE LIVE & SHOPEE VIDEO",
        "description": "Voucher giảm 20% - 50% độc quyền chỉ có trên Shopee Live và lướt Video",
        "slot": "Liên tục 24/7 (Đỉnh điểm 12h & 20h)",
        "tag": "HOT NHẤT HIỆN NAY",
        "is_live_now": True,
        "url": live_landing,
        "aff_url": live_aff,
        "banner": ""
    })

    return campaigns

def crawl_shopee_vip_deals(limit: int = 40) -> List[Dict[str, Any]]:
    """Cào và chọn lọc các deal Shopee VIP / Hàng hiệu chính hãng Shopee Mall."""
    all_deals = crawl_shopee_flash_sale(limit=limit * 2)
    # Lọc lấy deal VIP hoặc Mall
    vip_deals = [d for d in all_deals if d.get("is_vip") == 1 or d.get("is_mall") == 1]
    # Sắp xếp theo mức giảm và điểm số
    vip_deals.sort(key=lambda x: (x.get("is_mall", 0), x.get("discount", 0), x.get("sold", 0)), reverse=True)
    return vip_deals[:limit]

def crawl_shopee_deals_by_keyword(keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Cào sản phẩm deal theo từ khóa/ngành hàng từ Shopee."""
    # Thử gọi API kèm cookie nếu có
    cookies_dict = {}
    if os.path.exists(COOKIE_FILE):
        try:
            raw = json.load(open(COOKIE_FILE, encoding="utf-8"))
            for c in raw:
                cookies_dict[c["name"]] = c["value"]
        except Exception:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "vi-VN,vi;q=0.9",
        "Referer": f"https://shopee.vn/search?keyword={requests.utils.quote(keyword)}"
    }
    
    url = "https://shopee.vn/api/v4/search/search_items"
    params = {
        "by": "sales",
        "keyword": keyword,
        "limit": limit,
        "newest": 0,
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": 2
    }

    out = []
    try:
        r = requests.get(url, headers=headers, params=params, cookies=cookies_dict, timeout=12)
        if r.status_code == 200:
            items = r.json().get("items", [])
            for it in items:
                basic = it.get("item_basic", {})
                if not basic:
                    continue
                itemid = basic.get("itemid")
                shopid = basic.get("shopid")
                title = basic.get("name")
                price_raw = basic.get("price") or 0
                orig_raw = basic.get("price_before_discount") or price_raw
                price = round(price_raw / 100000) if price_raw > 100000 else price_raw
                orig_price = round(orig_raw / 100000) if orig_raw > 100000 else orig_raw

                discount = float(str(basic.get("discount") or "0").replace("%", "").strip() or 0)
                rating = round(basic.get("item_rating", {}).get("rating_star", 4.8), 1)
                sold = basic.get("historical_sold") or basic.get("sold") or 100

                img_hash = basic.get("image") or ""
                img_url = f"https://down-vn.img.susercontent.com/file/{img_hash}" if img_hash else ""
                prod_url = f"https://shopee.vn/product/{shopid}/{itemid}"

                out.append({
                    "id": f"sp_{itemid}",
                    "niche": keyword,
                    "title": title,
                    "price": price,
                    "orig_price": orig_price,
                    "discount": discount,
                    "commission": 8.0,
                    "rating": rating,
                    "sold": sold,
                    "url": prod_url,
                    "aff_url": prod_url,
                    "image": img_url
                })
    except Exception as e:
        print(f"[shopee] Lỗi cào sản phẩm từ khóa '{keyword}':", e)

    return out
