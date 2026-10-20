"""Module quét bài viết từ 5 nhóm Facebook, bóc tách Tên sản phẩm & Giá bán trung bình.
Sử dụng Playwright kèm cookie tài khoản có sẵn (nick_a / nick_b).
"""
import os, sys, time, re, json, subprocess
from typing import List, Dict, Any, Tuple

if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import db

def _load_account_cookies(account_name: str = "nick_a") -> List[Dict[str, Any]]:
    """Tải cookies của tài khoản Facebook."""
    cookie_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies", f"{account_name}.json")
    if not os.path.exists(cookie_file):
        # Thử fallback nick_b nếu nick_a không có
        cookie_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies", "nick_b.json")
        if not os.path.exists(cookie_file):
            return []

    try:
        raw = json.load(open(cookie_file, encoding="utf-8"))
        cookies = []
        for c in raw:
            if isinstance(c, dict) and "name" in c and "value" in c:
                cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".facebook.com"),
                    "path": c.get("path", "/"),
                    "secure": True
                })
        return cookies
    except Exception:
        return []

KNOWN_BRANDS = [
    "aula", "hero", "vxe", "vgn", "leobog", "mchose", "atk", "drunkdeer",
    "monsgeek", "akko", "ajazz", "logitech", "razer", "corsair", "keychron",
    "fl-esports", "flesports", "dareu", "nuphy", "lofree", "apple", "samsung",
    "lg", "dell", "sony", "asus", "acer", "lenovo", "msi", "edifier", "fuhlen",
    "e-dra", "edra", "rk", "royal kludge", "redragon", "langtu", "machenike",
    "darmoshark", "scyrox", "lamzu", "ninjutso", "pulsar", "zaopin", "waizowl",
    "rainy", "crush", "lucky", "xinmeng", "weikav", "cidoo", "epomaker", "wooting"
]

MODEL_TOKEN_RE = re.compile(
    r'\b('
    r'[a-zA-Z]{1,5}\d{1,4}[a-zA-Z]{0,4}'       # f75, s75pro, gx87, r1, f1, g304, 24mp500
    r'|\d{1,4}[a-zA-Z]{1,4}'                    # 68he, 75v2, 87pro
    r'|(?:win|rainy|crush|lucky|hi|nd|a|k|rk|g|m|v)\s*\d{1,4}(?:\s*(?:pro|max|plus|he|ultra|v2|v3))?'
    r')\b',
    re.I
)

LOCATIONS = [
    "tp hcm", "tphcm", "hcm", "sài gòn", "saigon", "hà nội", "hanoi", "hn", "thủ đức",
    "gò vấp", "quận 9", "quận 1", "quận 7", "quận 12", "bình thạnh", "tân bình",
    "cầu giấy", "đống đa", "hoàng mai", "hà đông", "thanh xuân", "võ văn ngân",
    "đỗ xuân hợp", "tb"
]

FILLERS = [
    "mình có", "em có", "e có", "mình cần", "em cần", "e cần", "bác nào", "ai cần", "ai lấy",
    "cần bay", "bay nhanh", "cần bán", "bán nhanh", "bán gấp", "bán lại", "bán",
    "pass lại", "cần pass", "pass nhanh", "pass", "thanh lý", "nhượng lại", "nhượng",
    "gom sale", "gom deal", "tìm mua", "cần tìm", "tìm", "mua", "dọn nhà",
    "gdtt", "giao dịch trực tiếp", "ship cod", "freeship", "free ship", "ship", "cod", "toàn quốc",
    "khu vực", "quanh", "gần",
    "vài con", "mấy con", "vài mẫu", "mẫu", "ít", "con", "cây", "chiếc", "bé", "bộ", "set", "pack",
    "new seal", "newseal", "new 100%", "new", "likenew", "like new", "used", "cũ",
    "mới tinh", "mới 99%", "mới", "chính hãng", "auth", "full box", "fullbox", "nobox", "no box",
    "chưa sử dụng", "lần nào", "như hình", "ạ", "nhé", "nha", "nè", "này", "hàng",
    "rapid trigger", "đen/trắng", "trắng", "đen", "giá", "mình nga", "ở", "tại", "còn"
]

GENERIC_ONLY = {"phím", "bàn phím", "kit", "chuột", "tai nghe", "màn hình", "cáp", "sạc", "vỏ", "switch", "keycap", "đồ", "máy"}

def is_fb_system_text(text: str) -> bool:
    """Kiểm tra văn bản có phải giao diện/tiêu đề hệ thống Facebook không."""
    low = text.lower()
    return any(p in low for p in [
        "thành viên", "bài viết/ngày", "bài viết /ngày", "bài viết mỗi ngày", "bài viết mới",
        "quy tắc nhóm", "quản trị viên", "người kiểm duyệt", "nhóm công khai", "nhóm riêng tư",
        "bạn đang nghĩ gì", "giới thiệu về nhóm", "lượt thích", "người theo dõi"
    ])

def clean_segment(seg: str) -> str:
    """Loại bỏ địa danh, từ đệm, từ xưng hô ra khỏi câu."""
    s = " " + seg.lower() + " "
    for loc in sorted(LOCATIONS, key=len, reverse=True):
        s = re.sub(rf'[\s,/.-]{re.escape(loc)}[\s,/.-]', " ", s)
    for fil in sorted(FILLERS, key=len, reverse=True):
        s = re.sub(rf'\b{re.escape(fil)}\b', " ", s)
    s = re.sub(r'[^\w\s]', " ", s)
    s = re.sub(r'\s+', " ", s).strip()
    return s

def extract_product_keyword(cleaned_text: str) -> str:
    """Trích xuất từ khóa sản phẩm chuẩn (Thương hiệu + Mã model, ví dụ: hero 68he, f75, s75pro, aula win 60)."""
    words = cleaned_text.split()
    if not words:
        return ""

    model_m = MODEL_TOKEN_RE.search(cleaned_text)

    brand_found = None
    brand_start = -1
    for b in sorted(KNOWN_BRANDS, key=len, reverse=True):
        m = re.search(rf'\b{re.escape(b)}\b', cleaned_text, re.I)
        if m:
            brand_found = m.group(0)
            brand_start = m.start()
            break

    if model_m:
        m_str = model_m.group(0).strip()
        m_start = model_m.start()

        # Nếu có brand đứng trước hoặc ngay sát model
        if brand_found and brand_start < m_start and (m_start - brand_start) < 25:
            between = cleaned_text[brand_start:model_m.end()].strip()
            after = cleaned_text[model_m.end():].strip().split()
            suffix = []
            for w in after[:2]:
                if w.lower() in ["pro", "max", "plus", "he", "ultra", "v2", "v3", "superlight"]:
                    suffix.append(w)
                else:
                    break
            res = (between + " " + " ".join(suffix)).strip()
            return " ".join(res.split())
        else:
            after = cleaned_text[model_m.end():].strip().split()
            suffix = []
            for w in after[:2]:
                if w.lower() in ["pro", "max", "plus", "he", "ultra", "v2", "v3"]:
                    suffix.append(w)
                else:
                    break
            before = cleaned_text[:m_start].strip().split()
            prefix = []
            if before and before[-1].lower() in KNOWN_BRANDS:
                prefix.append(before[-1])
            res = (" ".join(prefix) + " " + m_str + " " + " ".join(suffix)).strip()
            return " ".join(res.split())

    if brand_found:
        after = cleaned_text[brand_start:].strip().split()
        return " ".join(after[:3])

    for kw in ["keycap", "switch"]:
        if kw in cleaned_text:
            idx = cleaned_text.find(kw)
            after = cleaned_text[idx:].strip().split()
            if len(after) >= 2:
                return " ".join(after[:3])

    return ""

def extract_price_and_product(text: str) -> List[Tuple[str, float]]:
    """Trích xuất danh sách cặp (Từ khóa sản phẩm chuẩn, Giá VNĐ) từ bài viết Facebook."""
    if is_fb_system_text(text):
        return []

    clauses = re.split(r'[,;\n\+\-\|•]+', text)
    results = []

    for clause in clauses:
        clause = clause.strip()
        if not clause or len(clause) < 3:
            continue

        # Regex tìm giá (tránh khớp số thành viên '593k thành viên')
        m_pr = re.search(r'(\d{1,4})\s*(?:k|ngàn|nghìn)(?!\s*(?:thành viên|tv|bài|lượt|view|sub|follow|mem))\b', clause, re.I)
        if not m_pr:
            m_pr = re.search(r'(\d+)\s*(?:tr|triệu)\s*(\d+)?\b', clause, re.I)
            if m_pr:
                tr = int(m_pr.group(1))
                le = int(m_pr.group(2)) if m_pr.group(2) else 0
                val = tr * 1_000_000 + (le * 100_000 if le < 10 else le * 1_000)
            else:
                m_pr = re.search(r'(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|vnd|vnđ)?\b', clause, re.I)
                if m_pr:
                    val = float(re.sub(r'[^\d]', '', m_pr.group(1)))
                else:
                    continue
        else:
            val = int(m_pr.group(1)) * 1000

        if not (20_000 <= val <= 50_000_000):
            continue

        seg = clause[:m_pr.start()] + " " + clause[m_pr.end():]
        cleaned = clean_segment(seg)
        kw = extract_product_keyword(cleaned)

        if kw and len(kw.split()) <= 4 and kw not in GENERIC_ONLY:
            results.append((kw, val))

    return results

def scan_facebook_groups_posts(group_urls: List[str], account_name: str = "nick_a", posts_per_group: int = 25) -> Dict[str, Any]:
    """Quét danh sách bài viết từ tối đa 5 nhóm Facebook qua Playwright."""
    from playwright.sync_api import sync_playwright

    cookies = _load_account_cookies(account_name)
    if not cookies:
        return {
            "success": False,
            "error": f"Chưa tìm thấy Cookie của tài khoản Facebook ({account_name}). Vui lòng cập nhật cookie trước.",
            "products_scanned": 0
        }

    valid_urls = [u.strip() for u in group_urls if u.strip()][:5]
    if not valid_urls:
        return {
            "success": False,
            "error": "Vui lòng chọn ít nhất 1 nhóm Facebook.",
            "products_scanned": 0
        }

    raw_extractions = []
    total_posts_read = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        context.add_cookies(cookies)

        for g_url in valid_urls:
            page = context.new_page()
            try:
                # Mở nhóm Facebook
                target = g_url
                if not target.endswith("/"):
                    target += "/"
                page.goto(target, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                # Cuộn trang linh hoạt theo số bài cần cào (đào sâu bài viết thị trường)
                scroll_count = max(6, int(posts_per_group / 4))
                for _ in range(scroll_count):
                    page.mouse.wheel(0, 1400)
                    page.wait_for_timeout(1200)

                # Lấy text các bài viết, bỏ qua thành viên và tiêu đề nhóm FB
                post_texts = page.evaluate("""() => {
                    const texts = [];
                    const isSystemNoise = (str) => {
                        const s = str.toLowerCase();
                        return (
                            s.includes('thành viên') ||
                            s.includes('bài viết/ngày') ||
                            s.includes('bài viết /ngày') ||
                            s.includes('bài viết mới') ||
                            s.includes('quy tắc nhóm') ||
                            s.includes('quản trị viên') ||
                            s.includes('người kiểm duyệt') ||
                            s.includes('nhóm công khai') ||
                            s.includes('nhóm riêng tư') ||
                            s.includes('bạn đang nghĩ gì') ||
                            s.includes('giới thiệu về nhóm')
                        );
                    };

                    const selectors = [
                        'div[data-ad-preview="message"]',
                        'div[data-ad-comet-preview="message"]',
                        'div[role="feed"] div[dir="auto"]',
                        'div[role="article"] div[dir="auto"]'
                    ];
                    const elements = document.querySelectorAll(selectors.join(', '));
                    elements.forEach(el => {
                        const t = el.innerText ? el.innerText.trim() : '';
                        if (t && t.length > 15 && !texts.includes(t) && !isSystemNoise(t)) {
                            texts.push(t);
                        }
                    });
                    return texts;
                }""")

                total_posts_read += len(post_texts)
                for t in post_texts[:posts_per_group]:
                    pairs = extract_price_and_product(t)
                    for prod_name, price in pairs:
                        raw_extractions.append({
                            "name": prod_name,
                            "price": price,
                            "group_url": g_url
                        })
            except Exception as e:
                print(f"[fb_market_scanner] Lỗi quét nhóm {g_url}: {e}")
            finally:
                page.close()

        browser.close()

    # Gom nhóm sản phẩm & Tính toán giá trung bình
    aggregated = _aggregate_products(raw_extractions)
    
    # Lưu vào database lazada_tracked_products
    saved_count = _save_to_tracked_db(aggregated)

    return {
        "success": True,
        "scanned_groups": len(valid_urls),
        "total_posts_read": total_posts_read,
        "products_found": len(aggregated),
        "products_saved": saved_count,
        "sample_products": aggregated[:10]
    }

def _aggregate_products(raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gom nhóm các sản phẩm trùng/tương tự tên và tính giá trung bình."""
    groups_map = {}

    for item in raw_items:
        name = item["name"]
        price = item["price"]
        g_url = item["group_url"]

        # Chuẩn hóa keyword để gom cụm (thương hiệu + model code)
        norm_key = re.sub(r'[^\w\s]', '', name.lower()).strip()
        norm_key = " ".join(norm_key.split()[:4])  # Tối đa 4 từ

        if not norm_key or len(norm_key) < 2 or norm_key in GENERIC_ONLY:
            continue

        if norm_key not in groups_map:
            # Tạo tên hiển thị đẹp: Viết hoa mã sản phẩm (F75, S75PRO, Hero 68HE, Aula Win 60,...)
            disp_words = []
            for w in norm_key.split():
                if any(c.isdigit() for c in w) or len(w) <= 3:
                    disp_words.append(w.upper())
                else:
                    disp_words.append(w.capitalize())
            display_name = " ".join(disp_words)

            groups_map[norm_key] = {
                "display_name": display_name,
                "clean_keyword": norm_key,
                "prices": [],
                "source_groups": set()
            }

        groups_map[norm_key]["prices"].append(price)
        groups_map[norm_key]["source_groups"].add(g_url)

    result = []
    for k, data in groups_map.items():
        prices = data["prices"]
        if not prices:
            continue
        
        # Lọc outlier nếu có trên 3 mẫu
        if len(prices) >= 4:
            sorted_p = sorted(prices)
            # Cắt bớt phần tử thấp nhất và cao nhất
            prices = sorted_p[1:-1]

        avg_p = sum(prices) / len(prices)
        # Làm tròn đến hàng nghìn
        avg_p = round(avg_p / 1000.0) * 1000.0
        min_p = min(data["prices"])
        max_p = max(data["prices"])

        result.append({
            "name": data["display_name"],
            "clean_keyword": data["clean_keyword"],
            "avg_price": avg_p,
            "min_price": min_p,
            "max_price": max_p,
            "sample_count": len(data["prices"]),
            "source_groups": ",".join(list(data["source_groups"]))
        })

    # Sắp xếp theo số lượng bài viết nhắc đến nhiều nhất
    result.sort(key=lambda x: x["sample_count"], reverse=True)
    return result

def cleanup_junk_tracked_products() -> int:
    """Dọn dẹp các sản phẩm rác, câu văn dài hoặc tiêu đề nhóm FB trong bảng lazada_tracked_products."""
    rows = db.q("SELECT id, clean_keyword FROM lazada_tracked_products")
    deleted = 0
    for r in rows:
        kw = (r["clean_keyword"] or "").lower().strip()
        words = kw.split()

        # Tiêu chí rác: Chứa từ khóa giao diện FB hoặc dài hơn 4 từ hoặc từ chung chung vô nghĩa
        is_junk = (
            any(p in kw for p in ["thành viên", "bài viết", "mình có", "em có", "e cần", "hn mình", "dạ em", "về được", "quận", "thủ đức", "gò vấp"])
            or len(words) > 4
            or len(words) == 0
            or all(w in GENERIC_ONLY for w in words)
        )
        if is_junk:
            db.x("DELETE FROM lazada_tracked_products WHERE id = ?", (r["id"],))
            deleted += 1

    return deleted

def _save_to_tracked_db(aggregated: List[Dict[str, Any]]) -> int:
    """Lưu hoặc cập nhật danh sách sản phẩm & giá trung bình vào bảng lazada_tracked_products."""
    now = time.time()
    count = 0
    for prod in aggregated:
        name = prod["name"]
        kw = prod["clean_keyword"]
        avg_p = prod["avg_price"]
        min_p = prod["min_price"]
        max_p = prod["max_price"]
        samples = prod["sample_count"]
        sources = prod["source_groups"]

        # Kiểm tra xem sản phẩm đã tồn tại trong DB chưa
        row = db.q("SELECT id, avg_price, sample_count FROM lazada_tracked_products WHERE clean_keyword = ?", (kw,), one=True)
        if row:
            # Cập nhật giá trung bình mới
            old_avg = row["avg_price"] or avg_p
            # Tính trung bình kết hợp
            new_avg = round(((old_avg + avg_p) / 2.0) / 1000.0) * 1000.0
            db.x("""
                UPDATE lazada_tracked_products
                SET avg_price = ?, min_price = MIN(min_price, ?), max_price = MAX(max_price, ?),
                    sample_count = sample_count + ?, source_groups = ?, updated_at = ?
                WHERE id = ?
            """, (new_avg, min_p, max_p, samples, sources, now, row["id"]))
        else:
            db.x("""
                INSERT INTO lazada_tracked_products(
                    name, clean_keyword, avg_price, min_price, max_price,
                    sample_count, source_groups, is_active, filter_mall_only, min_discount_pct,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 10.0, ?, ?)
            """, (name, kw, avg_p, min_p, max_p, samples, sources, now, now))
            count += 1

    return count

def scan_facebook_groups_posts_isolated(group_urls: List[str], account_name: str = "nick_a", posts_per_group: int = 50) -> Dict[str, Any]:
    """Chạy cào bài viết Facebook trong một tiến trình subprocess riêng biệt (tránh xung đột asyncio của FastAPI)."""
    script_path = os.path.abspath(__file__)
    cmd = [sys.executable, script_path, "scan", account_name, "--limit", str(posts_per_group), "--groups"] + [u.strip() for u in group_urls if u.strip()]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        timeout_sec = max(300, len(group_urls) * 90)
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=BASE_DIR, timeout=timeout_sec)
        stdout_txt = proc.stdout.strip()
        if stdout_txt:
            try:
                if "{" in stdout_txt and "}" in stdout_txt:
                    s_idx = stdout_txt.find("{")
                    e_idx = stdout_txt.rfind("}") + 1
                    data = json.loads(stdout_txt[s_idx:e_idx])
                    if isinstance(data, dict):
                        return data
                data = json.loads(stdout_txt)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {"success": False, "error": proc.stderr.strip() or "Không có phản hồi từ tiến trình cào FB.", "products_scanned": 0}
    except Exception as e:
        return {"success": False, "error": f"Lỗi subprocess FB: {e}", "products_scanned": 0}

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["scan"])
    parser.add_argument("account", default="nick_a")
    parser.add_argument("--groups", nargs="+", default=[])
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    if args.action == "scan":
        res = scan_facebook_groups_posts(args.groups, account_name=args.account, posts_per_group=args.limit)
        print(json.dumps(res, ensure_ascii=True))
