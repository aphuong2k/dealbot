"""Module Lazada Hunter:
Tự động tìm kiếm sản phẩm trên Lazada theo danh sách cần theo dõi,
so sánh giá từng phân loại (SKU), lọc gian hàng LazMall / Tmall,
và gửi thông báo cảnh báo kèo hời về Telegram.
"""
import os, sys, time, json, yaml, re, unicodedata
from typing import Dict, Any, List, Optional, Tuple
import db
from notify import tg
from . import lazada

def remove_accents(input_str: str) -> str:
    """Loại bỏ dấu tiếng Việt để so khớp không dấu."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def normalize_text(text: str) -> str:
    """Chuẩn hóa chuỗi về chữ thường, bỏ dấu và ký tự đặc biệt."""
    text = remove_accents(text).lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def compact_text(text: str) -> str:
    """Bỏ khoảng trắng để so khớp các model dính liền như s75pro vs s 75 pro."""
    return re.sub(r'\s+', '', normalize_text(text))

# Danh sách từ khóa phụ kiện / linh kiện thay thế (để chặn bẫy giá rẻ của shop)
ACCESSORY_KEYWORDS = [
    "che bui", "dust cover", "dustcover", "nap day", "tam day",
    "day cap", "cap type c", "type c", "day lo xo", "coiled cable",
    "switch le", "combo switch", "pack switch", "set switch", "10 switch", "30 switch", "45 switch",
    "keycap", "key cap", "nut ban phim", "bo keycap",
    "num xoay", "knob", "num kim loai",
    "tui dung", "bao da", "tui chong soc",
    "foam", "pad chuot", "lot chuot", "mousepad",
    "plate", "mach pcb", "stab", "lubing", "dung cu", "keypuller", "switch puller"
]

# Từ khóa không liên quan (tránh nhầm model sang các ngành hàng khác như sơn, cơ khí)
UNRELATED_KEYWORDS = [
    "sung phun son", "spray gun", "binh son", "may phun", "may han", "dau phun"
]

def is_like_match(
    tracked_keyword: str,
    title: str,
    variation_name: str = "",
    laz_price: float = 0.0,
    avg_price: float = 0.0,
    min_discount_pct: float = 5.0,
    max_discount_pct: float = 75.0
) -> Tuple[bool, str]:
    """Hàm so khớp LIKE thông minh:
    1. Kiểm tra LIKE từ khóa model trong tiêu đề / phân loại
    2. Chống bẫy phụ kiện (Accessory Trap) và sản phẩm ngoại lai
    3. Chống nhầm model lân cận (vd: f75 nhầm sang f87, f99)
    4. Kiểm tra sàn chiết khấu tối đa (tránh phụ kiện 30k trong bài 800k)
    """
    norm_kw = normalize_text(tracked_keyword)
    comp_kw = compact_text(tracked_keyword)
    norm_title = normalize_text(title)
    comp_title = compact_text(title)
    norm_var = normalize_text(variation_name)
    comp_var = compact_text(variation_name)

    # 1. Loại trừ ngành hàng ngoại lai (súng sơn, máy công cụ...)
    for unrel in UNRELATED_KEYWORDS:
        if unrel in norm_title or unrel in norm_var:
            return False, f"Loại trừ: Ngành hàng không liên quan '{unrel}'"

    # 2. Bẫy phụ kiện (Accessory Trap):
    is_keyboard = any(k in norm_title for k in ["ban phim", "keyboard", "phim co", "kit", "custom"])
    for acc in ACCESSORY_KEYWORDS:
        # Nếu là núm xoay nhưng tiêu đề là cả chiếc bàn phím (with knob) thì không reject
        if acc in ["knob", "num xoay", "num kim loai"] and is_keyboard:
            continue
        if acc in norm_var:
            return False, f"Loại trừ: Phân loại chứa phụ kiện '{acc}' ({variation_name})"
        if acc in norm_title and not is_keyboard:
            return False, f"Loại trừ: Tiêu đề là phụ kiện '{acc}'"

    # 3. Kiểm tra biên độ giá hợp lý (Sanity Check)
    if avg_price > 0 and laz_price > 0:
        disc_pct = ((avg_price - laz_price) / avg_price) * 100.0
        if disc_pct < min_discount_pct:
            return False, f"Chưa đủ giảm giá: Giảm {disc_pct:.1f}% < ngưỡng {min_discount_pct}%"
        if disc_pct > max_discount_pct:
            # Nếu giảm sâu trên ngưỡng (kể cả 75% - 90%), nhưng giá bán >= 50.000đ và không dính phụ kiện:
            # Đây chính là kèo Sập Sàn Phân Loại (Single-SKU Clearance / Glitch) xịn
            is_accessory = any(acc in norm_var for acc in ACCESSORY_KEYWORDS)
            if laz_price >= 50000 and not is_accessory and disc_pct <= 92.0:
                pass  # Cho phép kèo giảm sâu phân loại
            else:
                return False, f"Bẫy giá rẻ bất thường: Giảm {disc_pct:.1f}% > {max_discount_pct}% (nghi ngờ phụ kiện)"

    # 4. So khớp LIKE model:
    # Model tokens (ví dụ: f75, s75pro, 68he, win 60)
    model_tokens = [w for w in norm_kw.split() if any(c.isdigit() for c in w) or len(w) >= 3]
    if not model_tokens:
        model_tokens = [norm_kw]

    has_model_match = False
    if comp_kw in comp_title or comp_kw in comp_var:
        has_model_match = True
    else:
        matched_tokens = 0
        for tok in model_tokens:
            compact_tok = compact_text(tok)
            if compact_tok in comp_title or compact_tok in comp_var:
                matched_tokens += 1
        if matched_tokens == len(model_tokens):
            has_model_match = True

    if not has_model_match:
        return False, f"Không khớp model: '{tracked_keyword}' không LIKE trong tiêu đề"

    # 5. Chống nhầm model lân cận (Model Exclusion)
    digits_in_kw = re.findall(r'\d+', norm_kw)
    if digits_in_kw:
        target_num = digits_in_kw[0]
        other_models = re.findall(r'\b[a-z]{1,3}\s*(\d{2,3})\b', norm_title)
        for num in other_models:
            if num != target_num and target_num not in other_models:
                return False, f"Loại trừ: Tiêu đề chứa model khác #{num} thay vì #{target_num}"

    return True, "Khớp hợp lệ"

def get_hunter_config() -> Dict[str, Any]:
    """Đọc cấu hình lazada_hunter từ config.yaml."""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    try:
        data = yaml.safe_load(open(cfg_path, encoding="utf-8"))
        return data.get("lazada_hunter", {
            "enabled": True,
            "interval_minutes": 5,
            "filter_mall_only": True,
            "min_discount_pct": 10.0,
            "selected_groups": [],
            "max_search_results": 10
        })
    except Exception:
        return {
            "enabled": True,
            "interval_minutes": 5,
            "filter_mall_only": True,
            "min_discount_pct": 10.0,
            "selected_groups": [],
            "max_search_results": 10
        }

def save_hunter_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """Lưu cấu hình lazada_hunter vào config.yaml."""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    data = {}
    try:
        data = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
    except Exception:
        pass

    curr = data.get("lazada_hunter", {})
    curr.update(new_config)
    data["lazada_hunter"] = curr

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return curr

def format_deal_telegram_message(deal: Dict[str, Any]) -> str:
    """Tạo nội dung thông báo Telegram đẹp mắt chuẩn HTML."""
    prod_name = deal.get("product_name", "")
    var_name = deal.get("variation_name", "Tiêu chuẩn")
    seller = deal.get("seller_name", "Shop Lazada")
    is_mall = deal.get("is_mall", True)
    laz_price = deal.get("laz_price", 0)
    avg_price = deal.get("market_avg_price", 0)
    diff_pct = deal.get("diff_pct", 0)
    save_amount = avg_price - laz_price
    url = deal.get("product_url", "https://www.lazada.vn/")
    time_str = time.strftime("%H:%M:%S - %d/%m/%Y")

    mall_badge = "🎖️ <b>LazMall (Chính Hãng)</b>" if is_mall else "🏪 <b>Shop Uy Tín</b>"

    msg = (
        f"🔥 <b>[KÈO HỜI LAZADA RẺ HƠN THỊ TRƯỜNG FB]</b> 🔥\n\n"
        f"📦 <b>Sản phẩm:</b> {prod_name}\n"
        f"🏷️ <b>Phân loại:</b> <code>{var_name}</code>\n"
        f"🏬 <b>Gian hàng:</b> {seller} ({mall_badge})\n\n"
        f"💰 <b>Giá Lazada:</b> <code>{laz_price:,.0f} đ</code>\n"
        f"📊 <b>Giá TB thị trường FB:</b> <code>{avg_price:,.0f} đ</code>\n"
        f"📉 <b>Rẻ hơn:</b> <b>-{diff_pct:.1f}%</b> (Tiết kiệm <b>{save_amount:,.0f} đ</b>)\n\n"
        f"🛒 <b>Link săn ngay:</b> <a href=\"{url}\">Bấm vào đây để xem sản phẩm</a>\n"
        f"⏰ <i>Quét tự động lúc: {time_str}</i>"
    )
    return msg

_hunter_status: Dict[str, Any] = {
    "is_running": False,
    "trigger_type": "none",
    "started_at": 0,
    "total_products": 0,
    "current_index": 0,
    "current_product_name": "",
    "deals_found": 0,
    "message": "Sẵn sàng",
    "last_finished_at": 0,
    "last_result": None
}

def get_hunter_status() -> Dict[str, Any]:
    global _hunter_status
    st = dict(_hunter_status)
    if st["is_running"] and st["started_at"] > 0:
        st["elapsed_seconds"] = int(time.time() - st["started_at"])
    else:
        st["elapsed_seconds"] = 0
    return st

def run_lazada_hunter_cycle(batch_size: Optional[int] = None, trigger_type: str = "auto_5m") -> Dict[str, Any]:
    """Chạy 1 chu kỳ săn deal Lazada:
    - Quét toàn bộ danh sách sản phẩm đang lưu trong DB (hoặc batch_size nếu chỉ định)
    - Tìm kiếm trên Lazada qua tiến trình subprocess độc lập
    - So sánh giá từng phân loại với giá TB thị trường Facebook
    - Bắn Telegram nếu thỏa mãn điều kiện rẻ hơn ngưỡng chiết khấu
    - Cập nhật nhật ký hoàn tất chu kỳ
    """
    global _hunter_status
    if _hunter_status.get("is_running"):
        return {
            "status": "already_running",
            "message": "Chu kỳ quét deal Lazada đang chạy, vui lòng chờ hoàn tất.",
            "deals_found": 0
        }

    cfg = get_hunter_config()
    start_time = time.time()

    # 1. Tạo bản ghi nhật ký ban đầu (trạng thái running)
    log_id = db.x("""
        INSERT INTO lazada_hunter_logs(
            started_at, finished_at, status, trigger_type,
            products_scanned, deals_found, telegram_sent, details, message, created_at
        ) VALUES (?, 0, 'running', ?, 0, 0, 0, '[]', 'Đang thực hiện quét tất cả sản phẩm theo dõi trên Lazada...', ?)
    """, (start_time, trigger_type, start_time))

    _hunter_status.update({
        "is_running": True,
        "trigger_type": trigger_type,
        "started_at": start_time,
        "total_products": 0,
        "current_index": 0,
        "current_product_name": "",
        "deals_found": 0,
        "message": "Đang khởi động chu kỳ quét deal Lazada..."
    })

    if not cfg.get("enabled", True):
        finish_time = time.time()
        msg = "Lazada Hunter đang tắt trong cấu hình (enabled = False)."
        db.x("""
            UPDATE lazada_hunter_logs
            SET finished_at = ?, status = 'skipped', message = ?
            WHERE id = ?
        """, (finish_time, msg, log_id))
        _hunter_status["is_running"] = False
        _hunter_status["last_finished_at"] = finish_time
        _hunter_status["last_result"] = msg
        _hunter_status["message"] = msg
        return {"status": "skipped", "message": msg, "deals_found": 0, "log_id": log_id}

    # Lấy toàn bộ danh sách sản phẩm active từ DB để quét sạch tất cả sản phẩm
    if batch_size and batch_size > 0:
        products = db.q("""
            SELECT * FROM lazada_tracked_products
            WHERE is_active = 1 AND avg_price > 0
            ORDER BY last_scanned_at ASC
            LIMIT ?
        """, (batch_size,))
    else:
        products = db.q("""
            SELECT * FROM lazada_tracked_products
            WHERE is_active = 1 AND avg_price > 0
            ORDER BY last_scanned_at ASC
        """)

    if not products:
        finish_time = time.time()
        msg = "Không có sản phẩm nào đang kích hoạt theo dõi trong cơ sở dữ liệu."
        db.x("""
            UPDATE lazada_hunter_logs
            SET finished_at = ?, status = 'success', products_scanned = 0, deals_found = 0, message = ?
            WHERE id = ?
        """, (finish_time, msg, log_id))
        _hunter_status["is_running"] = False
        _hunter_status["last_finished_at"] = finish_time
        _hunter_status["last_result"] = msg
        _hunter_status["message"] = msg
        return {"status": "ok", "message": msg, "deals_found": 0, "log_id": log_id}

    deals_found_count = 0
    now = time.time()
    day_ago = now - 86400  # 24 giờ qua
    scan_details = []
    summary_msg = ""
    _hunter_status["total_products"] = len(products)

    try:
        for idx, prod in enumerate(products, 1):
            prod_id = prod["id"]
            prod_name = prod["name"]
            kw = prod["clean_keyword"] or prod_name
            avg_price = float(prod["avg_price"] or 0)
            filter_mall = bool(prod["filter_mall_only"] if prod["filter_mall_only"] is not None else cfg.get("filter_mall_only", True))
            min_disc = float(prod["min_discount_pct"] or cfg.get("min_discount_pct", 10.0))

            _hunter_status["current_index"] = idx
            _hunter_status["current_product_name"] = prod_name
            _hunter_status["deals_found"] = deals_found_count
            _hunter_status["message"] = f"Đang quét [{idx}/{len(products)}]: {prod_name}"

            if avg_price <= 0:
                continue

            prod_detail = {
                "product_id": prod_id,
                "product_name": prod_name,
                "keyword": kw,
                "avg_price": avg_price,
                "filter_mall": filter_mall,
                "min_discount_pct": min_disc,
                "items_found": 0,
                "lowest_price": 0.0,
                "new_deals": 0
            }

            try:
                # 1. Tìm kiếm sâu 30-40 sản phẩm trên Lazada (qua tiến trình độc lập an toàn)
                search_limit = int(cfg.get("max_search_results", 40))
                # Sử dụng từ khóa clean_keyword trực tiếp để tìm kiếm chính xác (hỗ trợ cả bàn phím, chuột, tai nghe...)
                search_query = kw.strip()
                items = lazada.search_lazada_products(search_query, filter_mall_only=filter_mall, limit=search_limit)
                items = items or []
                prod_detail["items_found"] = len(items)

                lowest_p = 0.0
                for item in items:
                    # Nếu yêu cầu LazMall mà item không phải mall thì bỏ qua
                    if filter_mall and not item.get("is_mall", False):
                        continue

                    item_id = item.get("item_id", "")
                    title = item.get("title", "")
                    seller_name = item.get("seller_name", "")
                    prod_url = item.get("product_url", "")
                    image_url = item.get("image_url", "")
                    is_mall_item = item.get("is_mall", True)

                    # 2. Duyệt qua từng phân loại (Variations / SKUs)
                    variations = item.get("variations") or []
                    for var in variations:
                        var_name = var.get("name") or "Tiêu chuẩn"
                        sku_id = var.get("sku_id") or item_id
                        var_price = float(var.get("price") or 0)

                        # 1. Ghi nhận giá thấp nhất thực tế của model này trên sàn Lazada
                        is_real_model, _ = is_like_match(
                            tracked_keyword=kw,
                            title=title,
                            variation_name=var_name,
                            laz_price=0,
                            avg_price=0,
                            min_discount_pct=0,
                            max_discount_pct=100.0
                        )
                        if is_real_model and var_price > 0:
                            if lowest_p == 0.0 or var_price < lowest_p:
                                lowest_p = var_price

                        # 2. So khớp LIKE thông minh (loại trừ phụ kiện, chống nhầm model, kiểm tra giảm giá hợp lý)
                        is_matched, match_reason = is_like_match(
                            tracked_keyword=kw,
                            title=title,
                            variation_name=var_name,
                            laz_price=var_price,
                            avg_price=avg_price,
                            min_discount_pct=min_disc,
                            max_discount_pct=75.0
                        )

                        if not is_matched:
                            continue

                        diff_pct = round(((avg_price - var_price) / avg_price) * 100.0, 1)

                        # 4. Kiểm tra chống spam: Trong 24h qua đã gửi deal này chưa?
                        recent = db.q("""
                            SELECT id FROM lazada_found_deals
                            WHERE laz_item_id = ? AND laz_sku_id = ? AND sent_to_tg_at > ?
                        """, (item_id, sku_id, day_ago), one=True)

                        if not recent:
                            deal_data = {
                                "product_id": prod_id,
                                "product_name": prod_name,
                                "laz_item_id": item_id,
                                "laz_sku_id": sku_id,
                                "variation_name": var_name,
                                "seller_name": seller_name,
                                "is_mall": 1 if is_mall_item else 0,
                                "laz_price": var_price,
                                "market_avg_price": avg_price,
                                "diff_pct": diff_pct,
                                "product_url": prod_url,
                                "image_url": image_url
                            }

                            # Gửi thông báo Telegram
                            try:
                                tg_text = format_deal_telegram_message(deal_data)
                                tg(tg_text, parse_mode="HTML")
                            except Exception as tg_err:
                                print(f"[lazada_hunter] Gửi TG thất bại: {tg_err}")

                            # Ghi nhận vào DB
                            db.x("""
                                INSERT INTO lazada_found_deals(
                                    product_id, product_name, laz_item_id, laz_sku_id, variation_name,
                                    seller_name, is_mall, laz_price, market_avg_price, diff_pct,
                                    product_url, image_url, sent_to_tg, sent_to_tg_at, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """, (
                                prod_id, prod_name, item_id, sku_id, var_name,
                                seller_name, 1 if is_mall_item else 0, var_price, avg_price, diff_pct,
                                prod_url, image_url, now, now
                            ))

                            deals_found_count += 1
                            prod_detail["new_deals"] += 1

                prod_detail["lowest_price"] = lowest_p
            except Exception as e:
                print(f"[lazada_hunter] Lỗi quét sản phẩm #{prod_id} ({kw}): {e}")
                prod_detail["error"] = str(e)
            finally:
                # Cập nhật thời điểm quét
                db.x("UPDATE lazada_tracked_products SET last_scanned_at = ? WHERE id = ?", (now, prod_id))
                scan_details.append(prod_detail)

        finish_time = time.time()
        duration = round(finish_time - start_time, 1)
        summary_msg = f"Đã quét {len(products)} sản phẩm trong {duration}s. Phát hiện {deals_found_count} deal hời gửi Tele."

        db.x("""
            UPDATE lazada_hunter_logs
            SET finished_at = ?, status = 'success', products_scanned = ?, deals_found = ?,
                telegram_sent = ?, details = ?, message = ?
            WHERE id = ?
        """, (
            finish_time, len(products), deals_found_count, deals_found_count,
            json.dumps(scan_details, ensure_ascii=False), summary_msg, log_id
        ))

        return {
            "status": "success",
            "products_checked": len(products),
            "deals_found": deals_found_count,
            "duration_seconds": duration,
            "log_id": log_id,
            "message": summary_msg,
            "details": scan_details,
            "timestamp": finish_time
        }
    except Exception as e:
        finish_time = time.time()
        err_msg = f"Lỗi chu kỳ quét Lazada: {e}"
        print(f"[lazada_hunter] ❌ {err_msg}")
        summary_msg = err_msg
        db.x("""
            UPDATE lazada_hunter_logs
            SET finished_at = ?, status = 'error', message = ?
            WHERE id = ?
        """, (finish_time, err_msg, log_id))
        return {
            "status": "error",
            "message": err_msg,
            "deals_found": deals_found_count,
            "log_id": log_id
        }
    finally:
        _hunter_status["is_running"] = False
        _hunter_status["last_finished_at"] = time.time()
        _hunter_status["last_result"] = summary_msg
        _hunter_status["message"] = summary_msg or "Sẵn sàng"
