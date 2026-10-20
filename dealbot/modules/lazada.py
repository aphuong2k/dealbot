"""Module quản lý Lazada Engine & Lazada Hunter:
1. Lưu & kiểm tra Cookie Lazada (từ Cookie-Editor hoặc Header)
2. Tìm kiếm sản phẩm trên Lazada (hỗ trợ lọc LazMall / Tmall: service=mall)
3. Trích xuất chi tiết từng phân loại (Variations/SKUs) và giá thực tế
"""
import os, sys, time, json, re, urllib.parse, subprocess
from typing import List, Dict, Any, Optional
import requests

if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

COOKIE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies", "lazada.json")

def remove_accents(input_str: str) -> str:
    """Loại bỏ dấu tiếng Việt để URL tìm kiếm Lazada không bị WAF kích hoạt trang punish."""
    if not input_str:
        return ""
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def parse_lazada_cookie_input(raw_text: str) -> List[Dict[str, Any]]:
    """Phân tích cookie dán từ Cookie-Editor (JSON) hoặc chuỗi Header (name=value; ...)."""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Dữ liệu cookie Lazada trống.")

    # 1. Parse JSON từ Cookie-Editor
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
                            "domain": str(item.get("domain", ".lazada.vn")).strip(),
                            "path": str(item.get("path", "/")).strip(),
                            "secure": bool(item.get("secure", True)),
                            "sameSite": item.get("sameSite", "no_restriction")
                        })
                if cleaned:
                    return cleaned
        except json.JSONDecodeError:
            pass

    # 2. Parse dạng chuỗi Header (lzd_sid=...; user_id=...)
    items = []
    for part in raw_text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        items.append({
            "name": k.strip(),
            "value": v.strip(),
            "domain": ".lazada.vn",
            "path": "/",
            "secure": True,
            "sameSite": "no_restriction"
        })

    if items:
        return items

    raise ValueError("Không nhận diện được định dạng Cookie Lazada. Vui lòng dán mảng JSON hoặc chuỗi 'name=value;...'")

def get_lazada_cookie_info() -> Dict[str, Any]:
    """Lấy thông tin file cookie Lazada hiện tại."""
    info = {
        "exists": False,
        "count": 0,
        "user_name": None,
        "updated_at": None,
        "size_bytes": 0,
        "is_valid": False,
        "raw_preview": ""
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
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        val = item.get("value", "")
                        if name in ("user_name", "nick", "lzd_user_name"):
                            info["user_name"] = urllib.parse.unquote(str(val))
                        if name in ("lzd_sid", "t_s", "_tb_token_"):
                            info["is_valid"] = True
                
                # Tạo đoạn preview ngắn
                preview_items = [f"{c.get('name')}={c.get('value')[:15]}..." for c in data[:5] if isinstance(c, dict)]
                info["raw_preview"] = "; ".join(preview_items)
        except Exception as e:
            info["raw_preview"] = f"Lỗi đọc file cookie: {e}"

    return info

def save_lazada_cookie(raw_cookie: str) -> Dict[str, Any]:
    """Lưu cookie Lazada vào file."""
    cookies_list = parse_lazada_cookie_input(raw_cookie)
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, indent=2, ensure_ascii=False)
    return get_lazada_cookie_info()

def get_lazada_cookies_dict() -> Dict[str, str]:
    """Chuyển đổi cookies sang dict name: value cho requests."""
    if not os.path.exists(COOKIE_FILE):
        return {}
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {item["name"]: item["value"] for item in data if isinstance(item, dict) and "name" in item and "value" in item}
    except Exception:
        pass
    return {}

def test_lazada_cookie_connection() -> Dict[str, Any]:
    """Kiểm tra kết nối tới Lazada và trạng thái cookie."""
    cookies = get_lazada_cookies_dict()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.lazada.vn/"
    }
    
    try:
        # Test gọi trang chủ Lazada
        r = requests.get("https://www.lazada.vn/", headers=headers, cookies=cookies, timeout=10)
        has_login = False
        user_nick = None
        for k, v in cookies.items():
            if k in ("user_name", "nick", "lzd_user_name"):
                user_nick = urllib.parse.unquote(v)
                has_login = True
                break

        return {
            "success": r.status_code == 200,
            "status_code": r.status_code,
            "has_cookie": len(cookies) > 0,
            "user_nick": user_nick or ("Đã nạp cookie" if len(cookies) > 0 else "Chưa có cookie"),
            "message": "Kết nối Lazada thành công." if r.status_code == 200 else f"Lazada phản hồi mã HTTP {r.status_code}"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "has_cookie": len(cookies) > 0,
            "user_nick": None,
            "message": f"Không thể kết nối đến Lazada: {e}"
        }

def search_lazada_products(keyword: str, filter_mall_only: bool = True, limit: int = 40) -> List[Dict[str, Any]]:
    """Tìm kiếm sản phẩm trên Lazada (ưu tiên qua tiến trình subprocess độc lập để tránh xung đột event loop FastAPI/Playwright)."""
    # 1. Luôn chạy qua tiến trình độc lập (an toàn tuyệt đối với asyncio / Windows)
    items = search_lazada_products_isolated(keyword, filter_mall_only, limit)
    if items is not None:
        return items

    # 2. Fallback HTTP nếu subprocess gặp sự cố
    return _search_lazada_http(keyword, filter_mall_only, limit)

def search_lazada_products_isolated(keyword: str, filter_mall_only: bool = True, limit: int = 40) -> Optional[List[Dict[str, Any]]]:
    """Chạy tìm kiếm Lazada trong một subprocess Python riêng biệt, trả về kết quả JSON."""
    script_path = os.path.abspath(__file__)
    cmd = [sys.executable, script_path, "search", keyword, "--limit", str(limit)]
    if filter_mall_only:
        cmd.append("--mall-only")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=BASE_DIR, timeout=75)
        stdout_txt = proc.stdout.strip()
        if stdout_txt:
            try:
                if "[" in stdout_txt and "]" in stdout_txt:
                    s_idx = stdout_txt.find("[")
                    e_idx = stdout_txt.rfind("]") + 1
                    data = json.loads(stdout_txt[s_idx:e_idx])
                    if isinstance(data, list):
                        return data
                data = json.loads(stdout_txt)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        if proc.returncode == 0:
            return []
    except Exception as e:
        print(f"[lazada_isolated] Lỗi subprocess: {e}")

    return None

def _search_lazada_playwright(keyword: str, filter_mall_only: bool = True, limit: int = 40) -> List[Dict[str, Any]]:
    """Cào sản phẩm Lazada bằng Playwright headless để vượt WAF/anti-bot và lấy đầy đủ SKUs."""
    if sys.platform == "win32":
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    from playwright.sync_api import sync_playwright
    
    # URL tìm kiếm Lazada, nếu lọc LazMall thì thêm service=mall
    # Luôn loại bỏ dấu tiếng Việt để tránh bị hệ thống bảo mật Lazada kích hoạt trang punish
    clean_kw = remove_accents(keyword).strip()
    query_enc = urllib.parse.quote(clean_kw)
    url = f"https://www.lazada.vn/catalog/?q={query_enc}"
    if filter_mall_only:
        url += "&service=mall"

    results = []
    
    # Chuẩn bị cookie
    pw_cookies = []
    if os.path.exists(COOKIE_FILE):
        try:
            raw = json.load(open(COOKIE_FILE, encoding="utf-8"))
            for c in raw:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    pw_cookies.append({
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".lazada.vn"),
                        "path": c.get("path", "/"),
                        "secure": True
                    })
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="vi-VN"
        )
        # Bổ sung script stealth để bypass chống bot
        try:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)
        except Exception:
            pass

        if pw_cookies:
            try:
                context.add_cookies(pw_cookies)
            except Exception as e:
                print(f"[lazada] add_cookies error: {e}")

        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            # Cuộn trang nhiều lần để kích hoạt Lazy Loading nạp sâu đầy đủ 30 - 40 sản phẩm
            try:
                page.evaluate("""async () => {
                    for (let i = 0; i < 4; i++) {
                        window.scrollBy(0, 1000);
                        await new Promise(r => setTimeout(r, 400));
                    }
                }""")
                page.wait_for_timeout(1000)
            except Exception:
                pass

            # 1. Thử lấy data từ biến toàn cục window.pageData mà Lazada nhúng sẵn vào trang catalog
            page_data = page.evaluate("""() => {
                if (window.pageData && window.pageData.mods && window.pageData.mods.listItems) {
                    return window.pageData.mods.listItems;
                }
                return null;
            }""")

            if page_data and isinstance(page_data, list) and len(page_data) > 0:
                for raw_item in page_data:
                    item_id = str(raw_item.get("itemId") or "")
                    sku_id = str(raw_item.get("skuId") or "")
                    title = raw_item.get("name") or raw_item.get("title") or ""
                    seller_name = raw_item.get("sellerName") or ""
                    
                    is_mall = bool(raw_item.get("isLazMall") or raw_item.get("isMall") or "mall" in str(raw_item.get("icons", "")).lower())
                    if filter_mall_only and not is_mall:
                        continue

                    price_show = raw_item.get("priceShow") or raw_item.get("price") or 0
                    price_val = 0.0
                    try:
                        price_val = float(str(price_show).replace("₫", "").replace(".", "").replace(",", "").strip())
                    except Exception:
                        pass

                    orig_price_val = 0.0
                    if raw_item.get("originalPrice"):
                        try:
                            orig_price_val = float(str(raw_item.get("originalPrice")).replace("₫", "").replace(".", "").replace(",", "").strip())
                        except Exception:
                            pass

                    item_url = raw_item.get("itemUrl") or ""
                    if item_url and not item_url.startswith("http"):
                        item_url = "https:" + item_url

                    image_url = raw_item.get("image") or ""
                    if image_url and not image_url.startswith("http"):
                        image_url = "https:" + image_url

                    variations = []
                    sku_list = raw_item.get("skuList") or raw_item.get("skus") or []
                    if sku_list and isinstance(sku_list, list):
                        for s in sku_list:
                            var_name = s.get("name") or s.get("propValue") or "Mặc định"
                            s_price = s.get("price") or price_val
                            try:
                                s_price_val = float(str(s_price).replace("₫", "").replace(".", "").replace(",", "").strip())
                            except Exception:
                                s_price_val = price_val
                            variations.append({
                                "sku_id": str(s.get("skuId") or sku_id),
                                "name": var_name,
                                "price": s_price_val
                            })
                    else:
                        variations.append({
                            "sku_id": sku_id or item_id,
                            "name": "Tiêu chuẩn / Mặc định",
                            "price": price_val
                        })

                    results.append({
                        "item_id": item_id,
                        "sku_id": sku_id,
                        "title": title,
                        "seller_name": seller_name,
                        "is_mall": is_mall,
                        "price": price_val,
                        "orig_price": orig_price_val,
                        "product_url": item_url,
                        "image_url": image_url,
                        "variations": variations
                    })
                    if len(results) >= limit:
                        break
            else:
                # 2. DOM Fallback: Cào trực tiếp từ các thẻ card sản phẩm trên DOM (đặc biệt khi bị redirect sang /tag/...)
                dom_items = page.evaluate("""() => {
                    const list = [];
                    const cards = document.querySelectorAll('div[data-qa-locator="product-item"], div.Bm3ON');
                    cards.forEach(card => {
                        const aEl = card.querySelector('div.RfADt a') || card.querySelector('a[title]') || card.querySelector('a[href*="-i"]');
                        const title = aEl ? (aEl.getAttribute('title') || aEl.innerText.trim()) : '';
                        const href = aEl ? aEl.getAttribute('href') : '';
                        
                        const imgEl = card.querySelector('div._95X4G img') || card.querySelector('img');
                        const img = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';
                        
                        const priceEl = card.querySelector('span.ooOxS') || card.querySelector('span.aBrP0') || card.querySelector('div.aBrP0 span');
                        const price = priceEl ? priceEl.innerText.trim() : '';

                        const origPriceEl = card.querySelector('del.WNo53') || card.querySelector('del');
                        const origPrice = origPriceEl ? origPriceEl.innerText.trim() : '';

                        const sellerEl = card.querySelector('span.WavNE') || card.querySelector('span._1c2Gx') || card.querySelector('span.m4a4o');
                        const seller = sellerEl ? sellerEl.innerText.trim() : '';

                        const isMall = !!(
                            card.querySelector('i.ic-dynamic-badge-lazmall') || 
                            card.querySelector('img[src*="lazmall"]') || 
                            card.querySelector('.lazmall') ||
                            card.innerText.toLowerCase().includes('lazmall') ||
                            card.innerText.toLowerCase().includes('mall') ||
                            window.location.href.includes('service=mall')
                        );

                        // Bóc tách phân loại swatches nếu có trên card
                        const swatchImgs = Array.from(card.querySelectorAll('div.qmXQo img, div.Ms6aG img, div.g63b9 img, .sku-wrap img'));
                        const swatches = [];
                        swatchImgs.forEach(s => {
                            const sName = s.getAttribute('title') || s.getAttribute('alt') || '';
                            if (sName && !swatches.includes(sName)) {
                                swatches.push(sName);
                            }
                        });

                        if (title && price) {
                            list.push({ title, href, img, price, origPrice, seller, isMall, swatches });
                        }
                    });
                    return list;
                }""")

                for raw_d in dom_items:
                    is_mall_item = bool(raw_d.get("isMall", False))
                    if filter_mall_only and not is_mall_item:
                        continue

                    price_str = raw_d.get("price") or ""
                    clean_pr = re.sub(r'[^\d]', '', price_str)
                    price_val = float(clean_pr) if clean_pr else 0.0

                    orig_pr_str = raw_d.get("origPrice") or ""
                    clean_orig = re.sub(r'[^\d]', '', orig_pr_str)
                    orig_val = float(clean_orig) if clean_orig else 0.0

                    item_url = raw_d.get("href") or ""
                    if item_url.startswith("//"):
                        item_url = "https:" + item_url
                    elif item_url and not item_url.startswith("http"):
                        item_url = "https://www.lazada.vn" + item_url

                    img_url = raw_d.get("img") or ""
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url

                    item_id_m = re.search(r'-i(\d+)', item_url)
                    item_id = item_id_m.group(1) if item_id_m else str(int(time.time()*1000))

                    variations = []
                    swatches = raw_d.get("swatches") or []
                    if swatches:
                        for idx, s_name in enumerate(swatches):
                            variations.append({
                                "sku_id": f"{item_id}_{idx}",
                                "name": s_name,
                                "price": price_val
                            })
                    else:
                        variations.append({
                            "sku_id": item_id,
                            "name": "Tiêu chuẩn / Mặc định",
                            "price": price_val
                        })

                    results.append({
                        "item_id": item_id,
                        "sku_id": item_id,
                        "title": raw_d.get("title", ""),
                        "seller_name": raw_d.get("seller", "") or "Lazada Seller",
                        "is_mall": is_mall_item,
                        "price": price_val,
                        "orig_price": orig_val,
                        "product_url": item_url,
                        "image_url": img_url,
                        "variations": variations
                    })
                    if len(results) >= limit:
                        break
        finally:
            browser.close()

    return results

def _search_lazada_http(keyword: str, filter_mall_only: bool = True, limit: int = 40) -> List[Dict[str, Any]]:
    """Fallback cào bằng HTTP GET và Regex parse window.pageData."""
    cookies = get_lazada_cookies_dict()
    clean_kw = remove_accents(keyword).strip()
    query_enc = urllib.parse.quote(clean_kw)
    url = f"https://www.lazada.vn/catalog/?q={query_enc}"
    if filter_mall_only:
        url += "&service=mall"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.lazada.vn/"
    }

    results = []
    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        if r.status_code != 200:
            return []

        # Tìm chuỗi window.pageData = {...}
        m = re.search(r"window\.pageData\s*=\s*(\{.*?\});", r.text, re.DOTALL)
        if not m:
            m = re.search(r"pageData\s*=\s*(\{.*?\});", r.text, re.DOTALL)

        if m:
            data = json.loads(m.group(1))
            items = data.get("mods", {}).get("listItems", [])
            for raw_item in items[:limit]:
                item_id = str(raw_item.get("itemId") or "")
                sku_id = str(raw_item.get("skuId") or "")
                title = raw_item.get("name") or raw_item.get("title") or ""
                seller_name = raw_item.get("sellerName") or ""
                
                is_mall = bool(raw_item.get("isLazMall") or raw_item.get("isMall") or filter_mall_only)

                price_show = raw_item.get("priceShow") or raw_item.get("price") or 0
                price_val = 0.0
                try:
                    price_val = float(str(price_show).replace("₫", "").replace(".", "").replace(",", "").strip())
                except Exception:
                    pass

                item_url = raw_item.get("itemUrl") or ""
                if item_url and not item_url.startswith("http"):
                    item_url = "https:" + item_url

                image_url = raw_item.get("image") or ""
                if image_url and not image_url.startswith("http"):
                    image_url = "https:" + image_url

                results.append({
                    "item_id": item_id,
                    "sku_id": sku_id,
                    "title": title,
                    "seller_name": seller_name,
                    "is_mall": is_mall,
                    "price": price_val,
                    "orig_price": 0.0,
                    "product_url": item_url,
                    "image_url": image_url,
                    "variations": [{
                        "sku_id": sku_id or item_id,
                        "name": "Tiêu chuẩn / Mặc định",
                        "price": price_val
                    }]
                })
    except Exception as e:
        print(f"[lazada_http] Lỗi search: {e}")

    return results

def get_lazada_product_detail_variations(product_url: str) -> List[Dict[str, Any]]:
    """Cào chi tiết phân loại (Color, Size, Version) và giá từng phân loại trong trang sản phẩm Lazada."""
    # Trang chi tiết Lazada có các SKU nằm trong window.__moduleData__ hoặc app.data
    # Thường khi check nhanh, các phân loại đã được bóc tách từ catalog.
    # Hàm này dùng để đào sâu từng sản phẩm khi cần đối soát phân loại chi tiết.
    cookies = get_lazada_cookies_dict()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.lazada.vn/"
    }
    variations = []
    try:
        r = requests.get(product_url, headers=headers, cookies=cookies, timeout=12)
        if r.status_code == 200:
            # Tìm mảng skuGalleries hoặc skuBase
            m = re.search(r'"skuGalleries"\s*:\s*(\{.*?\})', r.text)
            if m:
                pass
            # Tìm patterns các phân loại và giá
            skus_m = re.findall(r'"skuId"\s*:\s*"(\d+)".*?"price"\s*:\s*\{.*?"value"\s*:\s*([\d.]+)', r.text)
            for sku_id, prc in skus_m:
                variations.append({
                    "sku_id": sku_id,
                    "name": f"Phân loại #{sku_id[-4:]}",
                    "price": float(prc)
                })
    except Exception:
        pass
    return variations

def clean_shop_slug(shop_url_or_slug: str) -> str:
    """Chuẩn hóa đường dẫn hoặc slug của shop về dạng slug thuần (vd: bear-electric-appliances)."""
    if not shop_url_or_slug:
        return ""
    slug = shop_url_or_slug.strip()
    if "/" in slug:
        slug = slug.split("?")[0].rstrip("/").split("/")[-1]
    return slug

def scrape_shop_all_products(shop_url_or_slug: str, max_pages: int = 1, limit_per_page: int = 40) -> List[Dict[str, Any]]:
    """Cào toàn bộ danh sách sản phẩm từ gian hàng Tmall/Lazada thông qua URL All-Products của shop."""
    slug = clean_shop_slug(shop_url_or_slug)
    if not slug:
        return []

    # Thử qua isolated subprocess để tránh xung đột event loop FastAPI/Playwright
    res = scrape_shop_all_products_isolated(slug, max_pages)
    if res is not None:
        return res

    return _scrape_shop_all_products_playwright(slug, max_pages, limit_per_page)

def scrape_shop_all_products_isolated(shop_slug: str, max_pages: int = 1) -> Optional[List[Dict[str, Any]]]:
    """Chạy cào sản phẩm shop trong tiến trình subprocess Python độc lập."""
    script_path = os.path.abspath(__file__)
    cmd = [sys.executable, script_path, "shop_products", shop_slug, "--pages", str(max_pages)]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=BASE_DIR, timeout=60 * max_pages)
        stdout_txt = proc.stdout.strip()
        if stdout_txt:
            try:
                if "[" in stdout_txt and "]" in stdout_txt:
                    s_idx = stdout_txt.find("[")
                    e_idx = stdout_txt.rfind("]") + 1
                    data = json.loads(stdout_txt[s_idx:e_idx])
                    if isinstance(data, list):
                        return data
                data = json.loads(stdout_txt)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        if proc.returncode == 0:
            return []
    except Exception as e:
        print(f"[lazada_shop_isolated] Lỗi subprocess shop '{shop_slug}': {e}")

    return None

def _scrape_shop_all_products_playwright(shop_slug: str, max_pages: int = 1, limit_per_page: int = 40) -> List[Dict[str, Any]]:
    """Cào sản phẩm gian hàng bằng Playwright headless."""
    if sys.platform == "win32":
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    from playwright.sync_api import sync_playwright

    pw_cookies = []
    if os.path.exists(COOKIE_FILE):
        try:
            raw = json.load(open(COOKIE_FILE, encoding="utf-8"))
            for c in raw:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    pw_cookies.append({
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".lazada.vn"),
                        "path": c.get("path", "/"),
                        "secure": True
                    })
        except Exception:
            pass

    all_products = []
    seen_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="vi-VN"
        )
        try:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)
        except Exception:
            pass

        if pw_cookies:
            try:
                context.add_cookies(pw_cookies)
            except Exception:
                pass

        page = context.new_page()

        for page_num in range(1, max_pages + 1):
            catalog_url = f"https://www.lazada.vn/{shop_slug}/?q=All-Products&from=wangpu&page={page_num}"
            try:
                page.goto(catalog_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2000)

                # Cuộn trang để nạp lazy loading
                try:
                    page.evaluate("""async () => {
                        for (let i = 0; i < 3; i++) {
                            window.scrollBy(0, 1000);
                            await new Promise(r => setTimeout(r, 300));
                        }
                    }""")
                    page.wait_for_timeout(800)
                except Exception:
                    pass

                items = page.evaluate("""() => {
                    const list = [];
                    const cards = document.querySelectorAll('div[data-qa-locator="product-item"], div.Bm3ON');
                    cards.forEach(card => {
                        const aEl = card.querySelector('div.RfADt a') || card.querySelector('a[title]') || card.querySelector('a[href*="-i"]');
                        const title = aEl ? (aEl.getAttribute('title') || aEl.innerText.trim()) : '';
                        const href = aEl ? aEl.getAttribute('href') : '';

                        const imgEl = card.querySelector('div._95X4G img') || card.querySelector('img');
                        const img = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';

                        const priceEl = card.querySelector('span.ooOxS') || card.querySelector('span.aBrP0') || card.querySelector('div.aBrP0 span');
                        const price = priceEl ? priceEl.innerText.trim() : '';

                        const origPriceEl = card.querySelector('del.WNo53') || card.querySelector('del');
                        const origPrice = origPriceEl ? origPriceEl.innerText.trim() : '';

                        const sellerEl = card.querySelector('span.WavNE') || card.querySelector('span._1c2Gx') || card.querySelector('span.m4a4o');
                        const seller = sellerEl ? sellerEl.innerText.trim() : '';

                        if (title && price) {
                            list.push({ title, href, img, price, origPrice, seller });
                        }
                    });
                    return list;
                }""")

                if not items:
                    break

                for raw_d in items:
                    title = raw_d.get("title") or ""
                    price_str = raw_d.get("price") or ""
                    clean_pr = re.sub(r'[^\d]', '', price_str)
                    price_val = float(clean_pr) if clean_pr else 0.0

                    orig_pr_str = raw_d.get("origPrice") or ""
                    clean_orig = re.sub(r'[^\d]', '', orig_pr_str)
                    orig_val = float(clean_orig) if clean_orig else 0.0

                    item_url = raw_d.get("href") or ""
                    if item_url.startswith("//"):
                        item_url = "https:" + item_url
                    elif item_url and not item_url.startswith("http"):
                        item_url = "https://www.lazada.vn" + item_url

                    img_url = raw_d.get("img") or ""
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url

                    item_id_m = re.search(r'-i(\d+)', item_url)
                    item_id = item_id_m.group(1) if item_id_m else item_url

                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)

                    all_products.append({
                        "item_id": item_id,
                        "sku_id": item_id,
                        "title": title,
                        "seller_name": raw_d.get("seller") or shop_slug,
                        "is_mall": True,
                        "price": price_val,
                        "orig_price": orig_val,
                        "product_url": item_url,
                        "image_url": img_url,
                        "variations": [{
                            "sku_id": item_id,
                            "name": "Mặc định",
                            "price": price_val
                        }]
                    })

                    if len(all_products) >= limit_per_page * max_pages:
                        break

            except Exception as page_err:
                print(f"[lazada_shop] Lỗi trang {page_num} shop '{shop_slug}': {page_err}")
                break

        browser.close()

    return all_products

def sync_tmall_brand_directory_live() -> Dict[str, Any]:
    """Cào trực tiếp cây danh mục Brand Tmall và toàn bộ gian hàng từ trang Brand Directory của Lazada."""
    tmall_brand_url = (
        "https://pages.lazada.vn/wow/gcp/route/lazada/vn/upr_1000345_lazada/channel/vn/upr-router/vn"
        "?spm=a2o4n.tm80416675.9881331290.dList-Brand&hybrid=1&data_prefetch=true&prefetch_replace=1"
        "&at_iframe=1&wh_pid=/lazada/channel/vn/LazMallOne-Campaign/tmall-brand-directory&pha=true&trafficSource=cp"
    )

    seed_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tmall_brands_seed.json")

    if sys.platform == "win32":
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                locale="vi-VN"
            )
            page = context.new_page()
            page.goto(tmall_brand_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Lấy data nhúng trong window.__FIRST_SCREEN_DATA
            raw_data = page.evaluate("""() => {
                if (window.__FIRST_SCREEN_DATA && window.__FIRST_SCREEN_DATA.data) {
                    const d = window.__FIRST_SCREEN_DATA.data;
                    for (const k of Object.keys(d)) {
                        if (d[k] && (d[k].categories || d[k].subCategories)) {
                            return d[k];
                        }
                    }
                }
                return null;
            }""")
            browser.close()

            if raw_data:
                categories = raw_data.get("categories", [])
                sub_cats = raw_data.get("subCategories", [])
                banners = raw_data.get("categoryBanners", [])

                cat_dict = {}
                for c in categories:
                    cid = str(c.get("id"))
                    name = c.get("name")
                    cat_dict[cid] = {
                        "id": cid,
                        "name": name,
                        "webUrl": c.get("webUrl"),
                        "shops": []
                    }

                seen = set()
                for item in (sub_cats + banners):
                    cid = str(item.get("categoryId"))
                    name = item.get("name")
                    web_url = item.get("webUrl")
                    img = item.get("imageSrc")
                    if cid in cat_dict and name and web_url:
                        key = (cid, web_url)
                        if key not in seen:
                            seen.add(key)
                            cat_dict[cid]["shops"].append({
                                "name": name,
                                "url": web_url,
                                "img": img
                            })

                result = {
                    "total_categories": len(cat_dict),
                    "summary": [
                        {
                            "id": c["id"],
                            "name": c["name"],
                            "shop_count": len(c["shops"]),
                            "sample_shops": [s["name"] for s in c["shops"][:5]]
                        }
                        for c in cat_dict.values()
                    ],
                    "full_data": cat_dict
                }

                # Lưu cache seed file
                os.makedirs(os.path.dirname(seed_file), exist_ok=True)
                with open(seed_file, "w", encoding="utf-8") as sf:
                    json.dump(result, sf, indent=2, ensure_ascii=False)

                return result

    except Exception as e:
        print(f"[lazada_tmall_sync] Lỗi cào live, sử dụng seed cache: {e}")

    # Fallback to local seed file
    if os.path.exists(seed_file):
        with open(seed_file, "r", encoding="utf-8") as sf:
            return json.load(sf)

    return {"total_categories": 0, "summary": [], "full_data": {}}

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["search", "test", "shop_products", "sync_brands"])
    parser.add_argument("keyword", nargs="?", default="")
    parser.add_argument("--mall-only", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args()

    if args.action == "search":
        items = _search_lazada_playwright(args.keyword, filter_mall_only=args.mall_only, limit=args.limit)
        print(json.dumps(items, ensure_ascii=False))
    elif args.action == "shop_products":
        items = _scrape_shop_all_products_playwright(args.keyword, max_pages=args.pages, limit_per_page=args.limit)
        print(json.dumps(items, ensure_ascii=False))
    elif args.action == "sync_brands":
        res = sync_tmall_brand_directory_live()
        print(json.dumps(res, ensure_ascii=False))

