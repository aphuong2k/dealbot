"""FastAPI Backend Server cho Dealbot Frontend (Angular + NG-ZORRO).
Cung cấp REST API đầy đủ để quản trị Deals, Groups, Lịch đăng, Coupons, Cấu hình và Báo cáo.
"""
import os, sys, time, yaml, threading, json, subprocess
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import db
from modules import groups, deals, planner, poster, coupons, telegram_channel, shopee, shopee_aff_converter
from notify import tg

load_dotenv()
db.init()

app = FastAPI(title="Dealbot Management API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = "config.yaml"
EVENTS_PATH = "events.yaml"

def get_config():
    return yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))

def save_config(cfg_data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg_data, f, allow_unicode=True, sort_keys=False)

# --- MODELS ---
class GroupUpdate(BaseModel):
    status: Optional[str] = None
    allow_link: Optional[int] = None
    account: Optional[str] = None
    priority_score: Optional[float] = None

class ConfigUpdate(BaseModel):
    dry_run: Optional[bool] = None
    niches: Optional[List[str]] = None
    dealhunt_niches: Optional[List[str]] = None
    deals: Optional[Dict[str, Any]] = None
    posting: Optional[Dict[str, Any]] = None
    accounts: Optional[List[Dict[str, Any]]] = None
    funnel: Optional[Dict[str, Any]] = None
    telegram_channel: Optional[Dict[str, Any]] = None
    learning: Optional[Dict[str, Any]] = None

class CookieUpdate(BaseModel):
    cookie_data: str

class EventItem(BaseModel):
    title: str
    merchant: str = "shopee"
    start: str
    end: str
    detail: Optional[str] = ""
    link: str

class SyncNichesRequest(BaseModel):
    niches: List[str]

class LeaveGroupRequest(BaseModel):
    group_url: str

class ImportGroupItem(BaseModel):
    url: str
    name: Optional[str] = ""
    account: Optional[str] = ""
    status: Optional[str] = "joined"
    kind: Optional[str] = "dealhunt"
    niche: Optional[str] = "săn sale"

class ImportGroupsRequest(BaseModel):
    groups: List[ImportGroupItem]

class ShopeeOpenApiConfig(BaseModel):
    app_id: str
    secret: str

class ShopeeTestConvertRequest(BaseModel):
    url: str
    sub_ids: Optional[List[str]] = None

# --- ENDPOINTS ---

@app.get("/api/stats")
def get_stats():
    """Tổng quan số liệu thống kê Dashboard."""
    today = db.today_start()
    now = time.time()
    cfg = get_config()

    total_deals = db.q("SELECT COUNT(*) c FROM deals", one=True)["c"]
    new_deals = db.q("SELECT COUNT(*) c FROM deals WHERE status='new'", one=True)["c"]

    total_groups = db.q("SELECT COUNT(*) c FROM groups", one=True)["c"]
    active_groups = db.q("SELECT COUNT(*) c FROM groups WHERE status IN ('joined','approved')", one=True)["c"]
    candidate_groups = db.q("SELECT COUNT(*) c FROM groups WHERE status='candidate'", one=True)["c"]
    cooling_groups = db.q("SELECT COUNT(*) c FROM groups WHERE status='cooling_down'", one=True)["c"]

    # Thống kê bài đăng hôm nay
    today_posts = db.q("SELECT status, COUNT(*) c FROM posts WHERE scheduled_at>? GROUP BY status", (today,))
    posts_by_status = {r["status"]: r["c"] for r in today_posts}

    # Thống kê tài khoản
    accounts_info = []
    for acc in cfg.get("accounts", []):
        row = db.q("SELECT * FROM accounts WHERE name=?", (acc["name"],), one=True)
        is_paused = (row and row["paused_until"] > now)
        paused_hours_left = max(0, int(((row["paused_until"] or 0) - now) / 3600)) if is_paused else 0
        posts_done_today = db.q("SELECT COUNT(*) c FROM posts WHERE account=? AND status='done' AND posted_at>?",
                                (acc["name"], today), one=True)["c"]
        accounts_info.append({
            "name": acc["name"],
            "status": "paused" if is_paused else "healthy",
            "paused_hours_left": paused_hours_left,
            "posts_today": posts_done_today,
            "max_posts_day": cfg.get("posting", {}).get("max_posts_per_account_per_day", 4),
            "last_warmup_at": row["last_warmup_at"] if row else 0
        })

    # Top deals đạt điểm cao nhất
    top_deals = [dict(d) for d in db.q("SELECT * FROM deals WHERE status IN ('new','planned') ORDER BY score DESC LIMIT 5")]

    return {
        "deals": {
            "total": total_deals,
            "new": new_deals
        },
        "groups": {
            "total": total_groups,
            "active": active_groups,
            "candidate": candidate_groups,
            "cooling_down": cooling_groups
        },
        "posts_today": {
            "total": sum(posts_by_status.values()),
            "done": posts_by_status.get("done", 0),
            "queued": posts_by_status.get("queued", 0),
            "pending_approval": posts_by_status.get("pending_approval", 0),
            "failed": posts_by_status.get("failed", 0),
            "skipped": posts_by_status.get("skipped", 0)
        },
        "accounts": accounts_info,
        "dry_run": cfg.get("dry_run", True),
        "top_deals": top_deals
    }

@app.get("/api/deals")
def list_deals(
    niche: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Danh sách deals cào được."""
    sql = "SELECT * FROM deals WHERE 1=1"
    args = []
    if niche:
        sql += " AND niche=?"
        args.append(niche)
    if status:
        sql += " AND status=?"
        args.append(status)
    if search:
        sql += " AND title LIKE ?"
        args.append(f"%{search}%")

    sql += " ORDER BY score DESC, created_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])

    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.post("/api/deals/crawl")
def trigger_crawl_deals(background_tasks: BackgroundTasks, source: Optional[str] = "all"):
    """Kích hoạt cào deal mới từ Shopee và Accesstrade."""
    def run_crawl():
        cfg = get_config()
        deals.refresh(cfg)
    background_tasks.add_task(run_crawl)
    return {"message": "Đang cào deal từ Shopee (Flash Sale & Ngành hàng) trong tiến trình nền..."}

@app.get("/api/groups")
def list_groups(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    niche: Optional[str] = None,
    search: Optional[str] = None,
    account: Optional[str] = None
):
    """Danh sách hội nhóm Facebook."""
    sql = "SELECT * FROM groups WHERE 1=1"
    args = []
    if status:
        sql += " AND status=?"
        args.append(status)
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if niche:
        sql += " AND niche=?"
        args.append(niche)
    if account:
        sql += " AND account=?"
        args.append(account)
    if search:
        sql += " AND (name LIKE ? OR url LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])

    sql += " ORDER BY priority_score DESC, fail_count ASC"
    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.put("/api/groups")
def update_group(url: str = Query(...), payload: GroupUpdate = ...):
    """Cập nhật trạng thái duyệt group, gán nick hoặc điểm ưu tiên."""
    updates = []
    args = []
    if payload.status is not None:
        updates.append("status=?")
        args.append(payload.status)
        if payload.status in ("joined", "approved"):
            updates.append("consecutive_fails=0")
    if payload.allow_link is not None:
        updates.append("allow_link=?")
        args.append(payload.allow_link)
    if payload.account is not None:
        updates.append("account=?")
        args.append(payload.account)
    if payload.priority_score is not None:
        updates.append("priority_score=?")
        args.append(payload.priority_score)

    if not updates:
        return {"message": "Không có gì thay đổi."}

    args.append(url)
    db.x(f"UPDATE groups SET {', '.join(updates)} WHERE url=?", tuple(args))
    return {"message": "Cập nhật group thành công!"}

@app.post("/api/groups/discover")
def trigger_discover_groups(background_tasks: BackgroundTasks):
    """Kích hoạt AI tìm kiếm group Facebook mới qua Google CSE."""
    def run_discover():
        cfg = get_config()
        names = [a["name"] for a in cfg.get("accounts", [])]
        groups.discover(cfg.get("niches", []), cfg.get("dealhunt_niches", []))
        groups.assign_accounts(names)
    background_tasks.add_task(run_discover)
    return {"message": "Đang tìm kiếm nhóm Facebook ứng viên..."}

@app.get("/api/posts")
def list_posts(
    status: Optional[str] = None,
    account: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Lịch trình bài đăng."""
    sql = "SELECT p.*, g.name as group_name FROM posts p LEFT JOIN groups g ON p.group_url=g.url WHERE 1=1"
    args = []
    if status:
        sql += " AND p.status=?"
        args.append(status)
    if account:
        sql += " AND p.account=?"
        args.append(account)

    sql += " ORDER BY p.scheduled_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])

    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.post("/api/posts/plan")
def trigger_plan():
    """Lập lịch phân bổ deal và bản tin săn sale cho hôm nay."""
    cfg = get_config()
    a = planner.plan_day(cfg)
    b = planner.plan_digests(cfg)
    return {"message": f"Đã lên lịch thành công {a} bài deal + {b} bản tin mã giảm giá!"}

@app.post("/api/posts/run-due")
def trigger_run_due(background_tasks: BackgroundTasks):
    """Thực thi đăng các bài đến giờ qua Playwright."""
    def run_post():
        cfg = get_config()
        poster.run_due(cfg)
    background_tasks.add_task(run_post)
    return {"message": "Đang thực thi phiên đăng bài..."}

@app.post("/api/posts/{post_id}/run-now")
def run_single_post_endpoint(post_id: int):
    """Đăng ngay lập tức một bài viết cụ thể."""
    cfg = get_config()
    post = db.q("SELECT * FROM posts WHERE id=?", (post_id,), one=True)
    if not post:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bài viết #{post_id}.")
    res = poster.post_single(cfg, dict(post))
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("message", "Lỗi khi đăng bài."))
    return res

@app.get("/api/coupons")
def list_coupons():
    """Danh sách mã giảm giá & voucher active."""
    rows = db.q("SELECT * FROM coupons ORDER BY end_at ASC LIMIT 60")
    return [dict(r) for r in rows]

@app.post("/api/coupons/refresh")
def trigger_refresh_coupons():
    added = coupons.refresh()
    return {"message": f"Đã cập nhật thêm {added} mã giảm giá mới!"}

@app.get("/api/events")
def get_events():
    """Đọc events.yaml."""
    if not os.path.exists(EVENTS_PATH):
        return []
    return yaml.safe_load(open(EVENTS_PATH, encoding="utf-8")) or []

@app.post("/api/events")
def save_events(events_list: List[EventItem]):
    """Cập nhật events.yaml."""
    data = [e.dict() for e in events_list]
    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    coupons.refresh()
    return {"message": "Đã lưu danh sách sự kiện!"}

@app.get("/api/config")
def read_config_endpoint():
    """Đọc config.yaml."""
    return get_config()

@app.put("/api/config")
def update_config_endpoint(payload: ConfigUpdate):
    """Cập nhật config.yaml."""
    cfg = get_config()
    p_dict = payload.dict(exclude_unset=True)
    for k, v in p_dict.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    save_config(cfg)
    return {"message": "Đã lưu cấu hình config.yaml thành công!", "config": cfg}

@app.post("/api/accounts/warmup")
def trigger_warmup(background_tasks: BackgroundTasks):
    """Kích hoạt nuôi nick nhẹ."""
    def run_warm():
        cfg = get_config()
        poster.warmup_accounts(cfg)
    background_tasks.add_task(run_warm)
    return {"message": "Bắt đầu phiên nuôi nick tương tác nhẹ..."}

@app.post("/api/telegram/test-notify")
def test_telegram_notify():
    """Gửi tin nhắn test tới Admin Telegram."""
    tg("🔔 <b>[Dealbot Test]</b> Kết nối Telegram Bot thành công!", parse_mode="HTML")
    return {"message": "Đã gửi thông báo test qua Telegram Bot!"}

@app.post("/api/telegram/post-digest")
def broadcast_telegram_digest(background_tasks: BackgroundTasks):
    """Đăng ngay bản tin tổng hợp mã giảm giá lên Telegram Channel."""
    def run_broadcast():
        cfg = get_config()
        dg = coupons.build_digest("shopee")
        if dg:
            img_path, _, _ = dg
            today_str = time.strftime("%d/%m")
            cs = coupons.active(limit=8)
            lines = [((c["code"] or "Ưu đãi"), c["title"] or c["detail"]) for c in cs]
            links = "\n".join(f"• {c['title'][:35]}: {c['aff_url']}" for c in cs if c["aff_url"])
            telegram_channel.post_digest_to_channel(
                cfg, f"Bản Tin Mã Giảm Giá Shopee {today_str}", lines, img_path=img_path, links_text=links
            )
    background_tasks.add_task(run_broadcast)
    return {"message": "Đang phát sóng bản tin lên Kênh Telegram..."}

# --- COOKIE MANAGEMENT ENDPOINTS ---

def parse_cookie_input(raw_text: str) -> list:
    """Hỗ trợ phân tích cả định dạng mảng JSON (từ Cookie-Editor) và chuỗi cookie c_user=...; xs=..."""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Nội dung cookie không được để trống!")

    # 1. Thử phân tích JSON
    if raw_text.startswith("[") or raw_text.startswith("{"):
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                if "cookies" in parsed and isinstance(parsed["cookies"], list):
                    parsed = parsed["cookies"]
                else:
                    parsed = [{"name": k, "value": str(v), "domain": ".facebook.com", "path": "/"} for k, v in parsed.items()]
            if isinstance(parsed, list):
                cleaned = []
                for item in parsed:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        cleaned.append({
                            "name": str(item["name"]),
                            "value": str(item["value"]),
                            "domain": item.get("domain", ".facebook.com"),
                            "path": item.get("path", "/"),
                            "secure": bool(item.get("secure", True)),
                            "sameSite": item.get("sameSite", "no_restriction")
                        })
                if cleaned:
                    return cleaned
        except json.JSONDecodeError:
            pass

    # 2. Thử phân tích dạng chuỗi Header: name=val; name2=val2
    items = []
    for part in raw_text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        items.append({
            "name": k.strip(),
            "value": v.strip(),
            "domain": ".facebook.com",
            "path": "/",
            "secure": True,
            "sameSite": "no_restriction"
        })
    if items:
        return items

    raise ValueError("Không nhận diện được định dạng Cookie. Vui lòng dán mảng JSON từ Cookie-Editor hoặc chuỗi cookie dạng 'c_user=...; xs=...'")

def get_account_cookie_info(acc_name: str, cookie_rel_path: str = None) -> dict:
    if not cookie_rel_path:
        cookie_rel_path = f"cookies/{acc_name}.json"
    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)
    
    info = {
        "account": acc_name,
        "cookie_file": cookie_rel_path,
        "exists": False,
        "count": 0,
        "c_user": None,
        "has_xs": False,
        "updated_at": None,
        "size_bytes": 0
    }
    if os.path.exists(full_path):
        info["exists"] = True
        info["size_bytes"] = os.path.getsize(full_path)
        info["updated_at"] = int(os.path.getmtime(full_path))
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                info["count"] = len(data)
                for item in data:
                    if isinstance(item, dict):
                        if item.get("name") == "c_user":
                            info["c_user"] = str(item.get("value"))
                        elif item.get("name") == "xs":
                            info["has_xs"] = True
        except Exception:
            pass
    return info

@app.get("/api/accounts/cookies")
def list_accounts_cookies():
    """Lấy trạng thái cookie của tất cả các nick cấu hình."""
    cfg = get_config()
    accs = cfg.get("accounts", [])
    result = []
    for a in accs:
        result.append(get_account_cookie_info(a["name"], a.get("cookie_file")))
    return result

@app.get("/api/accounts/{account_name}/cookie")
def get_account_cookie(account_name: str):
    """Lấy nội dung raw của cookie để hiển thị trên trình soạn thảo."""
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"
    info = get_account_cookie_info(account_name, cookie_rel_path)
    
    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)
    
    raw_content = ""
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_content = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            raw_content = f"Lỗi đọc file: {e}"
            
    return {**info, "raw_content": raw_content}

@app.post("/api/accounts/{account_name}/cookie")
def save_account_cookie(account_name: str, payload: CookieUpdate):
    """Lưu và chuẩn hóa cookie cho nick Facebook."""
    try:
        cookies_list = parse_cookie_input(payload.cookie_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"
    
    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, indent=2, ensure_ascii=False)

    info = get_account_cookie_info(account_name, cookie_rel_path)
    
    msg = f"Đã lưu thành công {info['count']} cookies cho {account_name}!"
    if info.get("c_user"):
        msg += f" (UID Facebook: {info['c_user']})"
    if not info.get("has_xs"):
        msg += " ⚠️ Chú ý: Chưa tìm thấy session 'xs', hãy đảm bảo nick đã đăng nhập Facebook."

    return {"message": msg, "info": info}

@app.delete("/api/accounts/{account_name}/cookie")
def delete_account_cookie(account_name: str):
    """Xóa file cookie của tài khoản."""
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"
    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        return {"message": f"Đã xóa file cookie của {account_name}"}
    return {"message": "File cookie không tồn tại"}

@app.post("/api/accounts/{account_name}/test-connect")
def test_facebook_connect(account_name: str):
    """Kiểm tra trực tiếp cookie Facebook có còn sống và đăng nhập được không qua tiến trình Playwright độc lập."""
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"
    
    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=400, detail=f"Chưa có file cookie cho tài khoản '{account_name}'. Hãy cập nhật cookie trước.")

    checker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "fb_checker.py")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [sys.executable, checker_script, full_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=35
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or "Tiến trình kiểm tra gặp lỗi không xác định."
            raise RuntimeError(err)

        output_str = proc.stdout.strip()
        if not output_str:
            raise RuntimeError("Không nhận được dữ liệu trả về từ trình duyệt kiểm tra.")

        data = json.loads(output_str)
        data["account"] = account_name
        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Lỗi phản hồi từ trình duyệt: {proc.stdout}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi kiểm tra kết nối Facebook: {str(e)}")

# --- SHOPEE AFFILIATE & CATEGORIES API ---

@app.get("/api/shopee/cookie")
def get_shopee_cookie_endpoint():
    """Lấy trạng thái và thông tin cookie Shopee Affiliate."""
    return shopee.get_shopee_cookie_info()

@app.post("/api/shopee/cookie")
def save_shopee_cookie_endpoint(payload: CookieUpdate):
    """Lưu và chuẩn hóa cookie Shopee Affiliate."""
    try:
        return shopee.save_shopee_cookie(payload.cookie_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@app.delete("/api/shopee/cookie")
def delete_shopee_cookie_endpoint():
    """Xóa file cookie Shopee Affiliate."""
    return shopee.delete_shopee_cookie()

@app.post("/api/shopee/test-connect")
def test_shopee_connect_endpoint():
    """Kiểm tra trực tiếp cookie Shopee có còn hoạt động không."""
    return shopee.test_shopee_connect()

@app.get("/api/shopee/categories")
def get_shopee_categories_endpoint():
    """Cào toàn bộ Cây Danh Mục Ngành Hàng chính thức từ Shopee."""
    cats = shopee.fetch_shopee_categories()
    return {"categories": cats, "total": len(cats)}

@app.post("/api/shopee/sync-niches")
def sync_shopee_niches_endpoint(payload: SyncNichesRequest):
    """Lưu các ngành hàng Shopee được chọn vào danh sách niches của bot trong config.yaml."""
    cfg = get_config()
    existing = set(cfg.get("niches", []))
    for n in payload.niches:
        if n and n.strip():
            existing.add(n.strip())
    cfg["niches"] = sorted(list(existing))
    save_config(cfg)
    return {"message": f"Đã đồng bộ {len(cfg['niches'])} ngành hàng vào cấu hình ngách (niches)!", "niches": cfg["niches"]}

# --- SHOPEE AFFILIATE PORTAL & OPEN API CONVERTER ---

@app.get("/api/shopee/affiliate-portal-cookie")
def get_shopee_aff_portal_cookie():
    """Lấy trạng thái cookie của cổng Shopee Affiliate Portal (affiliate.shopee.vn)."""
    return shopee_aff_converter.get_portal_cookie_info()

@app.post("/api/shopee/affiliate-portal-cookie")
def save_shopee_aff_portal_cookie(payload: CookieUpdate):
    """Lưu cookie của cổng Shopee Affiliate Portal (affiliate.shopee.vn)."""
    try:
        return shopee_aff_converter.save_portal_cookie(payload.cookie_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@app.delete("/api/shopee/affiliate-portal-cookie")
def delete_shopee_aff_portal_cookie():
    """Xóa cookie cổng Shopee Affiliate Portal."""
    return shopee_aff_converter.delete_portal_cookie()

@app.get("/api/shopee/open-api-config")
def get_shopee_open_api_config():
    """Lấy App ID và Secret của Shopee Open API."""
    return shopee_aff_converter.get_open_api_config()

@app.post("/api/shopee/open-api-config")
def save_shopee_open_api_config(payload: ShopeeOpenApiConfig):
    """Lưu cấu hình Shopee Open API vào config.yaml."""
    return shopee_aff_converter.save_open_api_config(payload.app_id, payload.secret)

@app.post("/api/shopee/test-convert")
def test_convert_shopee_link(payload: ShopeeTestConvertRequest):
    """Thử nghiệm tạo link affiliate (s.shopee.vn) từ link sản phẩm Shopee bất kỳ."""
    return shopee_aff_converter.convert_to_shopee_aff_link(payload.url, payload.sub_ids)

# --- FACEBOOK GROUP SCANNER & LEAVE GROUP ---

@app.post("/api/accounts/{account_name}/scan-groups")
def scan_joined_groups_endpoint(account_name: str):
    """Quét danh sách group Facebook mà tài khoản đã tham gia qua Playwright subprocess."""
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"

    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=400, detail=f"Chưa có file cookie cho tài khoản '{account_name}'. Hãy cập nhật cookie trước.")

    scanner_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "fb_groups_scanner.py")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [sys.executable, scanner_script, "scan", full_path, "--max-scroll", "15"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120  # Quét group cần thời gian cuộn trang
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or "Tiến trình quét gặp lỗi không xác định."
            raise RuntimeError(err)

        output_str = proc.stdout.strip()
        if not output_str:
            raise RuntimeError("Không nhận được dữ liệu trả về từ trình quét.")

        data = json.loads(output_str)
        data["account"] = account_name
        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Lỗi phản hồi từ trình duyệt: {proc.stdout}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi quét group: {str(e)}")

@app.post("/api/accounts/{account_name}/leave-group")
def leave_group_endpoint(account_name: str, payload: LeaveGroupRequest):
    """Rời khỏi một group Facebook qua Playwright subprocess."""
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"

    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=400, detail=f"Chưa có file cookie cho tài khoản '{account_name}'.")

    scanner_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "fb_groups_scanner.py")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [sys.executable, scanner_script, "leave", full_path, "--group-url", payload.group_url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=60
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or "Tiến trình rời nhóm gặp lỗi."
            raise RuntimeError(err)

        output_str = proc.stdout.strip()
        if not output_str:
            raise RuntimeError("Không nhận được dữ liệu trả về.")

        data = json.loads(output_str)
        data["account"] = account_name

        # Nếu rời nhóm thành công, cập nhật DB
        if data.get("success"):
            db.x("UPDATE groups SET status='skip' WHERE url=?", (payload.group_url,))

        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Lỗi phản hồi: {proc.stdout}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi rời nhóm: {str(e)}")

@app.delete("/api/groups/remove")
def remove_group_from_db(url: str = Query(...)):
    """Xóa một group khỏi database (chỉ xóa trong DB, không rời nhóm trên Facebook)."""
    existing = db.q("SELECT 1 FROM groups WHERE url=?", (url,), one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Group không tồn tại trong database.")
    db.x("DELETE FROM groups WHERE url=?", (url,))
    return {"message": f"Đã xóa group {url} khỏi database."}

@app.post("/api/groups/import-scanned")
def import_scanned_groups_endpoint(payload: ImportGroupsRequest):
    """Nhập các group đã quét vào cơ sở dữ liệu."""
    added = 0
    updated = 0
    for g in payload.groups:
        existing = db.q("SELECT 1 FROM groups WHERE url=?", (g.url,), one=True)
        if existing:
            db.x("UPDATE groups SET name=COALESCE(NULLIF(name, ''), ?), account=COALESCE(NULLIF(?, ''), account), status=? WHERE url=?",
                 (g.name or "Group Facebook", g.account or "", g.status or "joined", g.url))
            updated += 1
        else:
            db.x("INSERT INTO groups(url, name, niche, kind, status, account, allow_link, priority_score) VALUES(?,?,?,?,?,?,?,?)",
                 (g.url, g.name or "Group Facebook", g.niche or "săn sale", g.kind or "dealhunt", g.status or "joined", g.account or "", 1, 100.0))
            added += 1
    return {"message": f"Đã nhập thành công! Thêm mới {added} nhóm, cập nhật {updated} nhóm.", "added": added, "updated": updated}



