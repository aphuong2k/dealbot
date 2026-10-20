import os, sqlite3, time
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "dealbot.db")

class DictRow(sqlite3.Row):
    """sqlite3.Row mở rộng hỗ trợ .get() và toán tử 'in' an toàn theo tên cột."""
    def get(self, key, default=None):
        try:
            val = self[key]
            return val if val is not None else default
        except (IndexError, KeyError):
            return default

    def __contains__(self, key):
        return key in self.keys()

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = DictRow
    return c

def _ensure_column(table, column_def):
    """Thêm cột an toàn nếu chưa tồn tại trong bảng SQLite."""
    col_name = column_def.split()[0]
    c = conn()
    try:
        existing = [r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
        if col_name not in existing:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
            c.commit()
    except Exception as e:
        print(f"Migration error ({table}.{col_name}):", e)
    finally:
        c.close()

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS groups(
        url TEXT PRIMARY KEY, name TEXT, niche TEXT, members INTEGER DEFAULT 0,
        status TEXT DEFAULT 'candidate',   -- candidate | joined | approved | banned | cooling_down | skip
        allow_link INTEGER DEFAULT 1, account TEXT, last_posted_at REAL DEFAULT 0,
        fail_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        consecutive_fails INTEGER DEFAULT 0,
        priority_score REAL DEFAULT 100.0,
        last_error TEXT,
        kind TEXT DEFAULT 'niche');   -- niche | dealhunt

    CREATE TABLE IF NOT EXISTS deals(
        id TEXT PRIMARY KEY, niche TEXT, title TEXT, price REAL, orig_price REAL,
        discount REAL, commission REAL, rating REAL, sold INTEGER, url TEXT,
        aff_url TEXT, image TEXT, image_path TEXT, score REAL, status TEXT DEFAULT 'new',
        is_valid INTEGER DEFAULT 1, last_checked_at REAL DEFAULT 0, created_at REAL);

    CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, deal_id TEXT, group_url TEXT, account TEXT,
        caption TEXT, comment TEXT, image_path TEXT, kind TEXT DEFAULT 'deal',
        status TEXT DEFAULT 'queued', -- queued|done|failed|skipped
        sub_id TEXT,
        comment_status TEXT DEFAULT 'none', -- none | queued | pending_approval | done | failed
        comment_retry_at REAL DEFAULT 0,
        comment_retries INTEGER DEFAULT 0,
        channel_posted INTEGER DEFAULT 0,
        scheduled_at REAL, posted_at REAL, error TEXT);

    CREATE TABLE IF NOT EXISTS coupons(
        id TEXT PRIMARY KEY, merchant TEXT, title TEXT, code TEXT, detail TEXT,
        start_at REAL, end_at REAL, url TEXT, aff_url TEXT, created_at REAL, used INTEGER DEFAULT 0);

    CREATE TABLE IF NOT EXISTS accounts(
        name TEXT PRIMARY KEY, paused_until REAL DEFAULT 0, last_post_at REAL DEFAULT 0,
        last_warmup_at REAL DEFAULT 0);

    CREATE TABLE IF NOT EXISTS lazada_tracked_products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        clean_keyword TEXT,
        avg_price REAL DEFAULT 0,
        min_price REAL DEFAULT 0,
        max_price REAL DEFAULT 0,
        sample_count INTEGER DEFAULT 1,
        source_groups TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        filter_mall_only INTEGER DEFAULT 1,
        min_discount_pct REAL DEFAULT 10.0,
        last_scanned_at REAL DEFAULT 0,
        created_at REAL DEFAULT 0,
        updated_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_found_deals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER DEFAULT 0,
        product_name TEXT,
        laz_item_id TEXT,
        laz_sku_id TEXT,
        variation_name TEXT,
        seller_name TEXT,
        is_mall INTEGER DEFAULT 1,
        laz_price REAL,
        market_avg_price REAL,
        diff_pct REAL,
        product_url TEXT,
        image_url TEXT,
        sent_to_tg INTEGER DEFAULT 0,
        sent_to_tg_at REAL DEFAULT 0,
        created_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_hunter_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at REAL DEFAULT 0,
        finished_at REAL DEFAULT 0,
        status TEXT DEFAULT 'success',
        trigger_type TEXT DEFAULT 'auto_5m',
        products_scanned INTEGER DEFAULT 0,
        deals_found INTEGER DEFAULT 0,
        telegram_sent INTEGER DEFAULT 0,
        details TEXT DEFAULT '',
        message TEXT DEFAULT '',
        created_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_deep_drops(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT,
        sku_id TEXT,
        product_title TEXT,
        category TEXT,
        variation_name TEXT,
        sibling_count INTEGER DEFAULT 1,
        sibling_avg_price REAL DEFAULT 0,
        drop_price REAL DEFAULT 0,
        drop_pct REAL DEFAULT 0,
        stock INTEGER DEFAULT 1,
        seller_name TEXT,
        is_mall INTEGER DEFAULT 1,
        product_url TEXT,
        image_url TEXT,
        sent_to_tg INTEGER DEFAULT 0,
        sent_to_tg_at REAL DEFAULT 0,
        created_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_deep_drops_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at REAL DEFAULT 0,
        finished_at REAL DEFAULT 0,
        status TEXT DEFAULT 'success',
        categories_scanned TEXT DEFAULT '',
        items_scanned INTEGER DEFAULT 0,
        deals_found INTEGER DEFAULT 0,
        telegram_sent INTEGER DEFAULT 0,
        message TEXT DEFAULT '',
        created_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_radar_categories(
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '🏷️',
        keywords_json TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at REAL DEFAULT 0,
        updated_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_tmall_categories(
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '🏪',
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        shops_count INTEGER DEFAULT 0,
        created_at REAL DEFAULT 0,
        updated_at REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS lazada_tmall_shops(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id TEXT NOT NULL,
        category_name TEXT NOT NULL,
        shop_name TEXT NOT NULL,
        shop_slug TEXT NOT NULL,
        shop_url TEXT NOT NULL,
        logo_url TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        last_scanned_at REAL DEFAULT 0,
        last_items_count INTEGER DEFAULT 0,
        deals_found_count INTEGER DEFAULT 0,
        created_at REAL DEFAULT 0,
        updated_at REAL DEFAULT 0,
        UNIQUE(category_id, shop_slug)
    );
    """)
    c.commit(); c.close()

    # Chạy migration bổ sung cho cơ sở dữ liệu đã tồn tại từ các phiên bản trước
    _ensure_column("groups", "success_count INTEGER DEFAULT 0")
    _ensure_column("groups", "consecutive_fails INTEGER DEFAULT 0")
    _ensure_column("groups", "priority_score REAL DEFAULT 100.0")
    _ensure_column("groups", "last_error TEXT")

    _ensure_column("groups", "members INTEGER DEFAULT 0")
    _ensure_column("groups", "posts_per_day REAL DEFAULT 0")
    _ensure_column("groups", "activity_text TEXT")
    _ensure_column("groups", "privacy TEXT DEFAULT 'public'")
    _ensure_column("groups", "target_type TEXT DEFAULT 'posting'")

    # Phân tách 2 luồng: Nhóm quét giá thị trường Lazada vs Nhóm đăng bài bán hàng Facebook
    try:
        c_m = conn()
        c_m.execute("""UPDATE groups SET target_type='lazada_hunter' 
                     WHERE url IN (
                         'https://www.facebook.com/groups/chobanphimco',
                         'https://www.facebook.com/groups/181768129374914',
                         'https://www.facebook.com/groups/hoikeycapvietnam',
                         'https://www.facebook.com/groups/475147223546856',
                         'https://www.facebook.com/groups/2027534878034246',
                         'https://www.facebook.com/groups/186181648626920'
                     ) OR LOWER(name) LIKE '%phím%' OR LOWER(name) LIKE '%keycap%'""")
        c_m.commit()
        c_m.close()
    except Exception:
        pass

    _ensure_column("deals", "is_valid INTEGER DEFAULT 1")
    _ensure_column("deals", "last_checked_at REAL DEFAULT 0")
    _ensure_column("deals", "posted_count INTEGER DEFAULT 0")
    _ensure_column("deals", "last_posted_at REAL DEFAULT 0")
    _ensure_column("deals", "is_vip INTEGER DEFAULT 0")
    _ensure_column("deals", "is_mall INTEGER DEFAULT 0")
    _ensure_column("deals", "brand TEXT DEFAULT ''")

    _ensure_column("coupons", "category TEXT DEFAULT 'all'")
    _ensure_column("coupons", "save_url TEXT DEFAULT ''")

    _ensure_column("posts", "sub_id TEXT")
    _ensure_column("posts", "comment_status TEXT DEFAULT 'none'")
    _ensure_column("posts", "comment_retry_at REAL DEFAULT 0")
    _ensure_column("posts", "comment_retries INTEGER DEFAULT 0")
    _ensure_column("posts", "channel_posted INTEGER DEFAULT 0")
    _ensure_column("posts", "post_url TEXT")

    _ensure_column("accounts", "last_warmup_at REAL DEFAULT 0")

def q(sql, args=(), one=False):
    c = conn(); r = c.execute(sql, args).fetchall(); c.commit(); c.close()
    return (r[0] if r else None) if one else r

def x(sql, args=()):
    c = conn(); cur = c.execute(sql, args); c.commit(); n = cur.lastrowid; c.close(); return n

def today_start():
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))

