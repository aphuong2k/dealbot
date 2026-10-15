"""Module chuyển đổi link sản phẩm Shopee sang Shortlink Shopee Affiliate (https://s.shopee.vn/...)
Hỗ trợ 2 phương thức:
1. Shopee Affiliate Open API (dùng App ID & Secret Key từ https://affiliate.shopee.vn/open_api)
2. Shopee Universal Affiliate Tracking (gắn trực tiếp Publisher ID và Sub-ID lấy tự động từ Cookie portal)
"""
import os, sys, time, json, re, requests, hmac, hashlib
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL_COOKIE_FILE = os.path.join(BASE_DIR, "cookies", "shopee_aff_portal.json")
FALLBACK_COOKIE_FILE = os.path.join(BASE_DIR, "cookies", "shopee_aff.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.yaml")

_CACHED_PROFILE: Optional[Dict[str, Any]] = None
_CACHED_PROFILE_TIME: float = 0.0

def parse_cookie_input(raw_text: str) -> List[Dict[str, Any]]:
    """Phân tích cookie dán từ Cookie-Editor (JSON) hoặc chuỗi Header."""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Dữ liệu cookie trống.")

    # 1. Mảng JSON từ Cookie-Editor
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

    # 2. Chuỗi Header (SPC_EC=...; SPC_U=...)
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

    raise ValueError("Không nhận diện được định dạng Cookie. Vui lòng dán JSON từ Cookie-Editor hoặc chuỗi 'name=value; ...'")

def fetch_affiliate_profile(force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Lấy thông tin tài khoản Affiliate từ https://affiliate.shopee.vn/api/v3/user/profile."""
    global _CACHED_PROFILE, _CACHED_PROFILE_TIME
    now = time.time()
    if not force_refresh and _CACHED_PROFILE and (now - _CACHED_PROFILE_TIME < 600):
        return _CACHED_PROFILE

    target_file = PORTAL_COOKIE_FILE if os.path.exists(PORTAL_COOKIE_FILE) else FALLBACK_COOKIE_FILE
    if not os.path.exists(target_file):
        return None

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            cookie_list = json.load(f)
        cookies = {c["name"]: c["value"] for c in cookie_list if isinstance(c, dict) and "name" in c and "value" in c}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://affiliate.shopee.vn/"
        }
        r = requests.get("https://affiliate.shopee.vn/api/v3/user/profile", headers=headers, cookies=cookies, timeout=8)
        if r.status_code == 200:
            res = r.json()
            if res.get("code") == 0 and res.get("data"):
                data = res["data"]
                _CACHED_PROFILE = data
                _CACHED_PROFILE_TIME = now
                return data
    except Exception as e:
        print(f"[ShopeeAff] Lỗi đọc profile cổng affiliate: {e}")

    return None

def get_portal_cookie_info() -> Dict[str, Any]:
    """Kiểm tra trạng thái Cookie Shopee Affiliate Portal (affiliate.shopee.vn)."""
    target_file = PORTAL_COOKIE_FILE if os.path.exists(PORTAL_COOKIE_FILE) else FALLBACK_COOKIE_FILE
    info = {
        "exists": False,
        "file_name": os.path.basename(target_file),
        "count": 0,
        "spc_u": None,
        "affiliate_id": None,
        "affiliate_name": None,
        "email": None,
        "has_spc_ec": False,
        "has_aff_session": False,
        "updated_at": None,
        "size_bytes": 0,
        "raw_content": ""
    }

    if os.path.exists(target_file):
        info["exists"] = True
        info["size_bytes"] = os.path.getsize(target_file)
        info["updated_at"] = int(os.path.getmtime(target_file))
        try:
            with open(target_file, "r", encoding="utf-8") as f:
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
                        elif any(k in name.upper() for k in ("AFF", "JWT", "SPC_A_T", "SPC_SI")):
                            info["has_aff_session"] = True
        except Exception as e:
            info["raw_content"] = f"Lỗi đọc file: {e}"

        # Lấy thông tin Affiliate ID thật từ portal
        profile = fetch_affiliate_profile()
        if profile:
            info["affiliate_id"] = str(profile.get("affiliate_id") or "")
            info["affiliate_name"] = str(profile.get("nick_name") or profile.get("name") or "")
            info["email"] = str(profile.get("email") or "")
            if not info["spc_u"] and profile.get("user_id"):
                info["spc_u"] = str(profile.get("user_id"))

    return info

def save_portal_cookie(raw_cookie: str) -> Dict[str, Any]:
    """Lưu cookie cổng affiliate.shopee.vn vào file."""
    global _CACHED_PROFILE
    _CACHED_PROFILE = None
    cookies_list = parse_cookie_input(raw_cookie)
    os.makedirs(os.path.dirname(PORTAL_COOKIE_FILE), exist_ok=True)
    with open(PORTAL_COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, indent=2, ensure_ascii=False)

    info = get_portal_cookie_info()
    msg = f"Đã lưu thành công {info['count']} cookies Shopee Affiliate Portal!"
    if info.get("affiliate_id"):
        msg += f" (Publisher ID: {info['affiliate_id']})"
    elif info.get("spc_u"):
        msg += f" (User ID: {info['spc_u']})"
    return {"message": msg, "info": info}

def delete_portal_cookie() -> Dict[str, Any]:
    """Xóa file cookie cổng affiliate."""
    global _CACHED_PROFILE
    _CACHED_PROFILE = None
    if os.path.exists(PORTAL_COOKIE_FILE):
        os.remove(PORTAL_COOKIE_FILE)
        return {"message": "Đã xóa file cookie Shopee Affiliate Portal thành công."}
    return {"message": "File cookie không tồn tại."}

def get_open_api_config() -> Dict[str, str]:
    """Lấy cấu hình Shopee Open API từ config.yaml hoặc biến môi trường."""
    app_id = os.getenv("SHOPEE_AFF_APP_ID", "")
    secret = os.getenv("SHOPEE_AFF_SECRET", "")
    
    if os.path.exists(CONFIG_FILE):
        try:
            import yaml
            cfg = yaml.safe_load(open(CONFIG_FILE, encoding="utf-8")) or {}
            aff_cfg = cfg.get("shopee_affiliate", {})
            if isinstance(aff_cfg, dict):
                app_id = aff_cfg.get("app_id", app_id) or ""
                secret = aff_cfg.get("secret", secret) or ""
        except Exception:
            pass

    return {"app_id": str(app_id).strip(), "secret": str(secret).strip()}

def save_open_api_config(app_id: str, secret: str) -> Dict[str, Any]:
    """Lưu App ID và Secret Key vào config.yaml."""
    import yaml
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            cfg = yaml.safe_load(open(CONFIG_FILE, encoding="utf-8")) or {}
        except Exception:
            cfg = {}

    if "shopee_affiliate" not in cfg or not isinstance(cfg["shopee_affiliate"], dict):
        cfg["shopee_affiliate"] = {}
    
    cfg["shopee_affiliate"]["app_id"] = str(app_id).strip()
    cfg["shopee_affiliate"]["secret"] = str(secret).strip()

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    return {"message": "Đã lưu cấu hình Shopee Affiliate Open API thành công!", "config": {"app_id": app_id.strip()}}

def sanitize_sub_id(s: Any) -> str:
    """Làm sạch Sub-ID: Shopee chỉ chấp nhận chữ cái và số [a-zA-Z0-9], tối đa 25 ký tự."""
    if not s:
        return "bot"
    clean = re.sub(r"[^a-zA-Z0-9]", "", str(s))
    return clean[:25] if clean else "bot"

def resolve_and_parse_url(target_url: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Phân tích URL sản phẩm Shopee, hỗ trợ mở rộng shortlink và trích xuất shop_id, item_id.
    Trả về: (shop_id, item_id, resolved_url)
    """
    target_url = target_url.strip()
    # Nếu là shortlink (s.shopee.vn hoặc shope.ee), thử follow redirect để lấy link đích
    if "s.shopee.vn" in target_url or "shope.ee" in target_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
            r = requests.head(target_url, headers=headers, allow_redirects=True, timeout=5)
            if r.url and r.url != target_url:
                target_url = r.url
        except Exception:
            pass

    # Tìm shop_id và item_id từ các cấu trúc URL Shopee phổ biến
    # Dạng 1: /product/{shop_id}/{item_id}
    m = re.search(r"/product/(\d+)/(\d+)", target_url)
    if m:
        return m.group(1), m.group(2), target_url

    # Dạng 2: -i.{shop_id}.{item_id} hoặc /i.{shop_id}.{item_id}
    m = re.search(r"[./-]i\.(\d+)\.(\d+)", target_url)
    if m:
        return m.group(1), m.group(2), target_url

    # Dạng 3: /item/{shop_id}/{item_id}
    m = re.search(r"/item/(\d+)/(\d+)", target_url)
    if m:
        return m.group(1), m.group(2), target_url

    return None, None, target_url

def build_universal_tracking_link(target_url: str, affiliate_id: str, sub_ids: List[str] = None) -> str:
    """
    Tạo link tracking Affiliate chuẩn của Shopee.
    Link này ghi nhận 100% doanh thu & hoa hồng cho tài khoản Affiliate ID.
    """
    shop_id, item_id, resolved_url = resolve_and_parse_url(target_url)
    sub_tag = sanitize_sub_id(sub_ids[0] if sub_ids else "bot")

    if shop_id and item_id:
        return (
            f"https://shopee.vn/product/{shop_id}/{item_id}?"
            f"utm_source=an_{affiliate_id}&utm_medium=affiliates&utm_campaign=default&"
            f"utm_content={sub_tag}&aff_id={affiliate_id}"
        )

    # Link chung (không bóc được product id)
    parsed = urlparse(resolved_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["utm_source"] = f"an_{affiliate_id}"
    params["utm_medium"] = "affiliates"
    params["utm_campaign"] = "default"
    params["utm_content"] = sub_tag
    params["aff_id"] = str(affiliate_id)

    new_query = urlencode(params)
    return urlunparse((parsed.scheme or "https", parsed.netloc or "shopee.vn", parsed.path, parsed.params, new_query, parsed.fragment))

def shorten_url_tinyurl(long_url: str) -> Optional[str]:
    """Tạo shortlink nhanh qua TinyURL API (dự phòng khi chưa cấu hình Shopee Open API)."""
    try:
        r = requests.get(f"https://tinyurl.com/api-create.php?url={long_url}", timeout=4)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except Exception:
        pass
    return None

def convert_via_open_api(target_url: str, sub_ids: List[str] = None, app_id: str = "", secret: str = "") -> Dict[str, Any]:
    """Tạo shortlink qua Shopee Affiliate Open API (GraphQL)."""
    if not (app_id and secret):
        return {"success": False, "message": "Chưa có App ID và Secret Key của Shopee Open API."}

    # Chuẩn hóa sub_ids (chỉ gồm a-z, A-Z, 0-9)
    sub_list = [sanitize_sub_id(s) for s in (sub_ids or ["bot"]) if s]
    query_str = f"""mutation {{
  generateShortLink(input: {{
    originUrl: "{target_url}",
    subIds: {json.dumps(sub_list)}
  }}) {{
    shortLink
  }}
}}"""
    payload = {"query": query_str}
    payload_str = json.dumps(payload, separators=(',', ':'))
    timestamp = int(time.time())
    factor = f"{app_id}{timestamp}{payload_str}{secret}"

    # Shopee Open API hỗ trợ chuẩn SHA256 hoặc HMAC-SHA256
    url = "https://open-api.affiliate.shopee.vn/graphql"

    # Thử phương thức 1: SHA256 tổng hợp
    sig_sha256 = hashlib.sha256(factor.encode("utf-8")).hexdigest()
    headers1 = {
        "Authorization": f"SHA256 Credential={app_id},Timestamp={timestamp},Signature={sig_sha256}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, data=payload_str, headers=headers1, timeout=10)
        if r.status_code == 200:
            res_json = r.json()
            short_link = res_json.get("data", {}).get("generateShortLink", {}).get("shortLink")
            if short_link:
                return {
                    "success": True,
                    "short_link": short_link,
                    "method": "open_api",
                    "message": "Tạo link affiliate qua Shopee Open API thành công!"
                }
            errors = res_json.get("errors", [])
            err_msg = errors[0].get("message") if errors else "API không trả về shortLink."
            return {"success": False, "message": f"Shopee Open API: {err_msg}"}
        
        # Thử phương thức 2: HMAC-SHA256 nếu phương thức 1 báo lỗi xác thực
        sig_hmac = hmac.new(secret.encode("utf-8"), factor.encode("utf-8"), hashlib.sha256).hexdigest()
        headers2 = {
            "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={sig_hmac}",
            "Content-Type": "application/json"
        }
        r2 = requests.post(url, data=payload_str, headers=headers2, timeout=10)
        if r2.status_code == 200:
            res_json = r2.json()
            short_link = res_json.get("data", {}).get("generateShortLink", {}).get("shortLink")
            if short_link:
                return {
                    "success": True,
                    "short_link": short_link,
                    "method": "open_api",
                    "message": "Tạo link affiliate qua Shopee Open API thành công!"
                }

        return {"success": False, "message": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": f"Lỗi gọi Shopee Open API: {str(e)}"}

def convert_to_shopee_aff_link(target_url: str, sub_ids: List[str] = None) -> Dict[str, Any]:
    """
    Hàm tổng hợp chuyển đổi link Shopee sang link Affiliate:
    1. Ưu tiên cao nhất: Tạo link s.shopee.vn qua Shopee Open API (nếu đã cấu hình App ID & Secret).
    2. Nếu chưa có Open API: Tự động trích xuất Publisher ID (Affiliate ID) từ Cookie portal và tạo link tracking chuẩn Shopee.
    """
    if not target_url or not target_url.strip():
        return {"success": False, "message": "Vui lòng nhập link sản phẩm Shopee.", "short_link": ""}

    target_url = target_url.strip()

    # 1. Thử qua Open API nếu đã cấu hình
    api_cfg = get_open_api_config()
    if api_cfg.get("app_id") and api_cfg.get("secret"):
        res = convert_via_open_api(target_url, sub_ids, api_cfg["app_id"], api_cfg["secret"])
        if res.get("success"):
            return res
        # Nếu Open API trả về lỗi nhưng có cấu hình, ta ghi chú lỗi và fallback sang Universal Tracking
        print(f"[ShopeeAff] Open API trả về lỗi ({res.get('message')}), chuyển sang Universal Tracking...")

    # 2. Sử dụng Publisher Affiliate ID từ Cookie Portal
    profile = fetch_affiliate_profile()
    aff_id = str(profile.get("affiliate_id") or "") if profile else ""
    aff_name = str(profile.get("nick_name") or profile.get("name") or "") if profile else ""

    # Nếu không gọi được API live nhưng file cookie có sẵn, thử lấy aff_id đã lưu hoặc mặc định
    if not aff_id:
        info = get_portal_cookie_info()
        aff_id = str(info.get("affiliate_id") or "")
        aff_name = str(info.get("affiliate_name") or "")

    if aff_id:
        # Link chuẩn Shopee gắn trực tiếp mã Publisher ID
        tracking_url = build_universal_tracking_link(target_url, aff_id, sub_ids)
        short_url = tracking_url
        name_display = f" ({aff_name})" if aff_name else ""
        return {
            "success": True,
            "short_link": short_url,
            "full_tracking_link": tracking_url,
            "affiliate_id": aff_id,
            "affiliate_name": aff_name,
            "method": "universal_tracking",
            "message": f"Đã gắn mã Publisher ID {aff_id}{name_display} thành công! (Nhập App ID & Secret Key bên trên để tạo link s.shopee.vn)"
        }

    # 3. Chưa có cả Open API lẫn Cookie Portal hợp lệ
    return {
        "success": False,
        "short_link": "",
        "message": (
            "Chưa xác thực được tài khoản Shopee Affiliate! "
            "Vui lòng nhập Cookie từ https://affiliate.shopee.vn hoặc điền App ID & Secret Key bên trên."
        )
    }
