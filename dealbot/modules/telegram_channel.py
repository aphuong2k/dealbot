"""Module quản lý kênh Telegram riêng (Broadcast Channel) & Phễu kéo thành viên.
Giúp xây dựng tài sản cá nhân lâu dài, đăng bài chính thức 100% an toàn bằng Bot API.
"""
import os, json, requests

def _get_credentials(cfg):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chan = os.getenv("TELEGRAM_CHANNEL_ID") or (cfg.get("telegram_channel") or {}).get("channel_id")
    return tok, chan

def get_funnel_cta(cfg):
    """Tạo lời kêu gọi tham gia kênh Telegram riêng để phễu từ Facebook sang."""
    funnel_cfg = cfg.get("funnel", {})
    invite_link = funnel_cfg.get("telegram_invite") or os.getenv("TELEGRAM_INVITE_LINK")
    if not invite_link:
        return ""
    text_tmpl = funnel_cfg.get("cta_text", "👉 Nhận mã giảm giá & deal sớm nhất tại Telegram: {invite_link}")
    return "\n" + text_tmpl.format(invite_link=invite_link)

def post_deal_to_channel(cfg, deal, aff_url=None):
    """Đăng deal lẻ nổi bật lên kênh Telegram với hình ảnh, giá sale, và nút mua."""
    tok, chan = _get_credentials(cfg)
    if not (tok and chan):
        print("[telegram_channel] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHANNEL_ID")
        return False

    deal = dict(deal) if deal else {}
    link = aff_url or deal.get("aff_url") or deal.get("url")
    title = deal.get("title", "")
    price = deal.get("price", 0)
    discount = deal.get("discount", 0)

    rating = deal.get("rating", 5)
    sold = deal.get("sold", 0)
    niche = deal.get("niche", "Săn Sale").replace(" ", "")

    caption = (
        f"🔥 <b>{title}</b>\n\n"
        f"💰 Giá sale: <b>{price:,.0f}đ</b> (Giảm -{discount:.0f}%)\n"
        f"⭐️ Đánh giá: {rating}★ | Đã bán: {sold:,}\n\n"
        f"👉 <a href='{link}'>Bấm vào đây để đặt mua</a>\n\n"
        f"#{niche} #Shopee #DealGiaRe"
    )

    reply_markup = json.dumps({
        "inline_keyboard": [
            [{"text": "🛒 Mua ngay trên Shopee", "url": link}]
        ]
    })

    img_path = deal.get("image_path")
    try:
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{tok}/sendPhoto",
                    data={"chat_id": chan, "caption": caption, "parse_mode": "HTML", "reply_markup": reply_markup},
                    files={"photo": f},
                    timeout=25
                )
        elif deal.get("image"):
            r = requests.post(
                f"https://api.telegram.org/bot{tok}/sendPhoto",
                data={"chat_id": chan, "photo": deal["image"], "caption": caption, "parse_mode": "HTML", "reply_markup": reply_markup},
                timeout=25
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data={"chat_id": chan, "text": caption, "parse_mode": "HTML", "reply_markup": reply_markup},
                timeout=25
            )
        return r.status_code == 200
    except Exception as e:
        print("[telegram_channel] Lỗi đăng deal lên kênh:", e)
        return False

def post_digest_to_channel(cfg, title, coupon_lines, img_path=None, links_text=""):
    """Đăng bản tin tổng hợp mã giảm giá và sự kiện lên kênh Telegram."""
    tok, chan = _get_credentials(cfg)
    if not (tok and chan):
        print("[telegram_channel] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHANNEL_ID")
        return False

    summary_items = []
    for code, desc in coupon_lines[:8]:
        summary_items.append(f"▫️ <b>[{code}]</b> {desc}")
    
    text = (
        f"🎟 <b>{title}</b>\n\n"
        + "\n".join(summary_items) + "\n\n"
        + (f"🔗 <b>Chi tiết nhận mã:</b>\n{links_text}\n\n" if links_text else "")
        + "🔔 Bật thông báo kênh để không bỏ lỡ deal chớp nhoáng!\n#Voucher #Shopee #MaGiamGia"
    )

    try:
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{tok}/sendPhoto",
                    data={"chat_id": chan, "caption": text[:1024], "parse_mode": "HTML"},
                    files={"photo": f},
                    timeout=30
                )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data={"chat_id": chan, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=25
            )
        return r.status_code == 200
    except Exception as e:
        print("[telegram_channel] Lỗi đăng bản tin lên kênh:", e)
        return False
