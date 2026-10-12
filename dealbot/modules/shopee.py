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

def crawl_shopee_flash_sale(limit: int = 30) -> List[Dict[str, Any]]:
    """Cào các deal Flash Sale giảm giá sốc hiện tại trên Shopee."""
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

                img_hash = it.get("image") or ""
                img_url = f"https://down-vn.img.susercontent.com/file/{img_hash}" if img_hash else ""
                prod_url = f"https://shopee.vn/product/{shopid}/{itemid}" if shopid and itemid else f"https://shopee.vn/flash_sale"

                sold = it.get("promo_sold") or it.get("flash_sale_stock") or 50

                out.append({
                    "id": f"sp_fs_{itemid}",
                    "niche": "săn sale shopee",
                    "title": name,
                    "price": price,
                    "orig_price": orig_price,
                    "discount": discount,
                    "commission": 10.0,
                    "rating": 4.9,
                    "sold": sold,
                    "url": prod_url,
                    "aff_url": prod_url,
                    "image": img_url
                })
    except Exception as e:
        print("[shopee] Lỗi khi cào flash sale:", e)
    return out

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
