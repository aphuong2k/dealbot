"""Tải ảnh sản phẩm (từ field image của API affiliate) + tạo ảnh huy hiệu giá, ảnh tổng hợp mã giảm giá."""
import os, hashlib, requests, time
from PIL import Image, ImageDraw, ImageFont

IMG_DIR = "images"; os.makedirs(IMG_DIR, exist_ok=True)
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]   # cần font có dấu tiếng Việt

def _font(size):
    for p in FONT_PATHS:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def download(url, name):
    if not url: return None
    path = os.path.join(IMG_DIR, f"{name}.jpg")
    if os.path.exists(path): return path
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        open(path, "wb").write(r.content)
        Image.open(path).convert("RGB").save(path, quality=90)   # xác nhận là ảnh hợp lệ
        return path
    except Exception as e:
        print("download image fail:", e); return None

def prepare_deal_image(d):
    """Ảnh gốc + huy hiệu '-xx%' và giá. Mỗi bài một ảnh hơi khác nhau, nhìn tự nhiên hơn."""
    p = download(d.get("image"), "deal_" + hashlib.md5(d["id"].encode()).hexdigest()[:10])
    if not p: return None
    im = Image.open(p).convert("RGB"); im.thumbnail((1080, 1080))
    w, h = im.size; dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((16, 16, 200, 86), 14, fill=(238, 77, 45))
    dr.text((30, 28), f"-{d['discount']:.0f}%", font=_font(38), fill="white")
    dr.rounded_rectangle((16, h - 80, 16 + 330, h - 16), 14, fill=(0, 0, 0))
    dr.text((30, h - 70), f"{d['price']:,.0f}đ", font=_font(36), fill="white")
    out = p.replace(".jpg", "_b.jpg"); im.save(out, quality=90); return out

def digest_card(title, lines, name):
    """Ảnh tổng hợp: tiêu đề + danh sách mã/sự kiện. lines = [(nhãn, mô tả)]"""
    W, H = 1080, 160 + 110 * len(lines) + 40
    im = Image.new("RGB", (W, H), (255, 244, 238)); dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, W, 130), fill=(238, 77, 45))
    dr.text((40, 38), title, font=_font(48), fill="white")
    y = 160
    for lab, desc in lines:
        dr.rounded_rectangle((30, y, W - 30, y + 95), 16, fill="white", outline=(238, 77, 45), width=3)
        dr.text((55, y + 12), lab[:28], font=_font(34), fill=(238, 77, 45))
        dr.text((55, y + 54), desc[:60], font=_font(24), fill=(60, 60, 60))
        y += 110
    path = os.path.join(IMG_DIR, f"{name}.jpg"); im.save(path, quality=90); return path

def cleanup(days=7):
    cut = time.time() - days * 86400
    for f in os.listdir(IMG_DIR):
        p = os.path.join(IMG_DIR, f)
        if os.path.getmtime(p) < cut: os.remove(p)
