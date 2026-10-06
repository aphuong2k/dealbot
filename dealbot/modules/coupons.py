"""Module 4: tổng hợp mã giảm giá + sự kiện hằng ngày -> bản tin đăng vào group săn deal."""
import os, time, hashlib, datetime, requests, yaml, db, anthropic, json, re
from . import images

def fetch_accesstrade():
    """Chỉnh endpoint/field theo tài liệu network của bạn (thường là 'offers/coupons')."""
    tok = os.getenv("ACCESSTRADE_TOKEN")
    if not tok: return []
    r = requests.get("https://api.accesstrade.vn/v1/offers_informations",
                     headers={"Authorization": f"Token {tok}"},
                     params={"merchant": "shopee", "status": 1, "limit": 50}, timeout=30)
    out = []
    for o in r.json().get("data", []):
        coupon = (o.get("coupons") or [{}])[0] if o.get("coupons") else {}
        out.append(dict(merchant=o.get("merchant", "shopee"), title=o.get("name", ""), code=coupon.get("coupon_code", ""),
                        detail=o.get("content", "")[:120], start_at=_ts(o.get("start_time")), end_at=_ts(o.get("end_time")),
                        url=o.get("link", ""), aff_url=o.get("aff_link") or o.get("link", "")))
    return out

def _ts(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z", "")).timestamp()
    except Exception: return time.time() + 86400

def manual_events(path="events.yaml"):
    """Lịch sự kiện cố định (9.9, 10.10, 11.11, flash sale khung giờ...) bạn tự cập nhật. Link aff dán sẵn."""
    if not os.path.exists(path): return []
    out = []
    for e in yaml.safe_load(open(path, encoding="utf-8")) or []:
        out.append(dict(merchant=e.get("merchant", "shopee"), title=e["title"], code=e.get("code", ""),
                        detail=e.get("detail", ""), start_at=_ts(e["start"]), end_at=_ts(e["end"]),
                        url=e.get("link", ""), aff_url=e.get("link", "")))
    return out

def refresh():
    n = 0
    for c in fetch_accesstrade() + manual_events():
        cid = hashlib.md5(f"{c['merchant']}{c['code']}{c['title']}{c['end_at']}".encode()).hexdigest()[:16]
        if db.q("SELECT 1 FROM coupons WHERE id=?", (cid,), one=True): continue
        db.x("""INSERT INTO coupons(id,merchant,title,code,detail,start_at,end_at,url,aff_url,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (cid, c["merchant"], c["title"], c["code"], c["detail"],
                                                  c["start_at"], c["end_at"], c["url"], c["aff_url"], time.time()))
        n += 1
    return n

def active(limit=8):
    now = time.time()
    return db.q("SELECT * FROM coupons WHERE end_at>? AND start_at<=? ORDER BY end_at ASC LIMIT ?", (now, now + 3600, limit))

def build_digest(merchant="shopee"):
    """Trả về (ảnh, danh sách biến thể caption, comment chứa link). None nếu không có gì đáng đăng."""
    cs = [c for c in active() if c["merchant"] == merchant]
    if len(cs) < 2: return None
    today = datetime.date.today().strftime("%d/%m")
    lines = [((c["code"] or "Sự kiện"), c["title"] or c["detail"]) for c in cs]
    img = images.digest_card(f"Mã giảm giá {merchant.title()} {today}", lines, f"digest_{merchant}_{today.replace('/','')}")
    brief = "\n".join(f"- {c['title']} | mã: {c['code'] or 'không cần'} | hết hạn {datetime.datetime.fromtimestamp(c['end_at']):%d/%m %H:%M}" for c in cs)
    caps = None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            cli = anthropic.Anthropic(api_key=api_key)
            m = cli.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=1500, messages=[{"role": "user", "content":
                f"Viết 3 biến thể bài đăng group săn sale Facebook tiếng Việt tổng hợp ưu đãi {merchant} hôm nay ({today}).\n"
                f"Chỉ dùng đúng thông tin sau, không bịa mã hay điều kiện:\n{brief}\n"
                "Giọng người thật chia sẻ cho anh chị em trong group, ngắn gọn, mỗi mã 1 dòng, tối đa 2 emoji, "
                "cuối bài ghi 'link nhận mã mình để ở comment'. Trả JSON array 3 chuỗi."}])
            caps = json.loads(re.search(r"\[.*\]", m.content[0].text, re.S).group(0))
        except Exception as e:
            print("[coupons] Claude API notice:", type(e).__name__)

    if not caps:
        caps = [
            f"Tổng hợp mã giảm giá {merchant.title()} hôm nay ({today}) cho cả nhà săn sale nhé! Link nhận mã mình để ở comment nha 👇",
            f"Cập nhật nhanh một số voucher ngon {merchant.title()} ({today}) mới lên. Mọi người lưu mã sớm kẻo hết lượt, link ở comment nha!",
            f"Bản tin săn sale {today}: List mã giảm giá và freeship {merchant.title()} hôm nay. Link chi tiết mình để dưới bình luận nhé!"
        ]
    comment = "Link nhận mã:\n" + "\n".join(f"- {c['title'][:40]}: {c['aff_url']}" for c in cs if c["aff_url"])
    return img, caps, comment


