"""FastAPI Backend Server cho Dealbot Frontend (Angular + NG-ZORRO).
Cung cấp REST API đầy đủ để quản trị Deals, Groups, Lịch đăng, Coupons, Cấu hình và Báo cáo.
"""
import os, sys, time, yaml, threading
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import db
from modules import groups, deals, planner, poster, coupons, telegram_channel
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

class EventItem(BaseModel):
    title: str
    merchant: str = "shopee"
    start: str
    end: str
    detail: Optional[str] = ""
    link: str

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
def trigger_crawl_deals(background_tasks: BackgroundTasks):
    """Kích hoạt cào deal mới từ Accesstrade."""
    def run_crawl():
        cfg = get_config()
        deals.refresh(cfg)
    background_tasks.add_task(run_crawl)
    return {"message": "Đang cào deal trong tiến trình nền..."}

@app.get("/api/groups")
def list_groups(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    niche: Optional[str] = None,
    search: Optional[str] = None
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
