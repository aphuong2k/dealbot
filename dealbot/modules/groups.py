"""Module 1: sinh từ khóa theo ngành + gom group ứng viên (không cần đăng nhập FB)."""
import os, re, json, csv, requests, anthropic, db

def gen_keywords(niche, n=15):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            cli = anthropic.Anthropic(api_key=api_key)
            msg = cli.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=800,
                messages=[{"role": "user", "content":
                    f"Liệt kê {n} cụm từ khóa tiếng Việt mà admin hay đặt tên group Facebook về ngách '{niche}' "
                    "(review, hội mua sắm, săn sale, kinh nghiệm...). Chỉ trả JSON array các chuỗi."}])
            return json.loads(re.search(r"\[.*\]", msg.content[0].text, re.S).group(0))
        except Exception as e:
            print("[groups] Claude API keyword generation notice:", type(e).__name__)

    # Từ khóa mồi mặc định
    return [
        f"hội {niche}", f"review {niche}", f"săn sale {niche}", f"kinh nghiệm {niche}",
        f"thanh lý {niche}", f"mua bán {niche} giá rẻ", f"nghiện {niche}"
    ][:n]


def search_groups(keyword, pages=2):
    """Dùng Google Custom Search API (hợp lệ, ổn định hơn cào Google)."""
    key, cx = os.getenv("GOOGLE_CSE_KEY"), os.getenv("GOOGLE_CSE_CX")
    if not (key and cx):
        print("Thiếu GOOGLE_CSE_KEY/CX"); return []
    out = []
    for p in range(pages):
        r = requests.get("https://www.googleapis.com/customsearch/v1", params={
            "key": key, "cx": cx, "q": f"site:facebook.com/groups {keyword}", "start": 1 + p * 10}, timeout=20)
        for it in r.json().get("items", []):
            m = re.search(r"facebook\.com/groups/([\w.\-]+)", it["link"])
            if m:
                out.append((f"https://www.facebook.com/groups/{m.group(1)}", it["title"].split("|")[0].strip()))
    return out

def discover(niches, dealhunt_niches=()):
    found = 0
    for niche in list(niches) + list(dealhunt_niches):
        kind = 'dealhunt' if niche in dealhunt_niches else 'niche'
        for kw in gen_keywords(niche):
            for url, name in search_groups(kw):
                if not db.q("SELECT 1 FROM groups WHERE url=?", (url,), one=True):
                    db.x("INSERT INTO groups(url,name,niche,kind) VALUES(?,?,?,?)", (url, name, niche, kind)); found += 1
    export_csv()
    return found

def export_csv(path="groups_review.csv"):
    """Xuất để bạn duyệt tay: điền status=joined/skip, allow_link=0/1 rồi import lại."""
    rows = db.q("SELECT * FROM groups WHERE status IN ('candidate', 'cooling_down') ORDER BY priority_score DESC")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "name", "niche", "kind", "status", "allow_link", "priority_score", "fail_count"])
        for r in rows:
            w.writerow([r["url"], r["name"], r["niche"], r["kind"], r["status"], r["allow_link"], r["priority_score"], r["fail_count"]])

def import_reviewed(path="groups_review.csv"):
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            st = r.get("status", "candidate")
            # Nếu người dùng duyệt lại group thành joined/approved, reset chuỗi lỗi
            if st in ("joined", "approved"):
                db.x("""UPDATE groups SET status=?, allow_link=?, consecutive_fails=0 
                        WHERE url=?""", (st, int(r.get("allow_link") or 1), r["url"]))
            else:
                db.x("UPDATE groups SET status=?, allow_link=? WHERE url=?", 
                     (st, int(r.get("allow_link") or 1), r["url"]))

def reset_cooling_down_groups(cooldown_days=7):
    """Tự động cho group cooling_down thêm cơ hội sau 7 ngày thử thách."""
    threshold = time.time() - cooldown_days * 86400
    db.x("""UPDATE groups SET status='joined', consecutive_fails=0, priority_score=75.0 
            WHERE status='cooling_down' AND last_posted_at<?""", (threshold,))

def assign_accounts(account_names):
    """Mỗi group gắn cố định 1 nick (sticky) để không có 2 nick cùng xuất hiện trong 1 group."""
    gs = db.q("SELECT url FROM groups WHERE status IN ('joined','approved') AND (account IS NULL OR account='')")
    for i, g in enumerate(gs):
        db.x("UPDATE groups SET account=? WHERE url=?", (account_names[i % len(account_names)], g["url"]))

