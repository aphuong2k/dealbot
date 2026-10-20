"""FastAPI Backend Server cho Dealbot Frontend (Angular + NG-ZORRO).
Cung cấp REST API đầy đủ để quản trị Deals, Groups, Lịch đăng, Coupons, Cấu hình và Báo cáo.
"""
import os, sys, time, yaml, threading, json, subprocess
from typing import Optional, List, Dict, Any

if sys.platform == "win32":
    import asyncio
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import db
from modules import groups, deals, planner, poster, coupons, telegram_channel, shopee, shopee_aff_converter, lazada, fb_market_scanner, lazada_hunter, lazada_general_scanner
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
    target_type: Optional[str] = None
    niche: Optional[str] = None
    kind: Optional[str] = None

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

class JoinGroupRequest(BaseModel):
    group_url: str

class BatchJoinGroupsRequest(BaseModel):
    account: str
    group_urls: Optional[List[str]] = None
    limit: Optional[int] = 5

class BlacklistCleanRequest(BaseModel):
    auto_leave_fb: Optional[bool] = True
    max_groups: Optional[int] = 5

class BlacklistBanRequest(BaseModel):
    group_url: str
    reason: Optional[str] = "Chặn và rời nhóm thủ công bởi người dùng"
    auto_leave_fb: Optional[bool] = True
    account: Optional[str] = None

class BlacklistUnbanRequest(BaseModel):
    group_url: str
    new_status: Optional[str] = "candidate"

class BlacklistConfigUpdate(BaseModel):
    auto_clean_enabled: Optional[bool] = None
    clean_interval_hours: Optional[int] = None
    auto_leave_fb: Optional[bool] = None
    max_leaves_per_run: Optional[int] = None
    consecutive_fails_threshold: Optional[int] = None
    pending_approval_threshold: Optional[int] = None

class TestPostRequest(BaseModel):
    account: str
    group_url: str
    caption: str
    comment: Optional[str] = ""
    dry_run: bool = False
    image_path: Optional[str] = None

class StartGradualPostRequest(BaseModel):
    group_urls: Optional[List[str]] = None
    delay_seconds: Optional[int] = 60
    account: Optional[str] = None
    dry_run: Optional[bool] = False
    link_in_comment: Optional[bool] = False

class SingleGroupPostRequest(BaseModel):
    group_url: str
    deal_id: Optional[str] = None
    account: Optional[str] = None
    dry_run: Optional[bool] = False
    custom_caption: Optional[str] = None
    link_in_comment: Optional[bool] = False


class ImportGroupItem(BaseModel):
    url: str
    name: Optional[str] = ""
    account: Optional[str] = ""
    status: Optional[str] = "joined"
    kind: Optional[str] = "dealhunt"
    niche: Optional[str] = "săn sale"
    members: Optional[int] = 0
    posts_per_day: Optional[float] = 0.0
    activity_text: Optional[str] = ""
    privacy: Optional[str] = "public"
    priority_score: Optional[float] = 100.0
    target_type: Optional[str] = "posting"

class ImportGroupsRequest(BaseModel):
    groups: List[ImportGroupItem]

class LazadaHunterGroupPayload(BaseModel):
    url: str
    name: Optional[str] = ""

class SearchNicheGroupsRequest(BaseModel):
    account: str
    keyword: str
    niche: Optional[str] = ""
    min_members: Optional[int] = 5000
    min_posts_per_day: Optional[float] = 3.0
    only_public: Optional[bool] = True
    auto_join: Optional[bool] = False
    max_results: Optional[int] = 15
    max_scroll: Optional[int] = 6

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
    posted_deals = db.q("SELECT COUNT(*) c FROM deals WHERE status='posted'", one=True)["c"]

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
            "new": new_deals,
            "posted": posted_deals
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
    is_vip: Optional[bool] = None,
    is_mall: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
):
    """Danh sách deals cào được, kèm thông tin bài viết đã đăng."""
    sql = """
        SELECT d.*,
               (SELECT COUNT(*) FROM posts p WHERE p.deal_id=d.id AND p.status='done') AS posts_done_count,
               (SELECT p.post_url FROM posts p WHERE p.deal_id=d.id AND p.status='done' AND p.post_url IS NOT NULL ORDER BY p.posted_at DESC LIMIT 1) AS latest_post_url,
               (SELECT g.name FROM posts p JOIN groups g ON p.group_url=g.url WHERE p.deal_id=d.id AND p.status='done' ORDER BY p.posted_at DESC LIMIT 1) AS latest_group_name
        FROM deals d WHERE 1=1
    """
    args = []
    if niche:
        sql += " AND LOWER(d.niche)=LOWER(?)"
        args.append(niche)
    if status:
        sql += " AND d.status=?"
        args.append(status)
    if is_vip is True:
        sql += " AND d.is_vip=1"
    if is_mall is True:
        sql += " AND d.is_mall=1"
    if search:
        sql += " AND d.title LIKE ?"
        args.append(f"%{search}%")

    sql += " ORDER BY d.score DESC, d.created_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])

    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.get("/api/deals/vip")
def list_vip_deals(limit: int = 40):
    """Danh sách deal Shopee VIP / Shopee Mall chính hãng điểm cao nhất."""
    sql = """
        SELECT d.*,
               (SELECT COUNT(*) FROM posts p WHERE p.deal_id=d.id AND p.status='done') AS posts_done_count,
               (SELECT p.post_url FROM posts p WHERE p.deal_id=d.id AND p.status='done' AND p.post_url IS NOT NULL ORDER BY p.posted_at DESC LIMIT 1) AS latest_post_url,
               (SELECT g.name FROM posts p JOIN groups g ON p.group_url=g.url WHERE p.deal_id=d.id AND p.status='done' ORDER BY p.posted_at DESC LIMIT 1) AS latest_group_name
        FROM deals d WHERE (d.is_vip=1 OR d.is_mall=1) AND d.is_valid=1
        ORDER BY d.score DESC, d.sold DESC, d.created_at DESC LIMIT ?
    """
    rows = db.q(sql, (limit,))
    return [dict(r) for r in rows]

class CrawlDealsRequest(BaseModel):
    niche: Optional[str] = None

class CleanupDealsRequest(BaseModel):
    delete_from_db: bool = True

@app.post("/api/deals/crawl")
def trigger_crawl_deals(payload: Optional[CrawlDealsRequest] = None, niche: Optional[str] = Query(None)):
    """Kích hoạt cào deal mới từ Shopee (Flash Sale & Ngành hàng) và Accesstrade."""
    target_niche = (payload.niche if payload and payload.niche else None) or niche
    if target_niche and target_niche.lower() in ("all", "tất cả", ""):
        target_niche = None

    cfg = get_config()
    res = deals.refresh(cfg, target_niche=target_niche)
    added, updated = res if isinstance(res, tuple) else (res, 0)

    niche_label = f"ngành '{target_niche}'" if target_niche else "tất cả ngành"
    return {
        "success": True,
        "message": f"Cào deal thành công cho {niche_label}: +{added} deal mới, cập nhật {updated} deal!",
        "added": added,
        "updated": updated,
        "niche": target_niche
    }

@app.post("/api/deals/cleanup")
def trigger_cleanup_deals(payload: Optional[CleanupDealsRequest] = None):
    """
    Quét lại toàn bộ các deal đang lưu trong cơ sở dữ liệu:
    - Kiểm tra đối chiếu với danh sách Flash Sale hiện thời của Shopee.
    - Kiểm tra link sản phẩm xem có còn sale, bị xóa (404/410/redirect) hay hết hàng không.
    - Tự động xóa khỏi DB và giải phóng dung lượng nếu không còn sale / hết hàng.
    """
    delete_from_db = payload.delete_from_db if payload else True
    cfg = get_config()
    res = deals.cleanup_expired_deals(cfg, delete_from_db=delete_from_db)
    return res

@app.post("/api/deals/convert-aff")
def trigger_convert_all_deals_aff(limit: int = 50, only_unconverted: bool = False):
    """Chuyển đổi link các deal trong DB sang shortlink s.shopee.vn chuẩn (Playwright Portal / Open API)."""
    updated = deals.convert_all_deals_to_aff(limit=limit, only_unconverted=only_unconverted)
    return {"success": True, "updated": updated, "message": f"Đã chuyển đổi {updated} deal sang shortlink s.shopee.vn thành công!"}

@app.delete("/api/deals")
def clear_all_deals():
    """Xóa toàn bộ danh sách deal Shopee trong kho dữ liệu."""
    count_row = db.q("SELECT count(*) as c FROM deals", one=True)
    total = count_row["c"] if count_row else 0
    db.x("DELETE FROM deals")
    return {"success": True, "message": f"Đã xóa toàn bộ {total} deal khỏi kho dữ liệu thành công!", "deleted": total}

@app.delete("/api/deals/{deal_id}")
def delete_single_deal(deal_id: str):
    """Xóa 1 deal Shopee cụ thể khỏi kho dữ liệu."""
    db.x("DELETE FROM deals WHERE id = ?", (deal_id,))
    return {"success": True, "message": f"Đã xóa deal #{deal_id} khỏi kho dữ liệu."}

# --- TRẠNG THÁI TIẾN TRÌNH LUỒNG TUẦN TỰ (PIPELINE) ---
_pipeline_status: Dict[str, Any] = {
    "is_running": False,
    "step": 0,               # 0: idle, 1: crawling, 2: planning, 3: posting, 4: done
    "step_name": "",         # "Cào deal", "Lập lịch phân bổ", "Đăng bài Playwright", "Hoàn tất"
    "started_at": 0,
    "deals_added": 0,
    "deals_updated": 0,
    "posts_planned": 0,
    "posts_done": 0,
    "message": "Sẵn sàng",
    "last_finished_at": 0,
    "last_result": None,
    "error": None
}

class PipelineAutoConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_hours: Optional[int] = None
    auto_post_due: Optional[bool] = None

def get_pipeline_auto_config() -> Dict[str, Any]:
    cfg = get_config()
    p_cfg = cfg.get("pipeline_auto", {})
    last_run = _pipeline_status.get("last_finished_at", 0)
    int_h = int(p_cfg.get("interval_hours", 2))
    next_run = (last_run + int_h * 3600) if last_run > 0 else 0
    return {
        "enabled": bool(p_cfg.get("enabled", True)),
        "interval_hours": int_h,
        "auto_post_due": bool(p_cfg.get("auto_post_due", True)),
        "last_run_at": last_run,
        "next_run_at": next_run
    }

def save_pipeline_auto_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    cfg = get_config()
    p_cfg = cfg.get("pipeline_auto", {})
    p_cfg.update(updates)
    cfg["pipeline_auto"] = p_cfg
    save_config(cfg)
    return get_pipeline_auto_config()

def get_pipeline_status() -> Dict[str, Any]:
    global _pipeline_status
    st = dict(_pipeline_status)
    if st["is_running"] and st["started_at"] > 0:
        st["elapsed_seconds"] = int(time.time() - st["started_at"])
    else:
        st["elapsed_seconds"] = 0
    auto_cfg = get_pipeline_auto_config()
    st["auto_enabled"] = auto_cfg.get("enabled", True)
    st["interval_hours"] = auto_cfg.get("interval_hours", 2)
    st["next_run_at"] = auto_cfg.get("next_run_at", 0)
    return st

def _run_pipeline_worker():
    global _pipeline_status
    cfg = get_config()
    start_time = time.time()
    _pipeline_status.update({
        "is_running": True,
        "step": 1,
        "step_name": "Cào deal mới",
        "started_at": start_time,
        "message": "Bước 1/3: Đang cào deal từ Shopee & Accesstrade...",
        "deals_added": 0,
        "deals_updated": 0,
        "posts_planned": 0,
        "posts_done": 0,
        "error": None
    })

    try:
        # Bước 1: Cào deal
        try:
            print("[pipeline] 🛒 Bước 1/3: Đang cào deal...")
        except Exception:
            pass
        res = deals.refresh(cfg)
        added, updated = res if isinstance(res, tuple) else (res, 0)
        _pipeline_status["deals_added"] = added
        _pipeline_status["deals_updated"] = updated

        # Bước 2: Lập lịch phân bổ
        _pipeline_status["step"] = 2
        _pipeline_status["step_name"] = "Lập lịch phân bổ"
        _pipeline_status["message"] = f"Bước 2/3: Đang lập lịch phân bổ ({added} deal mới, {updated} cập nhật)..."
        try:
            print("[pipeline] 🗓 Bước 2/3: Đang lập lịch phân bổ...")
        except Exception:
            pass
        plan_deals = planner.plan_day(cfg)
        plan_digests = planner.plan_digests(cfg)
        total_planned = plan_deals + plan_digests
        _pipeline_status["posts_planned"] = total_planned

        # Bước 3: Đăng bài qua Playwright
        _pipeline_status["step"] = 3
        _pipeline_status["step_name"] = "Đăng bài qua Playwright"
        _pipeline_status["message"] = f"Bước 3/3: Đang mở Playwright đăng bài & comment vào các nhóm Facebook..."
        try:
            print("[pipeline] 🚀 Bước 3/3: Đang khởi chạy Playwright đăng bài...")
        except Exception:
            pass
        poster.run_due(cfg)

        finish_time = time.time()
        dur = int(finish_time - start_time)
        res_msg = f"Đã hoàn thành luồng tuần tự trong {dur}s (+{added} deal, {total_planned} bài lên lịch & đăng bài)!"
        _pipeline_status.update({
            "step": 4,
            "step_name": "Hoàn tất",
            "message": res_msg,
            "last_finished_at": finish_time,
            "last_result": res_msg
        })
        try:
            print(f"[pipeline] ✅ {res_msg}")
        except Exception:
            pass

    except Exception as e:
        err_msg = f"Lỗi luồng tuần tự: {e}"
        try:
            print(f"[pipeline] ❌ {err_msg}")
        except Exception:
            pass
        _pipeline_status["error"] = str(e)
        _pipeline_status["message"] = err_msg
        _pipeline_status["step_name"] = "Gặp lỗi"
    finally:
        _pipeline_status["is_running"] = False

@app.post("/api/pipeline/run-all")
def trigger_run_full_pipeline(background_tasks: BackgroundTasks):
    """Khởi chạy toàn bộ luồng tự động 1-chạm trong nền: Cào deal -> Lập lịch phân bổ bài -> Đăng bài ngay."""
    global _pipeline_status
    if _pipeline_status.get("is_running"):
        return {
            "success": False,
            "message": "Luồng tuần tự hiện đang chạy! Bạn có thể xem tiến độ trực tiếp trên thanh điều hướng hoặc trang Tổng quan.",
            "is_running": True
        }

    t = threading.Thread(target=_run_pipeline_worker, daemon=True, name="PipelineWorker")
    t.start()

    return {
        "success": True,
        "message": "🚀 Đã kích hoạt toàn bộ luồng tuần tự trong nền! Hệ thống đang cào deal, phân bổ và đăng bài.",
        "is_running": True
    }

@app.get("/api/pipeline/status")
def get_pipeline_status_endpoint():
    """Xem trạng thái trực tiếp của luồng tuần tự."""
    return get_pipeline_status()

@app.get("/api/pipeline/config")
def get_pipeline_config_endpoint():
    """Lấy cấu hình tự động chạy của Luồng Tuần Tự."""
    return get_pipeline_auto_config()

@app.post("/api/pipeline/config")
def update_pipeline_config_endpoint(req: PipelineAutoConfigRequest):
    """Cập nhật cấu hình tự động chạy của Luồng Tuần Tự."""
    updates = {k: v for k, v in req.dict().items() if v is not None}
    saved = save_pipeline_auto_config(updates)
    return {"success": True, "message": "Đã lưu cấu hình tự động Luồng Tuần Tự thành công!", "config": saved}

@app.get("/api/lazada/hunter-status")
def get_lazada_hunter_status_endpoint():
    """Xem trạng thái trực tiếp của luồng quét deal Lazada."""
    return lazada_hunter.get_hunter_status()

class DeepDropsScanRequest(BaseModel):
    categories: Optional[List[str]] = None
    min_drop_pct: Optional[float] = 50.0

@app.get("/api/tasks/status")
def get_tasks_status_endpoint():
    """Tổng hợp trạng thái của cả các luồng: Luồng tuần tự, Luồng săn deal Lazada (theo dõi), Radar Sập sàn toàn sàn, và Radar Tmall Brand."""
    return {
        "pipeline": get_pipeline_status(),
        "lazada_hunter": lazada_hunter.get_hunter_status(),
        "lazada_general": lazada_general_scanner.get_general_scanner_status(),
        "lazada_tmall": lazada_general_scanner.get_tmall_brand_scanner_status()
    }

@app.get("/api/lazada/deep-drops/status")
def get_deep_drops_status_endpoint():
    """Trạng thái trực tiếp của Radar Săn Kèo Sập Sàn Toàn Sàn."""
    return lazada_general_scanner.get_general_scanner_status()

@app.post("/api/lazada/deep-drops/scan")
def trigger_deep_drops_scan(payload: Optional[DeepDropsScanRequest] = None):
    """Kích hoạt Radar quét tổng quát Sập sàn LazMall / Tmall đa ngành hàng trong nền."""
    st = lazada_general_scanner.get_general_scanner_status()
    if st.get("is_running"):
        return {
            "success": False,
            "message": "Radar quét tổng quát Sập sàn hiện đang chạy! Vui lòng theo dõi thanh tiến trình.",
            "is_running": True
        }
    cats = payload.categories if payload else None
    min_pct = payload.min_drop_pct if payload and payload.min_drop_pct else 50.0

    def _worker():
        lazada_general_scanner.run_general_scanner_cycle(
            selected_categories=cats,
            min_drop_pct=min_pct
        )

    t = threading.Thread(target=_worker, daemon=True, name="LazadaGeneralScannerWorker")
    t.start()

    return {
        "success": True,
        "message": "🚀 Đã kích hoạt Radar Quét Tổng Quát Sập Sàn Tmall/LazMall trong nền!",
        "is_running": True
    }

@app.get("/api/lazada/deep-drops")
def list_deep_drops(
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Lấy danh sách các deal sập sàn phân loại / Tmall deep drops đã quét được."""
    sql = "SELECT * FROM lazada_deep_drops WHERE 1=1"
    args = []
    if category and category.lower() not in ("all", "tất cả", ""):
        sql += " AND category = ?"
        args.append(category)
    sql += " ORDER BY drop_pct DESC, created_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.get("/api/lazada/deep-drops/logs")
def list_deep_drops_logs(limit: int = 50):
    """Lấy lịch sử các lần quét sập sàn tổng quát."""
    rows = db.q("SELECT * FROM lazada_deep_drops_logs ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]

@app.delete("/api/lazada/deep-drops/logs")
def clear_deep_drops_logs():
    """Xóa toàn bộ nhật ký quét sập sàn."""
    db.x("DELETE FROM lazada_deep_drops_logs")
    return {"success": True, "message": "Đã xóa toàn bộ lịch sử log radar sập sàn."}

@app.delete("/api/lazada/deep-drops/{drop_id}")
def delete_single_deep_drop(drop_id: int):
    """Xóa 1 deal sập sàn."""
    db.x("DELETE FROM lazada_deep_drops WHERE id = ?", (drop_id,))
    return {"success": True, "message": f"Đã xóa deal sập sàn #{drop_id}."}

@app.delete("/api/lazada/deep-drops")
def clear_deep_drops():
    """Xóa danh sách deal sập sàn."""
    db.x("DELETE FROM lazada_deep_drops")
    return {"success": True, "message": "Đã xóa toàn bộ lịch sử deal sập sàn."}

class LazadaGeneralConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = None
    min_drop_pct: Optional[float] = None
    min_price_floor: Optional[float] = None
    batch_keywords_per_cycle: Optional[int] = None
    filter_mall_only: Optional[bool] = None

@app.get("/api/lazada/deep-drops/config")
def get_deep_drops_config():
    """Lấy cấu hình Radar quét sập sàn."""
    return lazada_general_scanner.get_general_scanner_config()

@app.post("/api/lazada/deep-drops/config")
def update_deep_drops_config(req: LazadaGeneralConfigUpdate):
    """Cập nhật cấu hình Radar quét sập sàn."""
    payload = {k: v for k, v in req.dict().items() if v is not None}
    saved = lazada_general_scanner.save_general_scanner_config(payload)
    return {"success": True, "config": saved}

class LazadaRadarCategoryPayload(BaseModel):
    id: Optional[str] = None
    name: str
    icon: Optional[str] = "🏷️"
    keywords: List[str] = []
    is_active: Optional[bool] = True
    sort_order: Optional[int] = 0

@app.get("/api/lazada/categories")
def get_lazada_radar_categories_endpoint(active_only: bool = False):
    """Lấy danh sách các ngành hàng và kho từ khóa của Radar Săn Sập Sàn."""
    cats = lazada_general_scanner.get_radar_categories(active_only=active_only)
    total_kws = sum(c["keywords_count"] for c in cats)
    return {
        "categories": cats,
        "total_categories": len(cats),
        "total_keywords": total_kws
    }

@app.post("/api/lazada/categories")
def save_lazada_radar_category_endpoint(payload: LazadaRadarCategoryPayload):
    """Thêm mới hoặc cập nhật một ngành hàng và danh sách từ khóa trong Radar."""
    cat_id = payload.id.strip() if payload.id and payload.id.strip() else f"cat_{int(time.time())}"
    res = lazada_general_scanner.save_radar_category(
        cat_id=cat_id,
        name=payload.name.strip(),
        icon=payload.icon.strip() if payload.icon else "🏷️",
        keywords=payload.keywords,
        is_active=payload.is_active if payload.is_active is not None else True,
        sort_order=payload.sort_order or 0
    )
    return {"success": True, "message": f"Đã lưu ngành hàng '{payload.name}' thành công!", "category": res}

@app.delete("/api/lazada/categories/{cat_id}")
def delete_lazada_radar_category_endpoint(cat_id: str):
    """Xóa một ngành hàng khỏi radar."""
    lazada_general_scanner.delete_radar_category(cat_id)
    return {"success": True, "message": f"Đã xóa ngành hàng #{cat_id} khỏi Radar."}

@app.post("/api/lazada/categories/sync")
def sync_lazada_categories_endpoint():
    """Tự động cào danh mục mới nhất trực tiếp từ Lazada Việt Nam và mở rộng kho từ khóa."""
    return lazada_general_scanner.sync_lazada_official_categories()

@app.post("/api/lazada/categories/reset-default")
def reset_lazada_categories_endpoint():
    """Khôi phục kho từ khóa Radar về bộ chuẩn 13 ngành / 260 từ khóa."""
    cats = lazada_general_scanner.reset_radar_categories_to_default()
    total_kws = sum(c["keywords_count"] for c in cats)
    return {
        "success": True,
        "message": f"Đã khôi phục kho từ khóa chuẩn 13 ngành ({total_kws} từ khóa)!",
        "categories": cats,
        "total_categories": len(cats),
        "total_keywords": total_kws
    }

# --- TMALL BRAND DIRECTORY & SHOP SCANNER ENDPOINTS ---
class TmallCategoryToggleRequest(BaseModel):
    category_id: str
    is_active: bool

class TmallBrandScanRequest(BaseModel):
    categories: Optional[List[str]] = None
    min_drop_pct: Optional[float] = None
    batch_shops: Optional[int] = None
    max_pages: Optional[int] = 1

@app.get("/api/lazada/tmall/categories")
def get_tmall_categories_endpoint(active_only: bool = False):
    """Lấy danh sách các nhóm ngành Tmall Brand (kèm số lượng shop & deal sập sàn)."""
    cats = lazada_general_scanner.get_tmall_categories(active_only=active_only)
    return {
        "categories": cats,
        "total_categories": len(cats),
        "active_categories": len([c for c in cats if c.get("is_active")])
    }

@app.post("/api/lazada/tmall/categories/toggle")
def toggle_tmall_category_endpoint(payload: TmallCategoryToggleRequest):
    """Bật/tắt quét một nhóm ngành Tmall Brand."""
    return lazada_general_scanner.toggle_tmall_category(payload.category_id, payload.is_active)

@app.get("/api/lazada/tmall/shops")
def get_tmall_shops_endpoint(category_id: Optional[str] = None, active_only: bool = False, limit: int = 300):
    """Lấy danh sách các shop thuộc nhóm ngành Tmall Brand."""
    shops = lazada_general_scanner.get_tmall_shops(category_id=category_id, active_only=active_only, limit=limit)
    return {
        "shops": shops,
        "total": len(shops)
    }

@app.post("/api/lazada/tmall/sync-brands")
def sync_tmall_brands_endpoint():
    """Đồng bộ live danh mục Brand Tmall và các shop mới nhất từ Lazada."""
    return lazada_general_scanner.sync_tmall_brands_directory()

@app.get("/api/lazada/tmall/status")
def get_tmall_brand_scanner_status_endpoint():
    """Lấy trạng thái trực tiếp của luồng quét Tmall Brand."""
    return lazada_general_scanner.get_tmall_brand_scanner_status()

@app.post("/api/lazada/tmall/scan")
def trigger_tmall_brand_scan_endpoint(payload: Optional[TmallBrandScanRequest] = None):
    """Kích hoạt Radar quét lần lượt các shop và sản phẩm Tmall Brand theo nhóm ngành."""
    st = lazada_general_scanner.get_tmall_brand_scanner_status()
    if st.get("is_running"):
        return {
            "success": False,
            "message": "Radar quét Tmall Brand hiện đang chạy! Vui lòng theo dõi thanh tiến trình.",
            "is_running": True
        }
    cats = payload.categories if payload else None
    min_pct = payload.min_drop_pct if payload and payload.min_drop_pct else None
    batch_shops = payload.batch_shops if payload and payload.batch_shops else None
    max_pages = payload.max_pages if payload and payload.max_pages else 1

    def _tmall_worker():
        lazada_general_scanner.run_tmall_brands_scan_cycle(
            trigger_type="manual",
            selected_category_ids=cats,
            batch_shops_per_cycle=batch_shops,
            min_drop_pct=min_pct,
            max_pages_per_shop=max_pages
        )

    t = threading.Thread(target=_tmall_worker, daemon=True, name="LazadaTmallBrandScannerWorker")
    t.start()

    return {
        "success": True,
        "message": "🚀 Đã kích hoạt Radar Quét Shop Tmall Brand theo nhóm ngành trong nền!",
        "is_running": True
    }

@app.post("/api/lazada/tmall/continuous/start")
def start_tmall_continuous_endpoint(payload: Optional[TmallBrandScanRequest] = None):
    """Bắt đầu luồng quét lần lượt toàn bộ các nhóm ngành và lặp lại liên tục ngày đêm."""
    cats = payload.categories if payload else None
    min_pct = payload.min_drop_pct if payload and payload.min_drop_pct else None
    max_pages = payload.max_pages if payload and payload.max_pages else 1
    return lazada_general_scanner.start_tmall_continuous_runner(
        selected_category_ids=cats,
        min_drop_pct=min_pct,
        max_pages_per_shop=max_pages
    )

@app.post("/api/lazada/tmall/continuous/stop")
def stop_tmall_continuous_endpoint():
    """Dừng luồng quét lần lượt các nhóm ngành liên tục."""
    return lazada_general_scanner.stop_tmall_continuous_runner()



@app.get("/api/groups")
def list_groups(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    niche: Optional[str] = None,
    search: Optional[str] = None,
    account: Optional[str] = None,
    target_type: Optional[str] = None
):
    """Danh sách hội nhóm Facebook, có lọc theo target_type (posting hoặc lazada_hunter)."""
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
    if target_type:
        sql += " AND target_type=?"
        args.append(target_type)
    if search:
        sql += " AND (name LIKE ? OR url LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])

    sql += " ORDER BY priority_score DESC, fail_count ASC"
    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.put("/api/groups")
def update_group(url: str = Query(...), payload: GroupUpdate = ...):
    """Cập nhật trạng thái duyệt group, gán nick, điểm ưu tiên hoặc mục đích target_type."""
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
    if payload.target_type is not None:
        updates.append("target_type=?")
        args.append(payload.target_type)
    if payload.niche is not None:
        updates.append("niche=?")
        args.append(payload.niche)
    if payload.kind is not None:
        updates.append("kind=?")
        args.append(payload.kind)

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

@app.post("/api/posts/test")
def test_post_endpoint(payload: TestPostRequest):
    """Kiểm tra và test đăng bài Facebook trực tiếp, trả về kết quả & link bài đăng."""
    cfg = get_config()
    res = poster.test_post(
        cfg=cfg,
        account_name=payload.account,
        group_url=payload.group_url,
        caption=payload.caption,
        comment=payload.comment or "",
        dry_run=payload.dry_run,
        image_path=payload.image_path
    )
    return res

@app.get("/api/posts/gradual-status")
def get_gradual_status():
    """Lấy trạng thái chu trình đăng bài dần."""
    return poster.get_gradual_posting_status()

@app.post("/api/posts/start-gradual")
def start_gradual_posting_endpoint(req: StartGradualPostRequest):
    """Khởi chạy chu trình đăng bài dần vào các nhóm theo nhịp nghỉ an toàn."""
    status = poster.get_gradual_posting_status()
    if status.get("is_running"):
        return {"success": False, "message": "Chu trình đăng bài đang chạy!", "state": status}

    cfg = get_config()
    delay = req.delay_seconds if req.delay_seconds and req.delay_seconds > 0 else 60

    def _worker():
        poster.run_gradual_posting(
            cfg=cfg,
            group_urls=req.group_urls,
            delay_seconds=delay,
            account_name=req.account,
            dry_run=bool(req.dry_run),
            link_in_comment=bool(req.link_in_comment) if req.link_in_comment is not None else False
        )

    t = threading.Thread(target=_worker, daemon=True, name="GradualPosterWorker")
    t.start()

    target_count = len(req.group_urls) if req.group_urls else "toàn bộ"
    return {
        "success": True,
        "message": f"🚀 Đã khởi động chu trình đăng tuần tự vào {target_count} nhóm (nhịp nghỉ {delay}s)!",
        "state": poster.get_gradual_posting_status()
    }

@app.post("/api/posts/stop-gradual")
def stop_gradual_posting_endpoint():
    """Dừng chu trình đăng bài dần."""
    return poster.stop_gradual_posting()

@app.post("/api/groups/post-single")
def post_single_group_endpoint(req: SingleGroupPostRequest):
    """Đăng bài ngay lập tức vào một nhóm Facebook cụ thể (Chỉ nhóm Đăng Bài)."""
    cfg = get_config()
    res = poster.post_single_group(
        cfg=cfg,
        group_url=req.group_url,
        deal_id=req.deal_id,
        account_name=req.account,
        dry_run=bool(req.dry_run),
        custom_caption=req.custom_caption,
        link_in_comment=bool(req.link_in_comment) if req.link_in_comment is not None else False
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Lỗi khi đăng bài."))
    return res

@app.get("/api/groups/matched-deals")
def get_matched_deals_endpoint():
    """Lấy danh sách sản phẩm khớp chuẩn theo ngành hàng cho toàn bộ nhóm Facebook."""
    return poster.get_group_matched_deals()


@app.get("/api/posts/history")
def list_posts_history(account: Optional[str] = None, limit: int = 50, offset: int = 0):
    """Lấy danh sách lịch sử các bài viết đã đăng (Thành công, Chờ duyệt, Thất bại, Bỏ qua)."""
    sql = """
        SELECT p.*, g.name as group_name 
        FROM posts p 
        LEFT JOIN groups g ON p.group_url = g.url 
        WHERE (p.status IN ('done', 'failed', 'skipped', 'pending_approval') OR p.posted_at > 0)
    """
    args = []
    if account:
        sql += " AND p.account = ?"
        args.append(account)
    sql += " ORDER BY COALESCE(NULLIF(p.posted_at, 0), p.scheduled_at) DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.delete("/api/posts/history")
def clear_posts_history():
    """Xóa toàn bộ lịch sử các bài viết đã đăng xong / lỗi / bỏ qua (không xóa các bài queued đang chờ)."""
    deleted = db.x("DELETE FROM posts WHERE status IN ('done', 'failed', 'skipped')")
    return {"success": True, "message": f"Đã dọn dẹp {deleted} bài viết trong lịch sử đăng bài.", "deleted": deleted}

@app.delete("/api/posts/{post_id}")
def delete_single_post(post_id: int):
    """Xóa 1 bài viết khỏi hàng đợi hoặc lịch sử."""
    db.x("DELETE FROM posts WHERE id = ?", (post_id,))
    return {"success": True, "message": f"Đã xóa bài viết #{post_id}."}

@app.get("/api/coupons")
def list_coupons(category: Optional[str] = None):
    """Danh sách mã giảm giá & voucher active, hỗ trợ lọc theo nhóm ngành/loại mã."""
    sql = "SELECT * FROM coupons WHERE 1=1"
    args = []
    if category and category.lower() not in ("all", "tất cả", ""):
        sql += " AND category=?"
        args.append(category.lower())
    sql += " ORDER BY category ASC, end_at ASC LIMIT 80"
    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

@app.get("/api/coupons/campaigns")
def list_campaigns():
    """Danh sách các chương trình Sale & Khung giờ vàng hôm nay của Shopee (tự động gắn link Affiliate)."""
    return shopee.get_daily_sale_campaigns()

@app.post("/api/coupons/refresh")
def trigger_refresh_coupons():
    """Quét và tổng hợp mới toàn bộ Voucher Shopee VIP, Khung giờ Sale và link lưu mã hôm nay."""
    added = coupons.refresh()
    active_count = len(coupons.active(limit=100))
    return {
        "success": True,
        "message": f"Đã quét & tổng hợp thành công {active_count} mã giảm giá Shopee VIP hôm nay (thêm mới {added} mã) kèm link lưu mã Affiliate!",
        "added": added,
        "active_count": active_count
    }

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

        # Nếu rời nhóm thành công, cập nhật DB vào Danh Sách Đen (Banned)
        if data.get("success"):
            now_str = time.strftime("%d/%m/%Y %H:%M")
            db.x("""UPDATE groups SET 
                    status='banned', 
                    priority_score=0.0, 
                    consecutive_fails=MAX(consecutive_fails, 3), 
                    last_error=? 
                    WHERE url=?""", (f"🚫 ĐÃ RỜI NHÓM & VÀO DS ĐEN [{now_str}] (Thao tác thủ công)", payload.group_url))

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
    """Nhập các group đã quét vào cơ sở dữ liệu kèm đầy đủ chỉ số tương tác."""
    added = 0
    updated = 0
    for g in payload.groups:
        existing = db.q("SELECT status FROM groups WHERE url=?", (g.url,), one=True)
        t_type = g.target_type or "posting"
        if existing:
            # BẢO VỆ TUYỆT ĐỐI: Không bao giờ cho phép nhập đè làm sống lại nhóm đã bị Blacklist!
            if existing.get("status") == "banned":
                continue
            db.x("""UPDATE groups SET 
                    name=COALESCE(NULLIF(name, ''), ?), 
                    account=COALESCE(NULLIF(?, ''), account), 
                    status=?,
                    niche=COALESCE(NULLIF(?, ''), niche),
                    kind=COALESCE(NULLIF(?, ''), kind),
                    target_type=COALESCE(NULLIF(?, ''), target_type),
                    members=CASE WHEN ? > 0 THEN ? ELSE members END,
                    posts_per_day=CASE WHEN ? > 0 THEN ? ELSE posts_per_day END,
                    activity_text=COALESCE(NULLIF(?, ''), activity_text),
                    privacy=COALESCE(NULLIF(?, ''), privacy),
                    priority_score=CASE WHEN ? > 0 THEN ? ELSE priority_score END
                    WHERE url=?""",
                 (g.name or "Group Facebook", g.account or "", g.status or "joined",
                  g.niche or "săn sale", g.kind or "dealhunt", t_type,
                  g.members or 0, g.members or 0,
                  g.posts_per_day or 0.0, g.posts_per_day or 0.0,
                  g.activity_text or "", g.privacy or "public",
                  g.priority_score or 0.0, g.priority_score or 100.0,
                  g.url))
            updated += 1
        else:
            db.x("""INSERT INTO groups(url, name, niche, kind, status, account, allow_link, priority_score, members, posts_per_day, activity_text, privacy, target_type) 
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (g.url, g.name or "Group Facebook", g.niche or "săn sale", g.kind or "dealhunt",
                  g.status or "joined", g.account or "", 1, g.priority_score or 100.0,
                  g.members or 0, g.posts_per_day or 0.0, g.activity_text or "", g.privacy or "public", t_type))
            added += 1
    return {"message": f"Đã nhập thành công! Thêm mới {added} nhóm, cập nhật {updated} nhóm.", "added": added, "updated": updated}


@app.get("/api/lazada/hunter-groups")
def get_lazada_hunter_groups():
    """Lấy danh sách các nhóm Facebook chuyên dùng để quét giá thị trường Lazada."""
    rows = db.q("SELECT * FROM groups WHERE target_type='lazada_hunter' ORDER BY priority_score DESC, name ASC")
    return [dict(r) for r in rows]

@app.post("/api/lazada/hunter-groups")
def add_lazada_hunter_group(payload: LazadaHunterGroupPayload):
    """Thêm một nhóm mới vào danh sách chuyên quét giá Lazada."""
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL nhóm Facebook.")
    name = payload.name.strip() if payload.name else (url.rstrip("/").split("/")[-1] or "Nhóm quét Lazada")
    existing = db.q("SELECT 1 FROM groups WHERE url=?", (url,), one=True)
    if existing:
        db.x("UPDATE groups SET target_type='lazada_hunter', status='joined' WHERE url=?", (url,))
    else:
        db.x("""INSERT INTO groups(url, name, niche, kind, status, allow_link, target_type)
                VALUES(?,?,?,?,?,?,?)""",
             (url, name, "công nghệ / bàn phím", "dealhunt", "joined", 1, "lazada_hunter"))
    return {"success": True, "message": f"Đã thêm nhóm '{name}' vào danh sách quét Lazada thành công!"}

@app.delete("/api/lazada/hunter-groups")
def remove_lazada_hunter_group(url: str = Query(...)):
    """Gỡ nhóm khỏi danh sách quét Lazada (chuyển sang nhóm posting)."""
    db.x("UPDATE groups SET target_type='posting' WHERE url=?", (url,))
    return {"success": True, "message": "Đã gỡ nhóm khỏi danh sách quét Lazada."}


@app.post("/api/groups/search-niche")
def search_niche_groups_endpoint(payload: SearchNicheGroupsRequest):
    """Tìm kiếm nhóm Facebook theo từ khóa/nhóm ngành, đánh giá tương tác/thành viên/bài viết, và auto-join."""
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == payload.account), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{payload.account}.json"

    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=400, detail=f"Chưa có file cookie cho tài khoản '{payload.account}'. Hãy cập nhật cookie trước.")

    scanner_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "fb_groups_scanner.py")
    cmd = [
        sys.executable, scanner_script, "search", full_path,
        "--keyword", payload.keyword,
        "--niche", payload.niche or "",
        "--min-members", str(payload.min_members or 5000),
        "--min-posts", str(payload.min_posts_per_day or 3.0),
        "--max-results", str(payload.max_results or 15),
        "--max-scroll", str(payload.max_scroll or 6)
    ]
    if payload.only_public:
        cmd.append("--only-public")
    if payload.auto_join:
        cmd.append("--auto-join")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        if proc.returncode != 0:
            err = proc.stderr.strip() or "Tiến trình tìm kiếm gặp lỗi không xác định."
            raise RuntimeError(err)

        output_str = proc.stdout.strip()
        if not output_str:
            raise RuntimeError("Không nhận được dữ liệu trả về từ trình duyệt.")

        data = json.loads(output_str)
        data["account"] = payload.account
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Lỗi phản hồi từ trình duyệt: {proc.stdout}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tìm kiếm nhóm: {str(e)}")


@app.post("/api/accounts/{account_name}/join-group")
def join_group_endpoint(account_name: str, payload: JoinGroupRequest):
    """Tự động tham gia một group Facebook bằng tài khoản được chỉ định qua Playwright."""
    # BẢO VỆ DS ĐEN: Chặn tuyệt đối không cho phép join lại nhóm đã bị banned!
    existing = db.q("SELECT status FROM groups WHERE url=?", (payload.group_url,), one=True)
    if existing and existing.get("status") == "banned":
        raise HTTPException(
            status_code=400,
            detail="Nhóm này đã bị đưa vào Danh Sách Đen (Blacklist / Banned). Hệ thống chặn không cho phép tham gia lại để bảo vệ tài khoản!"
        )

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
            [sys.executable, scanner_script, "join", full_path, "--group-url", payload.group_url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=90
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or "Tiến trình tham gia nhóm gặp lỗi."
            raise RuntimeError(err)

        output_str = proc.stdout.strip()
        if not output_str:
            raise RuntimeError("Không nhận được dữ liệu trả về từ trình duyệt.")

        data = json.loads(output_str)
        data["account"] = account_name

        if data.get("success"):
            new_status = data.get("status", "joined")
            existing = db.q("SELECT 1 FROM groups WHERE url=?", (payload.group_url,), one=True)
            if existing:
                db.x("UPDATE groups SET status=?, account=? WHERE url=?", (new_status, account_name, payload.group_url))
            else:
                db.x("INSERT INTO groups(url, name, status, account) VALUES(?,?,?,?)",
                     (payload.group_url, "Group Facebook", new_status, account_name))

        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Lỗi phản hồi từ trình duyệt: {proc.stdout}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tham gia nhóm: {str(e)}")


@app.post("/api/groups/auto-join-batch")
def auto_join_batch_endpoint(payload: BatchJoinGroupsRequest):
    """Tự động tham gia hàng loạt các nhóm candidate bằng Playwright."""
    account_name = payload.account
    cfg = get_config()
    acc = next((a for a in cfg.get("accounts", []) if a["name"] == account_name), None)
    cookie_rel_path = acc.get("cookie_file") if acc else f"cookies/{account_name}.json"

    full_path = cookie_rel_path
    if not os.path.isabs(full_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, full_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=400, detail=f"Chưa có file cookie cho tài khoản '{account_name}'.")

    urls = payload.group_urls or []
    if not urls:
        limit = payload.limit or 5
        rows = db.q("SELECT url FROM groups WHERE status='candidate' ORDER BY priority_score DESC LIMIT ?", (limit,))
        urls = [r["url"] for r in rows]

    # BẢO VỆ DS ĐEN: Lọc bỏ hoàn toàn mọi URL đã bị Blacklist (banned)
    urls = [u for u in urls if not groups.is_blacklisted(u)]

    if not urls:
        return {"success": True, "message": "Không có nhóm chờ (candidate) hợp lệ nào cần tham gia (đã loại trừ nhóm trong DS Đen).", "results": []}

    scanner_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "fb_groups_scanner.py")
    results = []
    success_count = 0
    pending_count = 0
    fail_count = 0

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    for idx, g_url in enumerate(urls):
        try:
            proc = subprocess.run(
                [sys.executable, scanner_script, "join", full_path, "--group-url", g_url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=90
            )
            data = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {"success": False, "message": proc.stderr.strip()}
        except Exception as e:
            data = {"success": False, "message": str(e)}

        data["url"] = g_url
        if data.get("success"):
            st = data.get("status", "joined")
            if st == "pending_approval":
                pending_count += 1
            else:
                success_count += 1
            db.x("UPDATE groups SET status=?, account=? WHERE url=?", (st, account_name, g_url))
        else:
            fail_count += 1

        results.append(data)
        if idx < len(urls) - 1:
            time.sleep(random.randint(4, 7))

    return {
        "success": True,
        "total": len(urls),
        "joined": success_count,
        "pending": pending_count,
        "failed": fail_count,
        "results": results,
        "message": f"Hoàn tất duyệt {len(urls)} nhóm: {success_count} đã vào, {pending_count} chờ duyệt, {fail_count} không thành công."
    }



# =====================================================================
# --- FACEBOOK GROUP BLACKLIST & AUTO-LEAVE ENDPOINTS ---
# =====================================================================

@app.get("/api/groups/blacklist")
def get_blacklisted_groups():
    """Lấy danh sách các nhóm Facebook đã bị đưa vào Danh Sách Đen (status='banned')."""
    rows = db.q("""
        SELECT url, name, niche, kind, status, account, allow_link, 
               priority_score, fail_count, success_count, consecutive_fails, 
               last_error, members, posts_per_day, last_posted_at, target_type
        FROM groups 
        WHERE status='banned'
        ORDER BY last_posted_at DESC, priority_score ASC
    """)
    return [dict(r) for r in rows]

@app.get("/api/groups/blacklist/candidates")
def get_blacklist_candidates(
    max_fails: int = Query(3, alias="max_consecutive_fails"),
    max_pending: int = Query(2, alias="max_pending_count")
):
    """Rà soát và trả về danh sách các nhóm có nguy cơ vi phạm (bắt duyệt, cấm đăng, lỗi liên tiếp)."""
    return groups.find_bad_groups(max_consecutive_fails=max_fails, max_pending_count=max_pending)

@app.post("/api/groups/blacklist/scan-and-clean")
def scan_and_clean_blacklist_endpoint(payload: BlacklistCleanRequest):
    """
    Quét tự động các nhóm vi phạm (cấm đăng, pending duyệt, lỗi liên tiếp >= 3):
    Tự động rời nhóm trên Facebook bằng Playwright và đánh dấu 'banned' vĩnh viễn không join lại.
    """
    cfg = get_config()
    res = groups.batch_scan_and_clean_blacklist(
        auto_leave_fb=payload.auto_leave_fb if payload.auto_leave_fb is not None else True,
        max_groups=payload.max_groups or 5,
        cfg=cfg
    )
    return res

@app.post("/api/groups/blacklist/ban")
def ban_group_manual_endpoint(payload: BlacklistBanRequest):
    """Đưa thủ công một nhóm vào Danh Sách Đen (Banned) và tự động rời nhóm trên FB."""
    res = groups.leave_and_blacklist_group(
        group_url=payload.group_url,
        reason=payload.reason or "Chặn và rời nhóm thủ công bởi người dùng",
        auto_leave_fb=payload.auto_leave_fb if payload.auto_leave_fb is not None else True,
        account=payload.account
    )
    return res

@app.post("/api/groups/blacklist/unban")
def unban_group_endpoint(payload: BlacklistUnbanRequest):
    """Mở khóa một nhóm khỏi Danh Sách Đen, đưa về trạng thái candidate để xem xét lại."""
    return groups.unban_group(payload.group_url, new_status=payload.new_status or "candidate")

@app.get("/api/groups/blacklist/config")
def get_blacklist_config():
    """Lấy cấu hình tự động quét và lọc nhóm vào Danh Sách Đen."""
    cfg = get_config()
    return cfg.get("group_blacklist", {
        "auto_clean_enabled": True,
        "clean_interval_hours": 6,
        "auto_leave_fb": True,
        "max_leaves_per_run": 5,
        "consecutive_fails_threshold": 3,
        "pending_approval_threshold": 2
    })

@app.post("/api/groups/blacklist/config")
def save_blacklist_config(payload: BlacklistConfigUpdate):
    """Cập nhật cấu hình tự động quét và lọc nhóm."""
    cfg = get_config()
    bl = cfg.get("group_blacklist", {})
    if payload.auto_clean_enabled is not None:
        bl["auto_clean_enabled"] = payload.auto_clean_enabled
    if payload.clean_interval_hours is not None:
        bl["clean_interval_hours"] = max(1, payload.clean_interval_hours)
    if payload.auto_leave_fb is not None:
        bl["auto_leave_fb"] = payload.auto_leave_fb
    if payload.max_leaves_per_run is not None:
        bl["max_leaves_per_run"] = max(1, payload.max_leaves_per_run)
    if payload.consecutive_fails_threshold is not None:
        bl["consecutive_fails_threshold"] = max(1, payload.consecutive_fails_threshold)
    if payload.pending_approval_threshold is not None:
        bl["pending_approval_threshold"] = max(1, payload.pending_approval_threshold)
    cfg["group_blacklist"] = bl
    save_config(cfg)
    return {"success": True, "message": "Đã lưu cấu hình Danh Sách Đen thành công!", "config": bl}


# =====================================================================
# --- LAZADA DEAL HUNTER ENDPOINTS ---
# =====================================================================

class LazadaCookieUpdate(BaseModel):
    cookie_data: str

class LazadaHunterConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = None
    filter_mall_only: Optional[bool] = None
    min_discount_pct: Optional[float] = None
    selected_groups: Optional[List[str]] = None
    max_search_results: Optional[int] = None

class LazadaProductCreate(BaseModel):
    name: str
    clean_keyword: Optional[str] = ""
    avg_price: float
    min_price: Optional[float] = 0.0
    max_price: Optional[float] = 0.0
    filter_mall_only: Optional[bool] = True
    min_discount_pct: Optional[float] = 10.0

class LazadaProductUpdate(BaseModel):
    name: Optional[str] = None
    clean_keyword: Optional[str] = None
    avg_price: Optional[float] = None
    is_active: Optional[int] = None
    filter_mall_only: Optional[bool] = None
    min_discount_pct: Optional[float] = None

class LazadaScanFBRequest(BaseModel):
    group_urls: List[str]
    account: Optional[str] = "nick_a"
    posts_per_group: Optional[int] = 50

class LazadaTestSearchRequest(BaseModel):
    keyword: str
    filter_mall_only: Optional[bool] = True
    limit: Optional[int] = 10

_fb_scan_status = {
    "is_running": False,
    "last_result": None,
    "started_at": 0,
    "finished_at": 0,
    "error": None
}

@app.get("/api/lazada/cookie")
def get_lazada_cookie():
    """Lấy thông tin và trạng thái cookie Lazada."""
    return lazada.get_lazada_cookie_info()

@app.post("/api/lazada/cookie")
def update_lazada_cookie(req: LazadaCookieUpdate):
    """Cập nhật Cookie Lazada từ JSON hoặc chuỗi header."""
    try:
        info = lazada.save_lazada_cookie(req.cookie_data)
        return {"success": True, "info": info, "message": f"Đã lưu thành công {info.get('count', 0)} cookies Lazada."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/lazada/cookie/test")
def test_lazada_cookie():
    """Kiểm tra kết nối và tính hợp lệ của cookie Lazada."""
    return lazada.test_lazada_cookie_connection()

@app.get("/api/lazada/config")
def get_lazada_hunter_config():
    """Lấy cấu hình Lazada Hunter."""
    return lazada_hunter.get_hunter_config()

@app.post("/api/lazada/config")
def update_lazada_hunter_config(req: LazadaHunterConfigUpdate):
    """Cập nhật cấu hình Lazada Hunter."""
    payload = {k: v for k, v in req.dict().items() if v is not None}
    saved = lazada_hunter.save_hunter_config(payload)
    return {"success": True, "config": saved}

@app.get("/api/lazada/products")
def list_tracked_products():
    """Lấy danh sách các sản phẩm đang được theo dõi kèm giá trung bình FB."""
    rows = db.q("""
        SELECT * FROM lazada_tracked_products
        ORDER BY is_active DESC, updated_at DESC
    """)
    return [dict(r) for r in rows]

@app.post("/api/lazada/products")
def create_tracked_product(req: LazadaProductCreate):
    """Thêm một sản phẩm mới để theo dõi."""
    now = time.time()
    kw = (req.clean_keyword or req.name).strip().lower()
    pid = db.x("""
        INSERT INTO lazada_tracked_products(
            name, clean_keyword, avg_price, min_price, max_price,
            sample_count, is_active, filter_mall_only, min_discount_pct,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?)
    """, (
        req.name.strip(), kw, req.avg_price, req.min_price or req.avg_price,
        req.max_price or req.avg_price, 1 if req.filter_mall_only else 0,
        req.min_discount_pct or 10.0, now, now
    ))
    return {"success": True, "id": pid, "message": "Đã thêm sản phẩm theo dõi."}

@app.put("/api/lazada/products/{product_id}")
def update_tracked_product(product_id: int, req: LazadaProductUpdate):
    """Cập nhật thông tin sản phẩm theo dõi."""
    row = db.q("SELECT * FROM lazada_tracked_products WHERE id = ?", (product_id,), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    fields = []
    args = []
    if req.name is not None:
        fields.append("name = ?")
        args.append(req.name.strip())
    if req.clean_keyword is not None:
        fields.append("clean_keyword = ?")
        args.append(req.clean_keyword.strip().lower())
    if req.avg_price is not None:
        fields.append("avg_price = ?")
        args.append(req.avg_price)
    if req.is_active is not None:
        fields.append("is_active = ?")
        args.append(req.is_active)
    if req.filter_mall_only is not None:
        fields.append("filter_mall_only = ?")
        args.append(1 if req.filter_mall_only else 0)
    if req.min_discount_pct is not None:
        fields.append("min_discount_pct = ?")
        args.append(req.min_discount_pct)

    if fields:
        fields.append("updated_at = ?")
        args.append(time.time())
        args.append(product_id)
        db.x(f"UPDATE lazada_tracked_products SET {', '.join(fields)} WHERE id = ?", tuple(args))

    return {"success": True, "message": "Đã cập nhật sản phẩm."}

@app.delete("/api/lazada/products/{product_id}")
def delete_tracked_product(product_id: int):
    """Xóa một sản phẩm khỏi danh sách theo dõi."""
    db.x("DELETE FROM lazada_tracked_products WHERE id = ?", (product_id,))
    return {"success": True, "message": "Đã xóa sản phẩm."}

@app.post("/api/lazada/products/{product_id}/toggle")
def toggle_tracked_product(product_id: int):
    """Bật/tắt theo dõi 1 sản phẩm."""
    row = db.q("SELECT is_active FROM lazada_tracked_products WHERE id = ?", (product_id,), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")
    new_st = 0 if row["is_active"] else 1
    db.x("UPDATE lazada_tracked_products SET is_active = ?, updated_at = ? WHERE id = ?", (new_st, time.time(), product_id))
    return {"success": True, "is_active": new_st}

@app.post("/api/lazada/products/cleanup-junk")
def cleanup_junk_products():
    """Dọn dẹp các sản phẩm rác, từ khóa dài lê thê hoặc chứa chữ thành viên FB."""
    deleted = fb_market_scanner.cleanup_junk_tracked_products()
    return {"success": True, "message": f"Đã xóa {deleted} sản phẩm rác khỏi danh sách theo dõi.", "deleted": deleted}

def _bg_scan_fb_worker(group_urls: List[str], account: str, posts_per_group: int = 50):
    global _fb_scan_status
    try:
        res = fb_market_scanner.scan_facebook_groups_posts_isolated(group_urls, account_name=account, posts_per_group=posts_per_group)
        _fb_scan_status["last_result"] = res
        _fb_scan_status["finished_at"] = time.time()
        _fb_scan_status["error"] = None if res.get("success") else res.get("error")
    except Exception as e:
        _fb_scan_status["error"] = str(e)
        _fb_scan_status["finished_at"] = time.time()
    finally:
        _fb_scan_status["is_running"] = False

@app.post("/api/lazada/scan-fb")
def trigger_scan_fb(req: LazadaScanFBRequest, background_tasks: BackgroundTasks):
    """Kích hoạt quét bài viết từ các nhóm Facebook để cập nhật giá thị trường."""
    global _fb_scan_status
    if _fb_scan_status["is_running"]:
        return {"success": False, "message": "Tiến trình quét Facebook đang chạy. Vui lòng chờ trong giây lát."}

    _fb_scan_status["is_running"] = True
    _fb_scan_status["started_at"] = time.time()
    _fb_scan_status["finished_at"] = 0
    _fb_scan_status["error"] = None

    posts_limit = req.posts_per_group if req.posts_per_group and req.posts_per_group > 0 else 50
    background_tasks.add_task(_bg_scan_fb_worker, req.group_urls, req.account or "nick_a", posts_limit)
    return {"success": True, "message": f"Đã bắt đầu tiến trình quét {len(req.group_urls)} nhóm Facebook ({posts_limit} bài/nhóm) trong nền."}

@app.get("/api/lazada/scan-fb/status")
def get_scan_fb_status():
    """Xem trạng thái tiến trình quét nhóm Facebook."""
    return _fb_scan_status

@app.get("/api/lazada/deals")
def list_lazada_deals(limit: int = 50):
    """Lấy danh sách các deal Lazada đã săn được."""
    rows = db.q("""
        SELECT * FROM lazada_found_deals
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    return [dict(r) for r in rows]

@app.delete("/api/lazada/deals/{deal_id}")
def delete_single_lazada_deal(deal_id: int):
    """Xóa 1 deal Lazada đã săn được."""
    db.x("DELETE FROM lazada_found_deals WHERE id = ?", (deal_id,))
    return {"success": True, "message": f"Đã xóa deal #{deal_id}."}

@app.delete("/api/lazada/deals")
def clear_all_lazada_deals():
    """Xóa toàn bộ danh sách deal Lazada đã săn được."""
    db.x("DELETE FROM lazada_found_deals")
    return {"success": True, "message": "Đã xóa toàn bộ danh sách deal Lazada đã săn được."}


@app.get("/api/lazada/logs")
def list_lazada_hunter_logs(limit: int = 50):
    """Lấy danh sách nhật ký các lần quét săn deal Lazada."""
    rows = db.q("""
        SELECT * FROM lazada_hunter_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    result = []
    for r in rows:
        d = dict(r)
        if d.get("details"):
            try:
                d["details_parsed"] = json.loads(d["details"])
            except Exception:
                d["details_parsed"] = []
        else:
            d["details_parsed"] = []
        result.append(d)
    return result

@app.delete("/api/lazada/logs")
def clear_lazada_hunter_logs():
    """Xóa toàn bộ nhật ký quét deal Lazada."""
    db.x("DELETE FROM lazada_hunter_logs")
    return {"success": True, "message": "Đã xóa toàn bộ lịch sử quét deal."}

@app.post("/api/lazada/run-hunter-now")
def run_hunter_now(background_tasks: BackgroundTasks):
    """Kích hoạt quét toàn bộ sản phẩm theo dõi trên Lazada ngay lập tức trong nền."""
    st = lazada_hunter.get_hunter_status()
    if st.get("is_running"):
        return {
            "success": False,
            "message": "Luồng quét deal Lazada hiện đang chạy! Bạn có thể xem tiến độ trực tiếp trên thanh điều hướng hoặc trang Săn Deal.",
            "is_running": True
        }
    background_tasks.add_task(lazada_hunter.run_lazada_hunter_cycle, None, "manual")
    return {"success": True, "message": "Đã bắt đầu chu kỳ quét toàn bộ sản phẩm theo dõi trên Lazada trong nền.", "is_running": True}

@app.post("/api/lazada/test-search")
def test_search_lazada(req: LazadaTestSearchRequest):
    """Tìm kiếm thử sản phẩm trên Lazada để xem trước giá và các phân loại."""
    items = lazada.search_lazada_products_isolated(
        keyword=req.keyword,
        filter_mall_only=bool(req.filter_mall_only),
        limit=req.limit or 40
    )
    items = items if items is not None else []
    return {"success": True, "keyword": req.keyword, "filter_mall_only": req.filter_mall_only, "count": len(items), "items": items}

# --- BACKGROUND DAEMON RUNNER CHO LAZADA HUNTER 5 PHÚT ---
_hunter_thread_started = False

def _start_lazada_hunter_daemon():
    global _hunter_thread_started
    if _hunter_thread_started:
        return
    _hunter_thread_started = True

    def _hunter_loop():
        print("[lazada_hunter_daemon] 🚀 Bắt đầu luồng chạy định kỳ săn deal Lazada (5 phút)...")
        time.sleep(10)  # Đợi server ổn định sau khi khởi động
        while True:
            try:
                cfg = lazada_hunter.get_hunter_config()
                if cfg.get("enabled", True):
                    interval_m = max(1, int(cfg.get("interval_minutes", 5)))
                    print(f"[lazada_hunter_daemon] ⏰ Đang thực hiện chu kỳ quét toàn bộ sản phẩm theo dõi định kỳ {interval_m}p...")
                    res = lazada_hunter.run_lazada_hunter_cycle(batch_size=None, trigger_type="auto_5m")
                    print(f"[lazada_hunter_daemon] ✅ Hoàn tất: {res.get('message')}")
                else:
                    interval_m = 5
            except Exception as e:
                print(f"[lazada_hunter_daemon] ❌ Lỗi chu kỳ: {e}")
                interval_m = 5

            time.sleep(interval_m * 60)

    t = threading.Thread(target=_hunter_loop, daemon=True, name="LazadaHunterDaemon")
    t.start()

# --- BACKGROUND DAEMON RUNNER CHO RADAR SẬP SÀN TMALL (LAZADA GENERAL SCANNER) 5 PHÚT ---
_general_daemon_started = False

def _start_lazada_general_daemon():
    global _general_daemon_started
    if _general_daemon_started:
        return
    _general_daemon_started = True

    def _general_loop():
        print("[lazada_general_daemon] 🚀 Bắt đầu luồng chạy định kỳ Radar Săn Sập Sàn Tmall (5 phút)...")
        time.sleep(25)  # Đợi 25s sau khi khởi động để so le với hunter daemon
        while True:
            try:
                cfg = lazada_general_scanner.get_general_scanner_config()
                if cfg.get("enabled", True):
                    interval_m = max(1, int(cfg.get("interval_minutes", 5)))
                    print(f"[lazada_general_daemon] ⏰ Đang thực hiện chu kỳ radar quét sập sàn định kỳ {interval_m}p...")
                    res = lazada_general_scanner.run_general_scanner_cycle(
                        selected_categories=None,
                        trigger_type="auto_5m"
                    )
                    # Quét xoay vòng một lô các gian hàng Tmall Brand (tập trung 6 nhóm ngành trọng điểm)
                    print("[lazada_general_daemon] 🏪 Đang thực hiện chu kỳ quét xoay vòng các shop Tmall Brand...")
                    res_tmall = lazada_general_scanner.run_tmall_brands_scan_cycle(
                        trigger_type="auto_5m",
                        batch_shops_per_cycle=6
                    )
                    print(f"[lazada_general_daemon] ✅ Hoàn tất Tmall Brand: {res_tmall.get('message')}")
                else:
                    interval_m = 5
            except Exception as e:
                print(f"[lazada_general_daemon] ❌ Lỗi chu kỳ radar: {e}")
                interval_m = 5

            time.sleep(interval_m * 60)

    t = threading.Thread(target=_general_loop, daemon=True, name="LazadaGeneralDaemon")
    t.start()

# --- BACKGROUND DAEMON RUNNER CHO LUỒNG TUẦN TỰ (AUTO PIPELINE SCHEDULER) ---
_pipeline_daemon_started = False

def _start_pipeline_auto_daemon():
    global _pipeline_daemon_started
    if _pipeline_daemon_started:
        return
    _pipeline_daemon_started = True

    def _pipeline_auto_loop():
        print("[pipeline_daemon] 🚀 Bắt đầu daemon tự động hóa Luồng Tuần Tự (Cào Deal ➔ Lập Lịch ➔ Đăng Bài)...")
        time.sleep(12)  # Đợi server ổn định sau khi khởi động
        last_full_cycle_time = _pipeline_status.get("last_finished_at", 0)
        last_run_due_time = time.time()

        while True:
            try:
                now = time.time()
                p_cfg = get_pipeline_auto_config()
                is_enabled = p_cfg.get("enabled", True)
                interval_hours = max(1, p_cfg.get("interval_hours", 2))
                cycle_interval_sec = interval_hours * 3600
                auto_post_due = p_cfg.get("auto_post_due", True)

                if is_enabled:
                    # 1. Kiểm tra chu kỳ cào + lập lịch + đăng toàn bộ (Full Cycle)
                    if (now - last_full_cycle_time) >= cycle_interval_sec:
                        if not _pipeline_status.get("is_running"):
                            print(f"[pipeline_daemon] ⏰ Đến chu kỳ tự động {interval_hours}h: Kích hoạt toàn bộ luồng tuần tự...")
                            last_full_cycle_time = now
                            _run_pipeline_worker()
                        else:
                            print("[pipeline_daemon] ⏳ Luồng tuần tự đang bận, dời sang lần kiểm tra tiếp theo.")

                    # 2. Định kỳ mỗi 5 phút kiểm tra đăng các bài đến giờ trong hàng đợi (Run Due Posts)
                    elif auto_post_due and (now - last_run_due_time) >= 300:
                        last_run_due_time = now
                        if not _pipeline_status.get("is_running"):
                            try:
                                queued = db.q("SELECT count(*) as c FROM posts WHERE status='queued' AND scheduled_at<=?", (now,), one=True)
                                if queued and queued["c"] > 0:
                                    print(f"[pipeline_daemon] 📬 Phát hiện {queued['c']} bài đến giờ hẹn đăng, kích hoạt poster.run_due...")
                                    poster.run_due(get_config())
                            except Exception as pe:
                                print(f"[pipeline_daemon] Lỗi run_due: {pe}")

            except Exception as e:
                print(f"[pipeline_daemon] ❌ Lỗi daemon tự động: {e}")

            time.sleep(30)  # Kiểm tra mỗi 30 giây

    t = threading.Thread(target=_pipeline_auto_loop, daemon=True, name="PipelineAutoDaemon")
    t.start()

# --- BACKGROUND DAEMON CHO VIỆC TỰ ĐỘNG QUÉT & LỌC NHÓM VI PHẠM (BLACKLIST DAEMON) ---
_blacklist_daemon_started = False

def _start_group_blacklist_daemon():
    global _blacklist_daemon_started
    if _blacklist_daemon_started:
        return
    _blacklist_daemon_started = True

    def _blacklist_loop():
        print("[blacklist_daemon] 🛡️ Bắt đầu daemon tự động quét & thanh lọc nhóm vi phạm (Blacklist / Auto-Leave)...")
        time.sleep(25)  # Đợi server ổn định sau khi khởi động
        last_clean_time = 0

        while True:
            try:
                cfg = get_config()
                bl_cfg = cfg.get("group_blacklist", {})
                is_enabled = bl_cfg.get("auto_clean_enabled", True)
                interval_hours = max(1, bl_cfg.get("clean_interval_hours", 6))
                interval_sec = interval_hours * 3600
                auto_leave_fb = bl_cfg.get("auto_leave_fb", True)
                max_leaves = bl_cfg.get("max_leaves_per_run", 5)

                now = time.time()
                if is_enabled and (now - last_clean_time) >= interval_sec:
                    last_clean_time = now
                    print(f"[blacklist_daemon] 🧹 Đến chu kỳ định kỳ ({interval_hours}h): Đang rà soát các nhóm bắt duyệt / cấm đăng...")
                    res = groups.batch_scan_and_clean_blacklist(
                        auto_leave_fb=auto_leave_fb,
                        max_groups=max_leaves,
                        cfg=cfg
                    )
                    cleaned_count = res.get("cleaned_count", 0)
                    bad_found = res.get("total_bad_found", 0)
                    if cleaned_count > 0:
                        print(f"[blacklist_daemon] ✅ Đã thanh lọc {cleaned_count}/{bad_found} nhóm vi phạm vào Danh Sách Đen (Blacklist)!")
                    else:
                        print("[blacklist_daemon] ✨ Kiểm tra hoàn tất: Hiện không có nhóm vi phạm nào cần thanh lọc.")
            except Exception as e:
                print(f"[blacklist_daemon] ❌ Lỗi chu kỳ thanh lọc nhóm: {e}")

            time.sleep(60)  # Kiểm tra chu kỳ mỗi 1 phút

    t = threading.Thread(target=_blacklist_loop, daemon=True, name="GroupBlacklistDaemon")
    t.start()

@app.on_event("startup")
def startup_event():
    _start_lazada_hunter_daemon()
    _start_lazada_general_daemon()
    _start_pipeline_auto_daemon()
    _start_group_blacklist_daemon()

# Khởi chạy daemon ngay nếu file được reload trong Uvicorn
_start_lazada_hunter_daemon()
_start_lazada_general_daemon()
_start_pipeline_auto_daemon()
_start_group_blacklist_daemon()





