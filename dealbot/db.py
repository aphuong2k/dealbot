import sqlite3, time
DB = "dealbot.db"

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
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
    """)
    c.commit(); c.close()

    # Chạy migration bổ sung cho cơ sở dữ liệu đã tồn tại từ các phiên bản trước
    _ensure_column("groups", "success_count INTEGER DEFAULT 0")
    _ensure_column("groups", "consecutive_fails INTEGER DEFAULT 0")
    _ensure_column("groups", "priority_score REAL DEFAULT 100.0")
    _ensure_column("groups", "last_error TEXT")

    _ensure_column("deals", "is_valid INTEGER DEFAULT 1")
    _ensure_column("deals", "last_checked_at REAL DEFAULT 0")

    _ensure_column("posts", "sub_id TEXT")
    _ensure_column("posts", "comment_status TEXT DEFAULT 'none'")
    _ensure_column("posts", "comment_retry_at REAL DEFAULT 0")
    _ensure_column("posts", "comment_retries INTEGER DEFAULT 0")
    _ensure_column("posts", "channel_posted INTEGER DEFAULT 0")

    _ensure_column("accounts", "last_warmup_at REAL DEFAULT 0")

def q(sql, args=(), one=False):
    c = conn(); r = c.execute(sql, args).fetchall(); c.commit(); c.close()
    return (r[0] if r else None) if one else r

def x(sql, args=()):
    c = conn(); cur = c.execute(sql, args); c.commit(); n = cur.lastrowid; c.close(); return n

def today_start():
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))

